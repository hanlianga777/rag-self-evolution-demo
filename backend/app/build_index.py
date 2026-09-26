"""Build the local robot-PDF vector index. Run with: python -m app.build_index."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np

from .corpus import (
    DOCUMENTS_DIR,
    EMBEDDING_MODEL,
    INDEX_DIR,
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    chunk_sections,
    current_manifest,
    discover_documents,
    is_current,
    source_fingerprint,
    tokenizer_token_count,
)


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _toc_paths(pdf) -> dict[int, str]:
    entries = pdf.get_toc(simple=True)
    paths, stack = {}, []
    for level, title, page in entries:
        stack = stack[: level - 1]
        stack.append(title.strip())
        paths[page] = " / ".join(stack)
    return paths


def _section_for_page(page_number: int, toc_paths: dict[int, str]) -> str:
    preceding = [page for page in toc_paths if page <= page_number]
    return toc_paths[max(preceding)] if preceding else f"第 {page_number} 页"


def _heading_lines(page) -> set[str]:
    """Return only visibly larger, short PDF text lines as reliable headings."""
    lines = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if text and spans:
                lines.append((text, max(span.get("size", 0) for span in spans)))
    if not lines:
        return set()
    baseline = median(size for _, size in lines)
    return {
        text.replace("\xa0", " ").strip()
        for text, size in lines
        if size >= baseline * 1.5 and 1 < len(text.strip()) <= 48 and not text.rstrip().endswith(("。", "！", "？", "."))
    }


def _heading_sections(raw_pages: list[dict]) -> list[dict]:
    """Keep contiguous PDF text under its detected heading, including across pages."""
    sections, active = [], None
    for item in raw_pages:
        headings = item["headings"]
        lines, current = item["text"].splitlines(), []
        for line in lines:
            normalized = line.replace("\xa0", " ").strip()
            if normalized in headings:
                if current:
                    sections.append({"page": item["page"], "text": "\n".join(current), "section_path": active or f"第 {item['page']} 页"})
                active, current = normalized, [line]
            else:
                current.append(line)
        if current:
            sections.append({"page": item["page"], "text": "\n".join(current), "section_path": active or f"第 {item['page']} 页"})
    return sections


def _ocr_page(ocr, page) -> str:
    # Render locally; no source bytes leave this process.
    import pymupdf

    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    result = ocr(pixmap.tobytes("png"))
    texts = getattr(result, "txts", None) or getattr(result, "texts", None) or []
    return "\n".join(str(item).strip() for item in texts if str(item).strip())


def _parse_document(catalog: dict, ocr, token_counter) -> tuple[dict, list[dict]]:
    import pymupdf

    source = DOCUMENTS_DIR / catalog["name"]
    record = {
        **catalog,
        "pages": None,
        "chunks": 0,
        "status": "Parse Failed",
        "parser": "PyMuPDF",
        "ocr": "未执行",
        "chunk_strategy": "待解析",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_fingerprint": source_fingerprint(catalog),
    }
    try:
        pdf = pymupdf.open(source)
        record["pages"] = pdf.page_count
        toc_paths = _toc_paths(pdf)
        raw_pages = []
        used_ocr = False
        for offset, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            if not text:
                used_ocr = True
                text = _ocr_page(ocr, page)
            if text:
                raw_pages.append({"page": offset, "text": text, "headings": _heading_lines(page) if not used_ocr else set()})
        non_whitespace = sum(len("".join(item["text"].split())) for item in raw_pages)
        record["ocr"] = "RapidOCR 本地中文 OCR" if used_ocr else "不需要（PDF 文字层）"
        if not raw_pages or non_whitespace < 100:
            record["status"] = "Needs OCR"
            return record, []
        if toc_paths:
            pages = [{"page": item["page"], "text": item["text"], "section_path": _section_for_page(item["page"], toc_paths)} for item in raw_pages]
            record["chunk_strategy"] = f"PDF 目录章节 → 连续段落，{TARGET_TOKENS} tokens，{OVERLAP_TOKENS} overlap"
        elif not used_ocr and sum(len(item["headings"]) for item in raw_pages) >= 2:
            pages = _heading_sections(raw_pages)
            record["chunk_strategy"] = f"PDF 正文短标题章节 → 连续段落，{TARGET_TOKENS} tokens，{OVERLAP_TOKENS} overlap"
        else:
            pages = [{"page": item["page"], "text": item["text"], "section_path": f"第 {item['page']} 页（页级/段落 fallback）"} for item in raw_pages]
            record["chunk_strategy"] = f"页级/段落 fallback，{TARGET_TOKENS} tokens，{OVERLAP_TOKENS} overlap"
        chunks = chunk_sections(catalog, pages, token_counter=token_counter)
        if not chunks:
            record["status"] = "Needs OCR"
            return record, []
        record["chunks"] = len(chunks)
        record["status"] = "Parsed"
        return record, chunks
    except Exception as error:  # State is visible in the inspector; no fabricated text is emitted.
        record["error"] = str(error)
        return record, []


def build_index(force: bool = False) -> int:
    if not force and is_current():
        print("索引已是最新状态：PDF 指纹未变化，无需重建。")
        return 0

    try:
        from rapidocr import RapidOCR
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer
        import faiss
    except ImportError as error:
        print(f"索引依赖不可用：{error}。请运行 python3 -m pip install -r backend/requirements.txt", file=sys.stderr)
        return 1

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "faiss.index").unlink(missing_ok=True)
    print("正在初始化本地 RapidOCR（PDF 不会上传）。")
    try:
        ocr = RapidOCR()
    except Exception as error:
        print(f"OCR 初始化失败：{error}", file=sys.stderr)
        return 1

    try:
        print(f"正在加载 BGE tokenizer：{EMBEDDING_MODEL}")
        tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
    except Exception as error:
        print(f"BGE tokenizer 初始化失败：{error}", file=sys.stderr)
        return 1
    token_counter = lambda text: tokenizer_token_count(tokenizer, text)

    documents, chunks = [], []
    for catalog in discover_documents():
        print(f"解析：{catalog['name']}")
        record, parsed_chunks = _parse_document(catalog, ocr, token_counter)
        documents.append(record)
        chunks.extend(parsed_chunks)
        print(f"  {record['status']}，{record['chunks']} 个真实分块")

    if chunks:
        try:
            print(f"首次运行：正在下载 {EMBEDDING_MODEL}（如本机尚无缓存）。")
            model = SentenceTransformer(EMBEDDING_MODEL)
            vectors = model.encode([chunk["chunk_text"] for chunk in chunks], normalize_embeddings=True, show_progress_bar=True)
            vectors = np.asarray(vectors, dtype="float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(INDEX_DIR / "faiss.index"))
            for chunk in chunks:
                chunk["embedding_status"] = "Indexed"
            for document in documents:
                if document["status"] == "Parsed":
                    document["status"] = "Indexed"
        except Exception as error:
            for document in documents:
                if document["status"] == "Parsed":
                    document["status"] = "Embedding Failed"
                    document["error"] = str(error)
            for chunk in chunks:
                chunk["embedding_status"] = "Failed"
            print(f"Embedding/FAISS 构建失败：{error}", file=sys.stderr)
    else:
        print("没有通过质量检查的可索引文本；文档将显示 Needs OCR / Parse Failed。")

    _write_json(INDEX_DIR / "documents.json", documents)
    _write_json(INDEX_DIR / "chunks.json", chunks)
    _write_json(INDEX_DIR / "manifest.json", current_manifest())
    print(f"索引完成：{sum(item['status'] == 'Indexed' for item in documents)} 份文档，{len(chunks)} 个分块。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the local robot PDF FAISS index")
    parser.add_argument("--if-needed", action="store_true", help="skip when PDF fingerprints and settings are unchanged")
    parser.add_argument("--force", action="store_true", help="rebuild even when fingerprints are unchanged")
    args = parser.parse_args()
    return build_index(force=args.force or not args.if_needed)


if __name__ == "__main__":
    raise SystemExit(main())
