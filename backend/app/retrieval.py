import math
from contextlib import contextmanager
from copy import deepcopy
import re
from collections import Counter
from pathlib import Path

from .telemetry import measure
from .corpus import EMBEDDING_MODEL, INDEX_DIR, TOP_K, CorpusStore
from .full_text import CORPUS_LOCK, validate_bundle, search_full_text


class RetrievalUnavailable(RuntimeError):
    """An unexecuted/failed stage is never an empty retrieval observation."""
    def __init__(self, stage, error):
        self.detail = {'code': 'RETRIEVAL_EXECUTION_FAILED', 'stage': stage, 'error_type': type(error).__name__}
        self.trace = {'status': 'failed', 'candidates': None, 'final': None, 'error': self.detail}
        super().__init__(f"本地检索执行失败（{stage}/{type(error).__name__}）；请检查索引与本地模型")


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
        self.index_dir = corpus.index_dir if isinstance(corpus, CorpusStore) else index_dir
        self._bundle = None
        self._loaded_path = None
        self._index = None
        self._model = None

    @contextmanager
    def snapshot(self):
        with CORPUS_LOCK:
            if self._bundle is not None or not isinstance(self.corpus, CorpusStore):
                yield self._bundle
                return
            path = self.index_dir.resolve()
            try:
                bundle = validate_bundle(path)
            except Exception as error:
                raise RetrievalUnavailable('corpus_bundle', error) from error
            if self._loaded_path != path:
                self._index = None
                self._loaded_path = path
            self._bundle = bundle
            try:
                yield bundle
            finally:
                self._bundle = None

    def invalidate(self):
        with CORPUS_LOCK:
            self._index = None
            self._loaded_path = None

    def _chunks(self):
        return self._bundle['chunks'] if self._bundle is not None else self.corpus.chunks()

    def full_text_probe(self, question):
        with self.snapshot():
            return search_full_text(question, self._bundle.get('full_text') if self._bundle else None)

    def _load(self):
        if self._index is not None:
            return True
        index_file = (self._bundle["path"] if self._bundle else self.index_dir) / "faiss.index"
        if not index_file.exists():
            raise RetrievalUnavailable('vector_load', FileNotFoundError('FAISS index missing'))
        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            self._index = faiss.read_index(str(index_file))
            self._model = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
            return True
        except Exception as error:
            self._index = None
            self._model = None
            raise RetrievalUnavailable('vector_load', error) from error

    def vector_candidates(self, question: str, limit: int = TOP_K, *, stages=None) -> list[dict]:
        try:
            with self.snapshot():
                return self._vector_candidates(question, limit, stages=stages)
        except RetrievalUnavailable:
            raise
        except Exception as error:
            raise RetrievalUnavailable('vector_search', error) from error

    def _vector_candidates(self, question: str, limit: int = TOP_K, *, stages=None) -> list[dict]:
        """Initial BGE/FAISS recall. Filtering belongs to the pipeline, never here."""
        if not self._load():
            raise RetrievalUnavailable('vector_load', RuntimeError('Vector stage unavailable'))
        chunks = self._chunks()
        if not chunks:
            return []
        with measure(stages, 'query_embedding', 'vector_search'):
            vector = self._model.encode([question], normalize_embeddings=True)
        with measure(stages, 'faiss_search', 'vector_search'):
            scores, positions = self._index.search(vector, limit)
        evidence = []
        for score, position in zip(scores[0], positions[0]):
            if position < 0 or position >= len(chunks):
                continue
            chunk = chunks[int(position)]
            content = chunk.get("chunk_text", chunk.get("text", ""))
            evidence.append(
                {
                    "document_id": chunk["document_id"],
                    "document": chunk.get("document_name") or chunk["document_id"],
                    "product": chunk.get("product"),
                    "chunk_id": chunk["chunk_id"],
                    "section": chunk.get("section"),
                    "section_path": chunk.get("section_path"),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "score": float(score),
                    "content_preview": content[:220],
                    "content": content,
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
        chunks = self._chunks()
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
            "document_id": chunk["document_id"], "document": chunk.get("document_name") or chunk.get("document") or chunk["document_id"],
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

    def retrieve(self, question: str, config: dict, *, aliases: dict[str, str] | None = None, queries: list[str] | None = None, stages: list | None = None, trace: dict | None = None) -> list[dict]:
        stages = stages if stages is not None else []
        try:
            with self.snapshot() as bundle:
                if trace is not None:
                    trace.update(status='running', corpus_fingerprint=deepcopy(bundle['manifest'].get('sources')) if bundle else None)
                return self._retrieve(question, config, aliases=aliases, queries=queries, stages=stages, trace=trace)
        except Exception as error:
            failure = error if isinstance(error, RetrievalUnavailable) else RetrievalUnavailable('retrieval_pipeline', error)
            failed_trace = {**(trace or {}), **failure.trace, 'config': deepcopy(config), 'question': question, 'timings': deepcopy(stages) if stages is not None else None, 'timing_unit': 'ms'}
            if trace is not None:
                trace.clear()
                trace.update(failed_trace)
            failure.trace = failed_trace
            if failure is error:
                raise
            raise failure from error

    def _retrieve(self, question, config, *, aliases=None, queries=None, stages=None, trace=None):
        """V1.0.1 pipeline: CandidateK → normalized Hybrid → Rerank → MinScore → TopK."""
        stages = stages if stages is not None else []
        stage_start = len(stages)
        aliases = aliases or {}
        rewritten = question
        for alias, canonical in aliases.items():
            rewritten = rewritten.replace(alias, canonical)
        query_list = [rewritten, *(queries or [])]
        candidate_k = int(config.get("candidate_k", 12))
        with measure(stages, 'metadata_filter', 'retrieval'):
            chunks = self._metadata_candidates(rewritten, config.get("metadata_filter", "OFF"), self._chunks())
        by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        vector_scores, bm25_scores = {}, {}
        for query in query_list:
            with measure(stages, "vector_search", "retrieval"):
                for hit in self.vector_candidates(query, candidate_k, stages=stages):
                    if hit["chunk_id"] in by_id:
                        vector_scores[hit["chunk_id"]] = max(vector_scores.get(hit["chunk_id"], float("-inf")), float(hit["score"]))
            with measure(stages, "bm25", "retrieval"):
                for chunk_id, score in sorted(self._bm25(query).items(), key=lambda item: item[1], reverse=True)[:candidate_k]:
                    if chunk_id in by_id:
                        bm25_scores[chunk_id] = max(bm25_scores.get(chunk_id, float("-inf")), score)
        with measure(stages, "hybrid_fusion" if config.get("hybrid_search", True) else "candidate_selection", "retrieval"):
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
            ranked = sorted(ranked, key=lambda item: (-item["combined"], item["chunk_id"]))[:candidate_k]
        if trace is not None:
            trace.update({'status': 'collected', 'candidate_stage': 'post_metadata_filter_fusion_candidate_cap_pre_rerank',
                          'config': deepcopy(config), 'question': question, 'queries': query_list, 'aliases': deepcopy(aliases),
                          'corpus_fingerprint': deepcopy(self._bundle['manifest'].get('sources')) if self._bundle else None,
                          'artifact_schema_version': self._bundle['manifest'].get('artifact_schema_version') if self._bundle else None,
                          'candidates': [{**self._materialize(by_id[item['chunk_id']], item['combined']), 'rank': rank,
                                          'vector_raw': vector_scores.get(item['chunk_id']), 'bm25_raw': bm25_scores.get(item['chunk_id']),
                                          'vector_normalized': item['vector_score'], 'bm25_normalized': item['bm25_score'], 'fusion_score': item['combined'],
                                          'sources': [name for name, scores in [('vector', vector_scores), ('bm25', bm25_scores)] if item['chunk_id'] in scores]}
                                         for rank, item in enumerate(ranked, 1)]})
        output = []
        query_terms = _terms(" ".join(query_list))
        for item in ranked:
            chunk = by_id[item["chunk_id"]]
            lexical_coverage = len(query_terms & _terms(chunk.get("chunk_text", chunk.get("text", "")))) / max(1, len(query_terms))
            # Keep the fused score in the rerank signal: Alpha must remain observable when rerank is enabled.
            rerank_score = None
            if config.get("rerank", True):
                with measure(stages, "rerank", "retrieval"):
                    rerank_score = 0.8 * item["combined"] + 0.2 * lexical_coverage
            final_score = rerank_score if rerank_score is not None else item["combined"]
            output.append({**self._materialize(chunk, final_score), "vector_normalized": round(item["vector_score"], 4), "bm25_normalized": round(item["bm25_score"], 4), "hybrid_score": round(item["combined"], 4), "rerank_score": round(rerank_score, 4) if rerank_score is not None else None, "final_score": round(final_score, 4)})
        minimum = float(config.get("min_score", 0))
        with measure(stages, 'threshold_top_k', 'retrieval'):
            final = [item for item in sorted(output, key=lambda item: (-item['final_score'], item['chunk_id'])) if item['final_score'] >= minimum][:int(config.get('top_k', 4))]
        if trace is not None:
            trace['final'] = [{**item, 'rank': rank} for rank, item in enumerate(final, 1)]
            trace['timings'] = deepcopy(stages[stage_start:])
            trace['timing_unit'] = 'ms'
        return final


def evidence_coverage(trace, required_ids):
    """Missing historical candidates remain unknown; Any does not establish All."""
    required = sorted(set(required_ids))
    result = {'required_chunk_ids': required}
    for field, key in (('candidate_recall', 'candidates'), ('final_context', 'final')):
        entries = trace.get(key) if trace else None
        intersection = sorted(set(required) & {entry['chunk_id'] for entry in entries}) if entries is not None else None
        result[field] = {'status': 'collected' if entries is not None else 'not_collected', 'matched_chunk_ids': intersection,
                         'any_hit': bool(intersection) if intersection is not None and required else None,
                         'all_hit': len(intersection) == len(required) if intersection is not None and required else None,
                         'coverage': len(intersection) / len(required) if intersection is not None and required else None}
    candidate, final = result['candidate_recall'], result['final_context']
    result['diagnostic_basis'] = ('final_evidence_available' if final['all_hit'] is True else
                                  'ranking_context_selection_failure' if candidate['all_hit'] is True and final['all_hit'] is False else
                                  'retrieval_failure' if candidate['all_hit'] is False else 'not_collected')
    return result
