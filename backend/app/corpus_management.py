"""User initiated PDF changes; build a complete replacement index before activation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from .build_index import build_index
from .corpus import DOCUMENTS_DIR, INDEX_DIR, UPLOADS_DIR, current_manifest, discover_documents


class CorpusManager:
    def __init__(self, retriever, *, index_dir=INDEX_DIR, documents_dir=DOCUMENTS_DIR, uploads_dir=UPLOADS_DIR):
        self.retriever = retriever
        self.index_dir = Path(index_dir)
        self.documents_dir = Path(documents_dir)
        self.uploads_dir = Path(uploads_dir)
        self.data_dir = self.index_dir.parent
        self._lock = threading.Lock()
        self._operations: dict[str, dict] = {}

    def state(self) -> dict:
        path = self.data_dir / "corpus_state.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def operation(self, operation_id: str) -> dict | None:
        if operation_id in self._operations:
            return self._operations[operation_id]
        try:
            value = json.loads((self.data_dir / "corpus_operations" / f"{operation_id}.json").read_text(encoding="utf-8"))
            return {**value, "status": "interrupted", "error": "服务重启后操作中断，请检查当前 Corpus"} if value["status"] == "running" else value
        except (OSError, json.JSONDecodeError):
            return None

    def _update(self, operation_id: str, **fields):
        value = {**self._operations[operation_id], **fields}
        self._operations[operation_id] = value
        path = self.data_dir / "corpus_operations" / f"{operation_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def start(self, kind: str, *, filename: str | None = None, data: bytes | None = None, document_id: str | None = None) -> dict:
        if not self._lock.acquire(blocking=False):
            raise ValueError("另一个 Corpus 操作正在执行")
        operation_id = "CORP-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        self._operations[operation_id] = {"id": operation_id, "kind": kind, "status": "running", "stage": "queued", "completed": 0, "total": 0, "error": None}
        self._update(operation_id)
        threading.Thread(target=self._run, args=(operation_id, kind, filename, data, document_id), daemon=True).start()
        return self._operations[operation_id]

    def _run(self, operation_id: str, kind: str, filename: str | None, data: bytes | None, document_id: str | None):
        stage = "validate"
        staging = self.data_dir / "index_versions" / f"{operation_id}-building"
        pending = self.data_dir / "pending_uploads" / operation_id
        moved_from = moved_to = prior = None
        activated = False
        try:
            self._update(operation_id, stage=stage)
            sources = discover_documents()
            if kind == "upload":
                if not filename or not data or not data.startswith(b"%PDF-") or len(data) > 50 * 1024 * 1024:
                    raise ValueError("需要不超过 50 MB 的有效 PDF")
                name = Path(filename).name
                if name != filename or not name.lower().endswith(".pdf") or any(item["name"] == name for item in sources):
                    raise ValueError("PDF 文件名无效或已存在")
                pending.mkdir(parents=True, exist_ok=True)
                candidate = pending / name
                candidate.write_bytes(data)
                identifier = "DOC-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
                sources.append({"id": identifier, "name": name, "chunk_prefix": identifier, "storage": "uploads", "_source_path": str(candidate)})
                moved_from, moved_to = candidate, self.uploads_dir / name
            elif kind == "delete":
                source = next((item for item in sources if item["id"] == document_id), None)
                if source is None:
                    raise ValueError("文档不在当前 Corpus")
                sources = [item for item in sources if item["id"] != document_id]
                moved_from = (self.uploads_dir if source.get("storage") == "uploads" else self.documents_dir) / source["name"]
                moved_to = self.data_dir / "archived_documents" / f"{operation_id}-{source['name']}"
            else:
                raise ValueError("未知 Corpus 操作")
            stage = "build"
            self._update(operation_id, stage=stage)
            result = build_index(force=True, catalog=sources, index_dir=staging, strict=True, on_progress=lambda step, completed, total: self._update(operation_id, stage=step, completed=completed, total=total))
            if result:
                records = json.loads((staging / "documents.json").read_text()) if (staging / "documents.json").exists() else []
                failed = [f"{item['name']}: {item.get('error') or item['status']}" for item in records if item["status"] != "Indexed"]
                if failed:
                    self._update(operation_id, stage="embedding" if any(item["status"] == "Embedding Failed" for item in records) else "parse")
                raise ValueError("；".join(failed) or "索引构建失败")
            stage = "activate"
            self._update(operation_id, stage=stage)
            moved_to.parent.mkdir(parents=True, exist_ok=True)
            os.replace(moved_from, moved_to)
            versions = self.data_dir / "index_versions"
            versions.mkdir(parents=True, exist_ok=True)
            if self.index_dir.exists() and not self.index_dir.is_symlink():
                prior = versions / f"{operation_id}-previous"
                os.replace(self.index_dir, prior)
                self.index_dir.symlink_to(prior, target_is_directory=True)
            elif self.index_dir.is_symlink():
                prior = self.index_dir.resolve()
            ready = versions / operation_id
            os.replace(staging, ready)
            pointer = versions / f"{operation_id}.link"
            pointer.symlink_to(ready, target_is_directory=True)
            os.replace(pointer, self.index_dir)
            activated = True
            self.retriever._index = None
            self.retriever._model = None
            state = {"changed_at": datetime.now(timezone.utc).isoformat(), "fingerprint": current_manifest()["sources"]}
            (self.data_dir / "corpus_state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            self._update(operation_id, status="completed", stage="completed", completed=1, total=1)
            if prior and prior.exists():
                shutil.rmtree(prior, ignore_errors=True)
        except Exception as error:
            if activated and prior and prior.exists():
                pointer = self.data_dir / "index_versions" / f"{operation_id}.rollback"
                pointer.symlink_to(prior, target_is_directory=True)
                os.replace(pointer, self.index_dir)
            if stage == "activate" and moved_from and moved_to and moved_to.exists() and not moved_from.exists():
                moved_from.parent.mkdir(parents=True, exist_ok=True)
                os.replace(moved_to, moved_from)
            self._update(operation_id, status="failed", stage=self._operations[operation_id]["stage"] if stage == "build" else stage, error=str(error))
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            shutil.rmtree(pending, ignore_errors=True)
            self._lock.release()
