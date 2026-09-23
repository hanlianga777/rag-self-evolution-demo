"""Offline, source-grounded chunk comparison; never writes the production index."""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from statistics import median

import numpy as np

from .build_index import _heading_lines, _heading_sections, _ocr_page, _section_for_page, _toc_paths
from .corpus import CorpusStore, DOCUMENT_CATALOG, DOCUMENTS_DIR, EMBEDDING_MODEL, INDEX_DIR, chunk_sections, tokenizer_token_count
from .policy import DEFAULT_PIPELINE_CONFIG
from .retrieval import VectorRetriever


def adaptive_chunks(document, pages, token_counter, *, target=400, soft_max=520, tiny=80, overlap=60):
    """Keep short coherent sections together and merge small adjacent same-section tails."""
    chunks = []
    group = []
    for page in [*pages, None]:
        if group and (page is None or page.get("section_path") != group[0].get("section_path")):
            length = token_counter("\n".join(item["text"] for item in group))
            # Procedure and warning text gets a larger intact window; short sections stay whole.
            group_target = min(soft_max, max(target, length)) if length <= soft_max else (450 if re.search(r"步骤|操作|安全|警告|注意", group[0].get("section_path", "")) else target)
            for chunk in chunk_sections(document, group, token_counter, group_target, overlap):
                if chunks and chunk["token_count"] < tiny and chunks[-1]["section_path"] == chunk["section_path"] and token_counter(chunks[-1]["chunk_text"] + "\n" + chunk["chunk_text"]) <= soft_max:
                    previous = chunks[-1]
                    previous["chunk_text"] += "\n" + chunk["chunk_text"]
                    previous["text"] = previous["chunk_text"]
                    previous["token_count"] = token_counter(previous["chunk_text"])
                    previous["page_end"] = max(previous["page_end"], chunk["page_end"])
                else:
                    chunks.append(chunk)
            group = []
        if page is not None:
            group.append(page)
    for serial, chunk in enumerate(chunks, 1):
        chunk["chunk_id"] = f"{document['chunk_prefix']}-AUDIT-{serial:04d}"
    return chunks


def _clean(value):
    return re.sub(r"\s+", "", value).replace("\xa0", "")


def evidence_matches(evidence, hit):
    if evidence["document_id"] != hit["document_id"] or evidence["page_end"] < hit["page_start"] or hit["page_end"] < evidence["page_start"]:
        return False
    content = _clean(hit["content"])
    return any(_clean(point) in content for point in evidence["key_points"] if len(_clean(point)) >= 5)


def _pages(catalog, ocr):
    import pymupdf

    with pymupdf.open(DOCUMENTS_DIR / catalog["name"]) as pdf:
        toc = _toc_paths(pdf)
        raw = []
        used_ocr = False
        for number, page in enumerate(pdf, 1):
            value = page.get_text("text").strip()
            if not value:
                used_ocr = True
                value = _ocr_page(ocr, page)
            if value:
                raw.append({"page": number, "text": value, "headings": _heading_lines(page) if not used_ocr else set()})
        if toc:
            return [{"page": item["page"], "text": item["text"], "section_path": _section_for_page(item["page"], toc)} for item in raw]
        if not used_ocr and sum(len(item["headings"]) for item in raw) >= 2:
            return _heading_sections(raw)
        return [{"page": item["page"], "text": item["text"], "section_path": f"第 {item['page']} 页（页级/段落 fallback）"} for item in raw]


def _score(cases, inventory, results):
    topics = {item["evidence_id"]: item for item in inventory["topics"]}
    rows = []
    for case, hits in zip(cases, results):
        evidence = [topics[key] for key in case["source_evidence_ids"]]
        matched = [[rank for rank, hit in enumerate(hits, 1) if evidence_matches(item, hit)] for item in evidence]
        ranks = [rank for group in matched for rank in group]
        rows.append({"id": case["id"], "hit_1": bool(ranks and min(ranks) == 1), "hit_4": bool(ranks), "recall_4": sum(bool(group) for group in matched) / len(evidence), "rr": 1 / min(ranks) if ranks else 0, "matched_evidence": sum(bool(group) for group in matched), "total_evidence": len(evidence), "top4": [{"rank": rank, "document_id": hit["document_id"], "page": [hit["page_start"], hit["page_end"]], "chunk_id": hit["chunk_id"]} for rank, hit in enumerate(hits, 1)]})
    n = len(rows)
    return {"hit_1": sum(row["hit_1"] for row in rows) / n, "hit_4": sum(row["hit_4"] for row in rows) / n, "recall_4": sum(row["recall_4"] for row in rows) / n, "mrr": sum(row["rr"] for row in rows) / n, "rows": rows}


def _stats(chunks, index_bytes):
    counts = [chunk["token_count"] for chunk in chunks]
    return {"chunks": len(chunks), "median_tokens": median(counts), "tiny_under_80": sum(count < 80 for count in counts), "oversize_over_520": sum(count > 520 for count in counts), "page_traceable": sum(isinstance(chunk.get("page_start"), int) and isinstance(chunk.get("page_end"), int) and chunk["page_start"] <= chunk["page_end"] for chunk in chunks), "index_bytes": index_bytes}


def run():
    import faiss
    from rapidocr import RapidOCR
    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer

    cases = json.loads((Path(__file__).resolve().parents[1] / "reports/golden_dataset_grounded_draft.json").read_text())["cases"]
    inventory = json.loads((Path(__file__).resolve().parents[1] / "reports/golden_evidence_inventory.json").read_text())
    baseline_chunks = CorpusStore().chunks()
    tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL, local_files_only=True)
    counter = lambda value: tokenizer_token_count(tokenizer, value)
    ocr = RapidOCR()
    candidate = []
    for catalog in DOCUMENT_CATALOG:
        candidate.extend(adaptive_chunks(catalog, _pages(catalog, ocr), counter))
    model = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
    vectors = np.asarray(model.encode([item["chunk_text"] for item in candidate], normalize_embeddings=True, show_progress_bar=False), dtype="float32")
    index = faiss.IndexFlatIP(vectors.shape[1]); index.add(vectors)
    with tempfile.TemporaryDirectory(prefix="rag-chunk-audit-") as directory:
        path = Path(directory)
        faiss.write_index(index, str(path / "faiss.index"))
        (path / "chunks.json").write_text(json.dumps(candidate, ensure_ascii=False))
        baseline = VectorRetriever(CorpusStore(), INDEX_DIR)
        alternative = VectorRetriever(CorpusStore(path), path)
        baseline._index = faiss.read_index(str(INDEX_DIR / "faiss.index")); baseline._model = model
        alternative._index = index; alternative._model = model
        outcomes = {}
        for name, retriever, chunks, size in (("baseline", baseline, baseline_chunks, (INDEX_DIR / "faiss.index").stat().st_size), ("candidate", alternative, candidate, (path / "faiss.index").stat().st_size)):
            # Warm BGE once per retriever, then measure the same production retrieval config.
            retriever.retrieve(cases[0]["question"], DEFAULT_PIPELINE_CONFIG)
            all_hits, latency = [], []
            for case in cases:
                start = time.perf_counter()
                all_hits.append(retriever.retrieve(case["question"], DEFAULT_PIPELINE_CONFIG))
                latency.append((time.perf_counter() - start) * 1000)
            scored = _score(cases, inventory, all_hits)
            outcomes[name] = {"metrics": {key: scored[key] for key in ("hit_1", "hit_4", "recall_4", "mrr")}, "rows": scored["rows"], "structure": _stats(chunks, size), "latency_p95_ms": float(np.percentile(latency, 95))}
    return outcomes


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
