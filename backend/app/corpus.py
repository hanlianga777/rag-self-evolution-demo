"""Local, source-faithful PDF parsing and chunk metadata helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable


EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
TARGET_TOKENS = 400
OVERLAP_TOKENS = 60
TOP_K = 4
INDEX_DIR = Path(__file__).resolve().parents[1] / "data" / "index"
DOCUMENTS_DIR = Path(__file__).resolve().parents[1] / "documents"

DOCUMENT_CATALOG = [
    {
        "id": "DOC-001",
        "chunk_prefix": "KIRA-B50",
        "name": "卡赫_KIRA_B_50完整操作说明_中文版.pdf",
        "category": "商用清洁机器人",
        "vendor": "卡赫",
        "product": "KIRA B 50",
        "document_type": "完整操作说明",
    },
    {
        "id": "DOC-002",
        "chunk_prefix": "B2-MANUAL",
        "name": "宇树_B2四足机器人用户手册_中文版.pdf",
        "category": "工业巡检机器人",
        "vendor": "宇树科技",
        "product": "B2 四足机器人",
        "document_type": "用户手册",
    },
    {
        "id": "DOC-003",
        "chunk_prefix": "B2-REMOTE",
        "name": "宇树_B2遥控器使用说明_中文版.pdf",
        "category": "工业巡检机器人",
        "vendor": "宇树科技",
        "product": "B2 遥控器",
        "document_type": "使用说明",
    },
    {
        "id": "DOC-004",
        "chunk_prefix": "B2-BATTERY",
        "name": "宇树_B2电池与充电器使用说明_中文版.pdf",
        "category": "工业巡检机器人",
        "vendor": "宇树科技",
        "product": "B2 电池与充电器",
        "document_type": "使用说明",
    },
]


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _token_count(text: str) -> int:
    # Chinese has no spaces; counting CJK characters yields a predictable local
    # approximation and avoids a second tokenizer model solely for chunking.
    return len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", text))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[。！？；.!?])\s*|\n+", text) if part.strip()]


def _overlap(sentences: list[str], token_counter: Callable[[str], int], overlap_tokens: int) -> list[str]:
    kept, total = [], 0
    for sentence in reversed(sentences):
        count = token_counter(sentence)
        if kept and total + count > overlap_tokens:
            break
        kept.insert(0, sentence)
        total += count
    return kept


def chunk_sections(
    document: dict,
    pages: list[dict],
    token_counter: Callable[[str], int] = _token_count,
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[dict]:
    """Create stable chunks, never joining text from different source documents."""
    chunks, serial = [], 1
    for page in pages:
        sentences = _sentences(page.get("text", ""))
        current = []
        for sentence in sentences:
            proposed = "".join(current + [sentence])
            if current and token_counter(proposed) > target_tokens:
                text = "".join(current)
                chunks.append(_chunk(document, serial, page, text, token_counter(text)))
                serial += 1
                current = _overlap(current, token_counter, overlap_tokens) + [sentence]
            else:
                current.append(sentence)
        if current:
            text = "".join(current)
            chunks.append(_chunk(document, serial, page, text, token_counter(text)))
            serial += 1
    return chunks


def _chunk(document: dict, serial: int, page: dict, text: str, token_count: int) -> dict:
    return {
        "chunk_id": f"{document['chunk_prefix']}-CHUNK-{serial:04d}",
        "document_id": document["id"],
        "document_name": document["name"],
        "section_path": page.get("section_path") or f"第 {page['page']} 页",
        "page_start": page["page"],
        "page_end": page["page"],
        "token_count": token_count,
        "text": text,
    }


def source_fingerprint(document: dict) -> str | None:
    source = DOCUMENTS_DIR / document["name"]
    if not source.exists():
        return None
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_manifest() -> dict:
    return {
        "schema": 1,
        "embedding_model": EMBEDDING_MODEL,
        "target_tokens": TARGET_TOKENS,
        "overlap_tokens": OVERLAP_TOKENS,
        "sources": {entry["id"]: source_fingerprint(entry) for entry in DOCUMENT_CATALOG},
    }


def is_current() -> bool:
    existing = _read_json(INDEX_DIR / "manifest.json", {})
    return bool(existing) and existing == current_manifest() and (INDEX_DIR / "faiss.index").exists()


class CorpusStore:
    """Read-only view of persisted source-faithful corpus metadata."""

    def __init__(self, index_dir: Path = INDEX_DIR):
        self.index_dir = index_dir

    def documents(self) -> list[dict]:
        persisted = _read_json(self.index_dir / "documents.json", [])
        by_id = {entry["id"]: entry for entry in persisted}
        records = []
        for catalog in DOCUMENT_CATALOG:
            stored = by_id.get(catalog["id"], {})
            records.append(
                {
                    **catalog,
                    "pages": stored.get("pages"),
                    "chunks": stored.get("chunks", 0),
                    "status": stored.get("status", "Needs OCR"),
                    "parser": stored.get("parser", "未建立索引"),
                    "ocr": stored.get("ocr", "未执行"),
                    "chunk_strategy": stored.get("chunk_strategy", f"目录/段落切片，{TARGET_TOKENS} tokens，{OVERLAP_TOKENS} overlap"),
                    "updated_at": stored.get("updated_at", "待构建"),
                    "pdf_url": f"/documents/{catalog['name']}",
                    "source_fingerprint": stored.get("source_fingerprint"),
                }
            )
        return records

    def chunks(self, document_id: str | None = None) -> list[dict]:
        chunks = _read_json(self.index_dir / "chunks.json", [])
        return [item for item in chunks if document_id is None or item["document_id"] == document_id]

    def detail(self, document_id: str) -> dict | None:
        document = next((item for item in self.documents() if item["id"] == document_id), None)
        if document is None:
            return None
        return {**document, "chunk_count": document["chunks"], "index": self.index_info(), "chunks": self.chunks(document_id)}

    def index_info(self) -> dict:
        manifest = _read_json(self.index_dir / "manifest.json", {})
        return {
            "status": "Current" if is_current() else "Needs rebuild",
            "embedding_model": manifest.get("embedding_model", EMBEDDING_MODEL),
            "vector_index": "FAISS IndexFlatIP (normalized cosine similarity)",
            "top_k": TOP_K,
            "chunk_target_tokens": manifest.get("target_tokens", TARGET_TOKENS),
            "chunk_overlap_tokens": manifest.get("overlap_tokens", OVERLAP_TOKENS),
        }
