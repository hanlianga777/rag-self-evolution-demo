"""User initiated PDF changes; build a complete replacement index before activation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from .build_index import build_index, _parse_document
from .full_text import CORPUS_LOCK, validate_bundle, write_full_text
from .corpus import DOCUMENTS_DIR, INDEX_DIR, UPLOADS_DIR, current_manifest, discover_documents, EMBEDDING_MODEL, tokenizer_token_count


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
        moved_from = moved_to = None
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
            validate_bundle(staging, require_full_text=True)
            with CORPUS_LOCK:
                moved_to.parent.mkdir(parents=True, exist_ok=True)
                os.replace(moved_from, moved_to)
                def finish():
                    state = {"changed_at": datetime.now(timezone.utc).isoformat(), "fingerprint": current_manifest()["sources"]}
                    (self.data_dir / "corpus_state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                    self._update(operation_id, status="completed", stage="completed", completed=1, total=1)
                self.activate_bundle(staging, operation_id, after_activate=finish)
        except Exception as error:
            if stage == "activate" and moved_from and moved_to and moved_to.exists() and not moved_from.exists():
                moved_from.parent.mkdir(parents=True, exist_ok=True)
                os.replace(moved_to, moved_from)
            self._update(operation_id, status="failed", stage=self._operations[operation_id]["stage"] if stage == "build" else stage, error=str(error))
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            shutil.rmtree(pending, ignore_errors=True)
            self._lock.release()

    def _invalidate(self):
        if hasattr(self.retriever, 'invalidate'):
            self.retriever.invalidate()
        else:
            self.retriever._index = None
            self.retriever._model = None

    def activate_bundle(self, staging, operation_id, *, after_activate=None, expected_active=None):
        """Validate before swapping; preserve the complete prior bundle on success and rollback."""
        staging = Path(staging)
        with CORPUS_LOCK:
            validate_bundle(staging, require_full_text=True)
            if expected_active is not None and self.index_dir.resolve() != expected_active:
                raise ValueError('Active Corpus changed during full-text supplementation')
            versions = self.data_dir / 'index_versions'
            versions.mkdir(parents=True, exist_ok=True)
            prior = self.index_dir.resolve() if self.index_dir.is_symlink() else None
            ready = versions / operation_id
            pointer = versions / f'{operation_id}.link'
            switched = False
            old_state = (self.data_dir / 'corpus_state.json').read_bytes() if (self.data_dir / 'corpus_state.json').exists() else None
            try:
                if self.index_dir.exists() and not self.index_dir.is_symlink():
                    prior = versions / f'{operation_id}-previous'
                    os.replace(self.index_dir, prior)
                    self.index_dir.symlink_to(prior, target_is_directory=True)
                os.replace(staging, ready)
                pointer.symlink_to(ready, target_is_directory=True)
                os.replace(pointer, self.index_dir)
                switched = True
                self._invalidate()
                if after_activate:
                    after_activate()
            except Exception:
                if prior and prior.exists():
                    rollback = versions / f'{operation_id}.rollback'
                    rollback.symlink_to(prior, target_is_directory=True)
                    os.replace(rollback, self.index_dir)
                elif switched:
                    self.index_dir.unlink(missing_ok=True)
                self._invalidate()
                state_path = self.data_dir / 'corpus_state.json'
                if old_state is None:
                    state_path.unlink(missing_ok=True)
                else:
                    state_path.write_bytes(old_state)
                raise
            finally:
                pointer.unlink(missing_ok=True)
            return {'active_bundle': str(ready), 'previous_bundle': str(prior) if prior else None}

    def supplement_full_text(self, *, activate=False, parser=None, ocr=None, token_counter=None):
        """Reparse with the existing parser, require exact chunks, copy unchanged vectors/documents."""
        if not self._lock.acquire(blocking=False):
            raise ValueError('另一个 Corpus 操作正在执行')
        operation_id = 'FULLTEXT-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        staging = self.data_dir / 'index_versions' / f'{operation_id}-building'
        self._operations[operation_id] = {'id': operation_id, 'kind': 'full_text_supplement', 'status': 'running', 'stage': 'parse', 'staging': str(staging)}
        self._update(operation_id)
        try:
            with CORPUS_LOCK:
                active = self.index_dir.resolve()
                original = validate_bundle(active)
                shutil.copytree(active, staging)
            sources = discover_documents()
            if current_manifest(sources)['sources'] != original['manifest']['sources']:
                raise ValueError('Source content differs from indexed Corpus; refusing supplementation')
            if parser is None:
                from rapidocr import RapidOCR
                from transformers import AutoTokenizer
                ocr = RapidOCR()
                tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL, local_files_only=True)
                token_counter = lambda text: tokenizer_token_count(tokenizer, text)
                parser = _parse_document
            pages, regenerated, records = [], [], []
            for source in sources:
                record, chunks = parser(source, ocr, token_counter, full_text_pages=pages)
                if record['status'] != 'Parsed':
                    raise ValueError(f"Parser failed for {source['id']}: {record.get('error') or record['status']}")
                records.append(record)
                regenerated.extend(chunks)
            def stable(chunks):
                # Parser traversal may differ; copied chunks and vectors keep their original order.
                by_id = {chunk.get('chunk_id'): {key: value for key, value in chunk.items() if key != 'embedding_status'} for chunk in chunks}
                if None in by_id or len(by_id) != len(chunks):
                    raise ValueError('Regenerated Chunk identity contains missing or duplicate IDs; original active Corpus preserved')
                return by_id
            if stable(regenerated) != stable(original['chunks']):
                raise ValueError('Regenerated Chunk identity/content differs; original active Corpus preserved')
            old_docs = {doc['id']: doc for doc in original['documents']}
            if any(record['source_fingerprint'] != old_docs[record['id']].get('source_fingerprint') or record['pages'] != old_docs[record['id']].get('pages') or record['name'] != old_docs[record['id']]['name'] for record in records):
                raise ValueError('Regenerated document identity differs')
            if current_manifest(sources)['sources'] != original['manifest']['sources']:
                raise ValueError('Source changed during parsing')
            write_full_text(staging, original['manifest'], original['documents'], pages)
            validate_bundle(staging, require_full_text=True)
            result = {'staging': str(staging), 'corpus_fingerprint': original['manifest']['sources'], 'artifact_schema_version': 3, 'content_compatible': True}
            if activate:
                with CORPUS_LOCK:
                    previous = active if self.index_dir.is_symlink() else self.data_dir / 'index_versions' / f'{operation_id}-previous'
                    result.update(active_bundle=str(self.data_dir / 'index_versions' / operation_id), previous_bundle=str(previous))
                    self.activate_bundle(staging, operation_id, expected_active=active,
                                         after_activate=lambda: self._update(operation_id, status='completed', stage='completed', result=result))
            else:
                self._update(operation_id, status='staged', stage='completed', result=result)
            return self._operations[operation_id]
        except Exception as error:
            self._update(operation_id, status='failed', error=str(error))
            raise
        finally:
            self._lock.release()
