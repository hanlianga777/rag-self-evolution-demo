import math
import re
from collections import Counter
from pathlib import Path

from .corpus import EMBEDDING_MODEL, INDEX_DIR, TOP_K


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]", text.lower()))


class LocalRetriever:
    """Legacy token retriever retained only for isolated tests/debugging."""
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def search(self, question: str, limit: int = 3) -> list[dict]:
        query_terms = _terms(question)
        ranked = []
        for document in self.documents:
            chunks = document.get("samples", [])
            for index, chunk in enumerate(chunks, start=1):
                text = f"{document['name']} {chunk}"
                terms = _terms(text)
                shared = query_terms & terms
                score = len(shared) / math.sqrt(max(1, len(query_terms) * len(terms)))
                if score:
                    ranked.append({"document": document["name"], "chunk": index, "content": chunk, "score": round(score, 3)})
        return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]


class VectorRetriever:
    """Local BGE + FAISS retrieval over persisted, real PDF chunks."""

    def __init__(self, corpus, index_dir: Path = INDEX_DIR):
        self.corpus = corpus
        self.index_dir = index_dir
        self._index = None
        self._model = None

    def _load(self):
        if self._index is not None:
            return True
        index_file = self.index_dir / "faiss.index"
        if not index_file.exists():
            return False
        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            self._index = faiss.read_index(str(index_file))
            self._model = SentenceTransformer(EMBEDDING_MODEL)
            return True
        except Exception:
            self._index = None
            self._model = None
            return False

    def vector_candidates(self, question: str, limit: int = TOP_K) -> list[dict]:
        """Initial BGE/FAISS recall. Filtering belongs to the pipeline, never here."""
        if not self._load():
            return []
        chunks = self.corpus.chunks()
        if not chunks:
            return []
        vector = self._model.encode([question], normalize_embeddings=True)
        scores, positions = self._index.search(vector, limit)
        evidence = []
        for score, position in zip(scores[0], positions[0]):
            if position < 0 or position >= len(chunks):
                continue
            chunk = chunks[int(position)]
            evidence.append(
                {
                    "document_id": chunk["document_id"],
                    "document": chunk["document_name"],
                    "product": chunk.get("product"),
                    "chunk_id": chunk["chunk_id"],
                    "section": chunk.get("section"),
                    "section_path": chunk["section_path"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "score": round(float(score), 4),
                    "content_preview": chunk.get("chunk_text", chunk["text"])[:220],
                    "content": chunk.get("chunk_text", chunk["text"]),
                }
            )
        return evidence

    def search(self, question: str, limit: int = TOP_K, min_score: float | None = None) -> list[dict]:
        """Compatibility entrypoint for read-only callers and retrieval smoke tests."""
        results = self.vector_candidates(question, limit)
        return [item for item in results if min_score is None or item["score"] >= min_score]

    @staticmethod
    def _normalize(values: dict[str, float]) -> dict[str, float]:
        if not values:
            return {}
        low, high = min(values.values()), max(values.values())
        if high == low:
            return {key: 1.0 for key in values}
        return {key: (value - low) / (high - low) for key, value in values.items()}

    def _bm25(self, question: str) -> dict[str, float]:
        chunks = self.corpus.chunks()
        query_terms = _terms(question)
        if not query_terms or not chunks:
            return {}
        documents = [(chunk.get("chunk_id"), _terms(chunk.get("chunk_text", chunk.get("text", "")))) for chunk in chunks]
        total = len(documents)
        average_length = sum(len(terms) for _, terms in documents) / total or 1
        document_frequency = Counter(term for _, terms in documents for term in terms)
        scores = {}
        for chunk_id, terms in documents:
            if not chunk_id:
                continue
            score = 0.0
            for term in query_terms:
                frequency = 1 if term in terms else 0
                if not frequency:
                    continue
                inverse_frequency = math.log(1 + (total - document_frequency[term] + .5) / (document_frequency[term] + .5))
                score += inverse_frequency * (frequency * 2.2) / (frequency + 1.2 * (1 - .75 + .75 * len(terms) / average_length))
            scores[chunk_id] = score
        return scores

    @staticmethod
    def _materialize(chunk: dict, score: float) -> dict:
        return {
            "document_id": chunk["document_id"], "document": chunk.get("document_name", chunk.get("document", "")),
            "product": chunk.get("product"), "vendor": chunk.get("vendor"), "chunk_id": chunk["chunk_id"],
            "section": chunk.get("section"), "section_path": chunk.get("section_path"),
            "page_start": chunk.get("page_start"), "page_end": chunk.get("page_end"), "score": round(float(score), 4),
            "content_preview": chunk.get("chunk_text", chunk.get("text", ""))[:220], "content": chunk.get("chunk_text", chunk.get("text", "")),
        }

    def _metadata_candidates(self, question: str, mode: str, chunks: list[dict]) -> list[dict]:
        if mode == "OFF":
            return chunks
        normalized = _terms(question)
        selected = [chunk for chunk in chunks if normalized & (_terms(str(chunk.get("product", ""))) | _terms(str(chunk.get("vendor", ""))) | _terms(str(chunk.get("document_name", ""))))]
        return selected if selected or mode == "STRICT" else chunks

    def retrieve(self, question: str, config: dict, *, aliases: dict[str, str] | None = None, queries: list[str] | None = None) -> list[dict]:
        """V1.0.1 pipeline: CandidateK → normalized Hybrid → Rerank → MinScore → TopK."""
        aliases = aliases or {}
        rewritten = question
        for alias, canonical in aliases.items():
            rewritten = rewritten.replace(alias, canonical)
        query_list = [rewritten, *(queries or [])]
        candidate_k = int(config.get("candidate_k", 12))
        chunks = self._metadata_candidates(rewritten, config.get("metadata_filter", "OFF"), self.corpus.chunks())
        by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        vector_scores, bm25_scores = {}, {}
        for query in query_list:
            for hit in self.vector_candidates(query, candidate_k):
                if hit["chunk_id"] in by_id:
                    vector_scores[hit["chunk_id"]] = max(vector_scores.get(hit["chunk_id"], float("-inf")), float(hit["score"]))
            for chunk_id, score in sorted(self._bm25(query).items(), key=lambda item: item[1], reverse=True)[:candidate_k]:
                if chunk_id in by_id:
                    bm25_scores[chunk_id] = max(bm25_scores.get(chunk_id, float("-inf")), score)
        candidate_ids = set(vector_scores) | set(bm25_scores)
        vector_normalized = self._normalize({key: vector_scores.get(key, 0.0) for key in candidate_ids})
        bm25_normalized = self._normalize({key: bm25_scores.get(key, 0.0) for key in candidate_ids})
        alpha = float(config.get("hybrid_alpha", .5))
        ranked = []
        for chunk_id in candidate_ids:
            vector_score, bm25_score = vector_normalized.get(chunk_id, 0.0), bm25_normalized.get(chunk_id, 0.0)
            combined = alpha * vector_score + (1 - alpha) * bm25_score if config.get("hybrid_search", True) else vector_score
            ranked.append({"chunk_id": chunk_id, "vector_score": vector_score, "bm25_score": bm25_score, "combined": combined})
        # CandidateK caps the shared recall pool before the optional second stage.
        ranked = sorted(ranked, key=lambda item: item["combined"], reverse=True)[:candidate_k]
        output = []
        query_terms = _terms(" ".join(query_list))
        for item in ranked:
            chunk = by_id[item["chunk_id"]]
            lexical_coverage = len(query_terms & _terms(chunk.get("chunk_text", chunk.get("text", "")))) / max(1, len(query_terms))
            # Keep the fused score in the rerank signal: Alpha must remain observable when rerank is enabled.
            rerank_score = (0.8 * item["combined"] + 0.2 * lexical_coverage) if config.get("rerank", True) else None
            final_score = rerank_score if rerank_score is not None else item["combined"]
            output.append({**self._materialize(chunk, final_score), "vector_normalized": round(item["vector_score"], 4), "bm25_normalized": round(item["bm25_score"], 4), "hybrid_score": round(item["combined"], 4), "rerank_score": round(rerank_score, 4) if rerank_score is not None else None, "final_score": round(final_score, 4)})
        minimum = float(config.get("min_score", 0))
        return [item for item in sorted(output, key=lambda item: item["final_score"], reverse=True) if item["final_score"] >= minimum][:int(config.get("top_k", 4))]
