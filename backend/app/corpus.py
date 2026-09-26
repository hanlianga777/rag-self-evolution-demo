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


def discover_documents() -> list[dict]:
    """Discover current PDFs, preserving known document identities and metadata."""
    known = {entry["name"]: entry for entry in DOCUMENT_CATALOG}
    records = []
    for source in sorted(DOCUMENTS_DIR.glob("*.pdf"), key=lambda path: path.name):
        catalog = known.get(source.name)
        if catalog is None:
            identifier = "DOC-" + hashlib.sha256(source.name.encode("utf-8")).hexdigest()[:12]
            catalog = {"id": identifier, "name": source.name, "chunk_prefix": identifier}
        records.append(catalog.copy())
    return records


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def tokenizer_token_count(tokenizer, text: str) -> int:
    """Count exactly the token ids used by the installed BGE tokenizer."""
    return len(tokenizer.encode(text, add_special_tokens=False))


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in text.split("\n") if part.strip()]


def _overlap(parts: list[dict], token_counter: Callable[[str], int], overlap_tokens: int) -> list[dict]:
    kept, total = [], 0
    for part in reversed(parts):
        count = token_counter(part["text"])
        if kept and total + count > overlap_tokens:
            break
        kept.insert(0, part)
        total += count
    return kept


def _split_long_part(text: str, page: int, token_counter: Callable[[str], int], target_tokens: int) -> list[dict]:
    """Split only an oversize paragraph; token boundaries are always measured."""
    if token_counter(text) <= target_tokens:
        return [{"page": page, "text": text}]

    sentences = [part.strip() for part in re.split(r"(?<=[。！？；.!?])\s*", text) if part.strip()]
    units = sentences or [text]
    result: list[dict] = []
    for unit in units:
        if token_counter(unit) <= target_tokens:
            result.append({"page": page, "text": unit})
            continue
        current = ""
        for char in unit:
            proposed = current + char
            if current and token_counter(proposed) > target_tokens:
                result.append({"page": page, "text": current})
                current = char
            else:
                current = proposed
        if current:
            result.append({"page": page, "text": current})
    return result


def chunk_sections(
    document: dict,
    pages: list[dict],
    token_counter: Callable[[str], int],
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[dict]:
    """Chunk contiguous same-section paragraphs with true-token limits."""
    chunks, serial, group = [], 1, []

    def flush_group(section_pages: list[dict]) -> None:
        nonlocal serial
        if not section_pages:
            return
        section_path = section_pages[0].get("section_path") or f"第 {section_pages[0]['page']} 页"
        parts = []
        for source in section_pages:
            for paragraph in _paragraphs(source.get("text", "")):
                parts.extend(_split_long_part(paragraph, source["page"], token_counter, target_tokens))
        current: list[dict] = []
        for part in parts:
            proposed = "\n".join(item["text"] for item in current + [part])
            if current and token_counter(proposed) > target_tokens:
                chunks.append(_chunk(document, serial, section_path, current, token_counter("\n".join(item["text"] for item in current))))
                serial += 1
                overlap = _overlap(current, token_counter, overlap_tokens)
                while overlap and token_counter("\n".join(item["text"] for item in overlap + [part])) > target_tokens:
                    overlap.pop(0)
                current = overlap + [part]
            else:
                current.append(part)
        if current:
            text = "\n".join(item["text"] for item in current)
            chunks.append(_chunk(document, serial, section_path, current, token_counter(text)))
            serial += 1

    for page in pages:
        if group and page.get("section_path") != group[0].get("section_path"):
            flush_group(group)
            group = []
        group.append(page)
    flush_group(group)
    return chunks


def _chunk(document: dict, serial: int, section_path: str, parts: list[dict], token_count: int) -> dict:
    text = "\n".join(part["text"] for part in parts)
    page_start = min(part["page"] for part in parts)
    page_end = max(part["page"] for part in parts)
    return {
        "chunk_id": f"{document.get('chunk_prefix', document['id'])}-CHUNK-{serial:04d}",
        "document_id": document["id"],
        "document_name": document["name"],
        "vendor": document.get("vendor"),
        "product": document.get("product"),
        "section": section_path.split(" / ")[-1],
        "section_path": section_path,
        "page_start": page_start,
        "page_end": page_end,
        "token_count": token_count,
        "chunk_text": text,
        "text": text,
        "embedding_status": "Pending",
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
        "schema": 2,
        "embedding_model": EMBEDDING_MODEL,
        "tokenizer_model": EMBEDDING_MODEL,
        "chunking_strategy_version": "section-aware-v2",
        "target_tokens": TARGET_TOKENS,
        "overlap_tokens": OVERLAP_TOKENS,
        "sources": {entry["id"]: source_fingerprint(entry) for entry in discover_documents()},
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
        by_id = {entry["id"]: entry for entry in persisted if entry.get("id")}
        catalog_by_id = {entry["id"]: entry for entry in discover_documents()}
        records = []
        for document_id in dict.fromkeys([*by_id, *catalog_by_id]):
            catalog = catalog_by_id.get(document_id, {})
            stored = by_id.get(document_id, {})
            name = stored.get("name") or catalog.get("name")
            records.append(
                {
                    **catalog, **stored,
                    "pages": stored.get("pages"),
                    "chunks": stored.get("chunks", 0),
                    "status": stored.get("status", "Needs OCR"),
                    "parser": stored.get("parser", "未建立索引"),
                    "ocr": stored.get("ocr", "未执行"),
                    "chunk_strategy": stored.get("chunk_strategy", f"目录/段落切片，{TARGET_TOKENS} tokens，{OVERLAP_TOKENS} overlap"),
                    "updated_at": stored.get("updated_at", "待构建"),
                    "pdf_url": f"/documents/{name}" if name else None,
                    "source_fingerprint": stored.get("source_fingerprint"),
                }
            )
        return records

    def chunks(self, document_id: str | None = None) -> list[dict]:
        chunks = _read_json(self.index_dir / "chunks.json", [])
        return [item for item in chunks if document_id is None or item.get("document_id") == document_id]

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
            "tokenizer_model": manifest.get("tokenizer_model", EMBEDDING_MODEL),
            "vector_index": "FAISS IndexFlatIP (normalized cosine similarity)",
            "top_k": TOP_K,
            "chunk_target_tokens": manifest.get("target_tokens", TARGET_TOKENS),
            "chunk_overlap_tokens": manifest.get("overlap_tokens", OVERLAP_TOKENS),
        }
