import math
import re
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

    def search(self, question: str, limit: int = TOP_K) -> list[dict]:
        if not self._load():
            return []
        chunks = self.corpus.chunks()
        if not chunks:
            return []
        vector = self._model.encode([question], normalize_embeddings=True)
        scores, positions = self._index.search(vector, TOP_K)
        evidence = []
        for score, position in zip(scores[0], positions[0]):
            if position < 0 or position >= len(chunks):
                continue
            chunk = chunks[int(position)]
            evidence.append(
                {
                    "document_id": chunk["document_id"],
                    "document": chunk["document_name"],
                    "chunk_id": chunk["chunk_id"],
                    "section_path": chunk["section_path"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "score": round(float(score), 4),
                    "content_preview": chunk.get("chunk_text", chunk["text"])[:220],
                    "content": chunk.get("chunk_text", chunk["text"]),
                }
            )
        return evidence[:limit]
