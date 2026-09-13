"""Build the local robot-PDF vector index. Run with: python -m app.build_index."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .corpus import (
    DOCUMENT_CATALOG,
    DOCUMENTS_DIR,
    EMBEDDING_MODEL,
    INDEX_DIR,
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    chunk_sections,
    current_manifest,
    is_current,
    source_fingerprint,
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


def _ocr_page(ocr, page) -> str:
    # Render locally; no source bytes leave this process.
    import pymupdf

    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    result = ocr(pixmap.tobytes("png"))
    texts = getattr(result, "txts", None) or getattr(result, "texts", None) or []
    return "\n".join(str(item).strip() for item in texts if str(item).strip())


def _parse_document(catalog: dict, ocr) -> tuple[dict, list[dict]]:
    import pymupdf

    source = DOCUMENTS_DIR / catalog["name"]
    record = {
        **catalog,
        "pages": None,
        "chunks": 0,
        "status": "Parse Failed",
        "parser": "PyMuPDF",
        "ocr": "未执行",
        "chunk_strategy": f"目录/页内自然段落，{TARGET_TOKENS} tokens，{OVERLAP_TOKENS} overlap",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_fingerprint": source_fingerprint(catalog),
    }
    try:
        pdf = pymupdf.open(source)
        record["pages"] = pdf.page_count
        toc_paths = _toc_paths(pdf)
        pages = []
        used_ocr = False
        for offset, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            if not text:
                used_ocr = True
                text = _ocr_page(ocr, page)
            if text:
                pages.append({"page": offset, "text": text, "section_path": _section_for_page(offset, toc_paths)})
        non_whitespace = sum(len("".join(item["text"].split())) for item in pages)
        record["ocr"] = "RapidOCR 本地中文 OCR" if used_ocr else "不需要（PDF 文字层）"
        if not pages or non_whitespace < 100:
            record["status"] = "Needs OCR"
            return record, []
        chunks = chunk_sections(catalog, pages)
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

    documents, chunks = [], []
    for catalog in DOCUMENT_CATALOG:
        print(f"解析：{catalog['name']}")
        record, parsed_chunks = _parse_document(catalog, ocr)
        documents.append(record)
        chunks.extend(parsed_chunks)
        print(f"  {record['status']}，{record['chunks']} 个真实分块")

    if chunks:
        try:
            print(f"首次运行：正在下载 {EMBEDDING_MODEL}（如本机尚无缓存）。")
            model = SentenceTransformer(EMBEDDING_MODEL)
            vectors = model.encode([chunk["text"] for chunk in chunks], normalize_embeddings=True, show_progress_bar=True)
            vectors = np.asarray(vectors, dtype="float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(INDEX_DIR / "faiss.index"))
            for document in documents:
                if document["status"] == "Parsed":
                    document["status"] = "Indexed"
        except Exception as error:
            for document in documents:
                if document["status"] == "Parsed":
                    document["status"] = "Embedding Failed"
                    document["error"] = str(error)
                    document["chunks"] = 0
            chunks = []
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
