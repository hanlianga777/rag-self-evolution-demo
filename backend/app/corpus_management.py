"""User initiated PDF changes; build a complete replacement index before activation."""

from __future__ import annotations
from .sqlite_support import open_database

import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import threading
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .build_index import build_index, _parse_document
from .full_text import CORPUS_LOCK, validate_bundle, write_full_text
from .corpus import DOCUMENTS_DIR, INDEX_DIR, UPLOADS_DIR, current_manifest, discover_documents, EMBEDDING_MODEL, tokenizer_token_count, write_checkpoint, write_checkpoint_json


def _known_operation_identity(index_dir, state):
    operation_id = state.get('operation_id')
    if not operation_id:
        return None
    path = index_dir.parent / 'corpus_operations' / f'{operation_id}.json'
    operation = json.loads(path.read_text())
    identity = state.get('knowledge_identity')
    if (operation.get('stage') not in {'activate', 'golden', 'completed'}
            or operation.get('request', {}).get('fingerprint') != state.get('fingerprint')
            or identity and identity.get('sources') != state.get('fingerprint')):
        raise ValueError('Corpus 状态与已保存操作不一致')
    return identity


def _switch_binding(database, record):
    """Read the committed Golden identity. Never restore an older database over it."""
    identities = [identity for key in ('new_identity', 'old_identity') if (identity := record.get(key))]
    with open_database(database, read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        run_id = 'GGEN-20261012120721324996'
        row = (connection.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?',
                                  (run_id,)).fetchone() if 'golden_generation_artifacts' in tables else None)
        if row is None and identities and 'schema_migrations' in tables:
            markers = {'experiment-reset-v1:' + str(identity.get('corpus_snapshot_id')): identity for identity in identities}
            current = record.get('old_identity' if record['phase'] == 'rolled_back' else 'new_identity') or {}
            preferred = 'experiment-reset-v1:' + str(current.get('corpus_snapshot_id'))
            names = ','.join('?' for _ in markers)
            reset = connection.execute(f'SELECT name FROM schema_migrations WHERE name IN ({names}) '
                                       'ORDER BY applied_at DESC, (name=?) DESC LIMIT 1', (*markers, preferred)).fetchone()
            if reset:
                return markers[reset[0]]
        audit = json.loads(row[0]) if row else {}
        expected = audit.get('corpus_fingerprint')
        if expected not in identities:
            raise ValueError('Corpus pointer/Golden binding inconsistent')
        plan_id = audit['frozen_plan']['plan_id']
        if expected == record.get('new_identity') and record['new_plan_id'] != plan_id:
            raise ValueError('Golden Plan binding inconsistent')
        row = connection.execute('SELECT question_ids_json FROM golden_generation_runs WHERE id=?', (run_id,)).fetchone()
        ids = json.loads(row[0]) if row else []
        plans = connection.execute("SELECT json_extract(raw_json,'$.plan_id') FROM questions WHERE id IN (" +
                                   ','.join('?' for _ in ids) + ')', ids).fetchall()
        if len(ids) != 50 or len(set(ids)) != 50 or len(plans) != 50 or any(p[0] != plan_id for p in plans):
            raise ValueError('Working set Plan bindings inconsistent')
        return expected


def require_consistent_switch(index_dir, database_path=None):
    """Read-only switch verification for the API and maintenance scripts."""
    index_dir = Path(index_dir)
    journal = index_dir.parent / 'q02-switch.json'
    state_path = index_dir.parent / 'corpus_state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if not isinstance(state, dict):
        raise ValueError('Corpus State JSON 不可用')
    expected = _known_operation_identity(index_dir, state)
    if expected is None and journal.exists():
        record = json.loads(journal.read_text())
        if not isinstance(record, dict):
            raise ValueError('Corpus 切换记录不可用')
        if record['phase'] not in ('completed', 'rolled_back'):
            raise ValueError('Incomplete Q02 switch: recovery required')
        expected = record['new_identity'] if record['phase'] == 'completed' else record['old_identity']
        database = Path(database_path or index_dir.parent / 'demo.db').resolve()
        if _switch_binding(database, record) != expected:
            raise ValueError('Corpus pointer/Golden binding inconsistent')
        if state.get('knowledge_identity') != expected and not (
                record['phase'] == 'rolled_back' and record.get('old_state') is None and not state_path.exists()):
            raise ValueError('Corpus State inconsistent')
    if expected is None and not journal.exists():
        expected = state.get('knowledge_identity')
    if expected is not None:
        actual = validate_bundle(index_dir, require_full_text=True)['manifest'].get('knowledge_identity')
        if actual != expected:
            raise ValueError('Corpus index identity inconsistent')


def _rebuild_faiss(directory, manifest):
    import faiss
    import numpy as np
    from .full_text import checksum

    artifact = directory / 'embeddings.npy'
    if artifact.is_file():
        chunks = json.loads((directory / 'chunks.json').read_text())
        vectors = np.load(artifact, allow_pickle=False)
        if (vectors.shape != (len(chunks), manifest['knowledge_config']['dimension'])
                or not np.isfinite(vectors).all()):
            raise ValueError('已保存切块与向量不匹配')
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(directory / 'faiss.index'))
        if checksum((directory / 'faiss.index').read_bytes()) != manifest['artifacts']['faiss.index']:
            raise ValueError('重建索引的校验值与原身份不一致')
    validate_bundle(directory, require_full_text=True)


ACTIVE_OPERATIONS = {"running", "recovering", "retry_wait"}


class CorpusManager:
    def __init__(self, retriever, *, index_dir=INDEX_DIR, documents_dir=DOCUMENTS_DIR, uploads_dir=UPLOADS_DIR, knowledge_pipeline=False, on_knowledge_activated=None):
        self.on_knowledge_activated = on_knowledge_activated
        self.knowledge_pipeline = knowledge_pipeline
        self.retriever = retriever
        self.index_dir = Path(index_dir)
        self.documents_dir = Path(documents_dir)
        self.uploads_dir = Path(uploads_dir)
        self.data_dir = self.index_dir.parent
        self._lock = threading.Lock()
        self._operations: dict[str, dict] = {}

    def repair_switch(self, database_path):
        """Rebuild and activate only a bundle matching the durable binding."""
        if not self._claim():
            return {'status': 'recovering', 'error': 'Corpus 操作正在恢复'}
        try:
            with CORPUS_LOCK:
                try:
                    require_consistent_switch(self.index_dir, database_path)
                    return {'status': 'ready', 'error': None}
                except (ValueError, OSError, RuntimeError, KeyError, sqlite3.Error):
                    pass
                state = self.state()
                expected = _known_operation_identity(self.index_dir, state)
                journal = self.data_dir / 'q02-switch.json'
                record = None
                if expected is None and journal.exists():
                    record = json.loads(journal.read_text())
                    if not isinstance(record, dict):
                        raise ValueError('Corpus 切换记录不可用')
                    expected = _switch_binding(Path(database_path).resolve(), record)
                if expected is None:
                    expected = state.get('knowledge_identity')
                if expected is None:
                    raise ValueError('没有可核验的 Corpus 身份')
                versions = self.data_dir / 'index_versions'
                versions.mkdir(exist_ok=True)
                prior_paths = [Path(record[key]) for key in ('old_archived_path', 'old_initial_path')
                               if record and record.get(key)]
                candidates = [self.index_dir, *prior_paths, *sorted(versions.iterdir())]
                failures = []
                for path in candidates:
                    try:
                        manifest = json.loads((path / 'manifest.json').read_text())
                    except (OSError, ValueError):
                        continue
                    if manifest.get('knowledge_identity') != expected:
                        continue
                    try:
                        with tempfile.TemporaryDirectory(prefix='repair-', dir=versions) as temporary:
                            staging = Path(temporary) / 'bundle'
                            shutil.copytree(path, staging, ignore=shutil.ignore_patterns('faiss.index')
                                            if (path / 'embeddings.npy').is_file() else None)
                            _rebuild_faiss(staging, manifest)
                            operation_id = 'REPAIR-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
                            self.activate_bundle(staging, operation_id)
                        break
                    except (ValueError, OSError, RuntimeError, KeyError) as error:
                        failures.append(str(error))
                else:
                    raise ValueError('找不到可重建的同身份切块和向量' + ('：' + '；'.join(failures) if failures else ''))
                if record:
                    phase = 'completed' if expected == record['new_identity'] else 'rolled_back'
                    state.pop('operation_id', None)
                    write_checkpoint_json(journal, {**record, 'phase': phase})
                write_checkpoint_json(self.data_dir / 'corpus_state.json', {**state, 'knowledge_identity': expected,
                                                                          'fingerprint': expected.get('sources', state.get('fingerprint'))})
                require_consistent_switch(self.index_dir, database_path)
                return {'status': 'repaired', 'error': None}
        except (ValueError, OSError, RuntimeError, KeyError, sqlite3.Error) as error:
            return {'status': 'blocked', 'error': str(error)}
        finally:
            self._release()

    def state(self) -> dict:
        path = self.data_dir / "corpus_state.json"
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def operation(self, operation_id: str) -> dict | None:
        value = self._operations.get(operation_id)
        if value is None:
            try:
                value = json.loads((self.data_dir / "corpus_operations" / f"{operation_id}.json").read_text())
            except (OSError, json.JSONDecodeError):
                return None
            if value['status'] in ACTIVE_OPERATIONS and value.get('kind') not in {'rebuild', 'upload', 'delete'}:
                value = {**value, 'status': 'interrupted', 'error': '服务重启后操作缺少可恢复的输入'}
        return {key: val for key, val in value.items() if key != 'request'}

    def _update(self, operation_id: str, **fields):
        value = {**self._operations[operation_id], **fields}
        path = self.data_dir / "corpus_operations" / f"{operation_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_checkpoint_json(path, value)
        self._operations[operation_id] = value

    def active(self):
        return self._lock.locked()

    def _claim(self):
        if not self._lock.acquire(blocking=False):
            return False
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._operation_lock = (self.data_dir / 'corpus-operation.lock').open('a')
            try:
                fcntl.flock(self._operation_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                self._operation_lock.close()
                raise
        except BlockingIOError:
            self._lock.release()
            return False
        except BaseException:
            self._lock.release()
            raise
        return True

    def _release(self):
        self._operation_lock.close()
        self._lock.release()

    def recover_pending(self):
        folder = self.data_dir / 'corpus_operations'
        if not folder.is_dir() or not self._claim():
            return False
        launched = False
        try:
            for path in sorted(folder.glob('*.json')):
                try:
                    value = json.loads(path.read_text())
                except (OSError, ValueError):
                    continue
                if value.get('status') not in ACTIVE_OPERATIONS or value.get('kind') not in {'rebuild', 'upload', 'delete'}:
                    continue
                operation_id = path.stem
                self._operations[operation_id] = value
                self._update(operation_id, status='recovering', error=None, resumed_at=datetime.now(timezone.utc).isoformat())
                threading.Thread(target=self._run, args=(operation_id,), daemon=True).start()
                launched = True
                return True
            return False
        finally:
            if not launched:
                self._release()

    def start(self, kind: str, *, filename: str | None = None, data: bytes | None = None, document_id: str | None = None) -> dict:
        if self.recover_pending() or not self._claim():
            raise ValueError("另一个 Corpus 操作正在执行")
        operation_id = "CORP-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        try:
            if kind == 'upload':
                if not filename or Path(filename).name != filename or not filename.lower().endswith('.pdf'):
                    raise ValueError('PDF 文件名无效')
                if not data or not data.startswith(b'%PDF-') or len(data) > 50 * 1024 * 1024:
                    raise ValueError('需要不超过 50 MB 的有效 PDF')
                pending = self.data_dir / "pending_uploads" / operation_id
                pending.mkdir(parents=True)
                write_checkpoint(pending / filename, data)
            self._operations[operation_id] = {"id": operation_id, "kind": kind, "status": "running", "stage": "queued",
                                              "completed": 0, "total": 0, "error": None,
                                              "request": {"filename": filename, "document_id": document_id}}
            self._update(operation_id)
            threading.Thread(target=self._run, args=(operation_id,), daemon=True).start()
        except BaseException:
            self._release()
            raise
        return self.operation(operation_id)

    def _build_request(self, operation, pending):
        kind = operation['kind']
        args = operation.get('request') or {}
        sources = discover_documents()
        moved_from = moved_to = None
        if kind == 'upload':
            pdfs = list(pending.glob('*.pdf'))
            name = args.get('filename') or (pdfs[0].name if len(pdfs) == 1 else None)
            if not name or not (pending / name).is_file() or any(doc['name'] == name for doc in sources):
                raise ValueError('上传 PDF 缺失或文件名已存在')
            moved_from, moved_to = pending / name, self.uploads_dir / name
            identifier = 'DOC-' + hashlib.sha256(name.encode()).hexdigest()[:12]
            sources.append({'id': identifier, 'name': name, 'chunk_prefix': identifier, 'storage': 'uploads',
                            '_source_path': str(moved_from)})
        elif kind == 'delete':
            source = next((doc for doc in sources if doc['id'] == args.get('document_id')), None)
            if source is None:
                raise ValueError('找不到要删除的 Corpus 文档，旧操作可能未保存文档 ID')
            sources.remove(source)
            moved_from = (self.uploads_dir if source.get('storage') == 'uploads' else self.documents_dir) / source['name']
            moved_to = self.data_dir / 'archived_documents' / f"{operation['id']}-{source['name']}"
        elif kind != 'rebuild':
            raise ValueError('未知 Corpus 操作')
        return {**args, 'sources': sources, 'fingerprint': current_manifest(sources)['sources'],
                'move': [str(moved_from), str(moved_to)] if moved_from else None}

    def _run(self, operation_id: str):
        operation = self._operations[operation_id]
        kind = operation['kind']
        stage = 'validate'
        versions = self.data_dir / 'index_versions'
        staging = versions / f'{operation_id}-building'
        ready = versions / operation_id
        pending = self.data_dir / 'pending_uploads' / operation_id
        moved_from = moved_to = None
        switched = False
        new_pipeline = self.knowledge_pipeline or kind == 'rebuild'
        try:
            request = operation.get('request') or {}
            if 'sources' not in request:
                request = self._build_request(operation, pending)
                self._update(operation_id, request=request)
            sources = request['sources']
            if request['move']:
                moved_from, moved_to = map(Path, request['move'])
            if new_pipeline:
                from .knowledge_pipeline import ACTIVE_CHUNK_VERSION, CachedMinerUParser, KnowledgePipeline, MinerUProvider, settings as pipeline_settings
                pipeline = KnowledgePipeline(self.index_dir, self.retriever)
            activation_pending = operation['stage'] in {'activate', 'golden'}
            if not activation_pending:
                if current_manifest(sources)['sources'] != request['fingerprint']:
                    raise ValueError('源 PDF 已变化，无法继续原来的 Corpus 操作')
                stage = 'build'
                self._update(operation_id, stage=stage)
                def progress(step, completed, total):
                    self._update(operation_id, stage=step, completed=completed, total=total)
                def document(doc_id, name, status, phase, error):
                    docs = {**self._operations[operation_id].get('documents', {}),
                            doc_id: {'name': name, 'status': status, 'stage': phase, 'error': error}}
                    active = 'retry_wait' if any(doc['status'] == 'retry_wait' for doc in docs.values()) else operation['status']
                    self._update(operation_id, status=active, documents=docs)
                if new_pipeline:
                    parser = CachedMinerUParser(self.index_dir, lambda: MinerUProvider(pipeline_settings()))
                    staging, _ = pipeline.build(sources, progress=progress, chunk_version=ACTIVE_CHUNK_VERSION, parser=parser,
                                                operation_id=operation_id, on_document=document)
                    self._update(operation_id, mineru_cache={'reused': parser.hits, 'parsed': parser.misses},
                                 chunk_version=ACTIVE_CHUNK_VERSION)
                else:
                    shutil.rmtree(staging, ignore_errors=True)
                    result = build_index(force=True, catalog=sources, index_dir=staging, strict=True, on_progress=progress)
                    if result:
                        records = json.loads((staging / 'documents.json').read_text()) if (staging / 'documents.json').exists() else []
                        failed = [f"{item['name']}: {item.get('error') or item['status']}" for item in records if item['status'] != 'Indexed']
                        raise ValueError('；'.join(failed) or '索引构建失败')
            stage = 'activate'
            switched = self.index_dir.resolve() == ready.resolve()
            with CORPUS_LOCK:
                if not activation_pending:
                    old_manifest = self.index_dir / 'manifest.json'
                    if new_pipeline and old_manifest.exists() and not json.loads(old_manifest.read_text()).get('knowledge_identity'):
                        legacy = self.index_dir.resolve() if self.index_dir.is_symlink() else versions / f'{operation_id}-previous'
                        request = {**request, 'legacy_path': str(legacy)}
                self._update(operation_id, stage=stage, request=request)
                if not switched and ready.is_dir() and not staging.exists():
                    os.replace(ready, staging)
                bundle = validate_bundle(ready if switched else staging, require_full_text=True)
                if bundle['manifest']['sources'] != request['fingerprint']:
                    raise ValueError('构建产物的源文件身份与原操作不一致')
                if activation_pending and not switched:
                    current_sources = sources
                    if kind == 'upload' and not moved_from.exists():
                        current_sources = [{**doc, '_source_path': str(moved_to)}
                                           if doc.get('_source_path') == str(moved_from) else doc for doc in sources]
                    if current_manifest(current_sources)['sources'] != request['fingerprint']:
                        raise ValueError('源 PDF 已变化，无法切换原来的 Corpus')
                if moved_to:
                    if moved_from.exists():
                        moved_to.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(moved_from, moved_to)
                    elif not moved_to.exists():
                        raise ValueError('待切换的原始 PDF 文件缺失')
                def finish():
                    if request.get('legacy_path') and not (self.data_dir / 'legacy_index.json').exists():
                        write_checkpoint_json(self.data_dir / 'legacy_index.json', {'path': request['legacy_path']})
                    identity = bundle['manifest'].get('knowledge_identity')
                    state = {'changed_at': datetime.now(timezone.utc).isoformat(), 'fingerprint': bundle['manifest']['sources'],
                             'knowledge_identity': identity, 'operation_id': operation_id}
                    write_checkpoint_json(self.data_dir / 'corpus_state.json', state)
                    self._update(operation_id, stage='golden')
                if switched:
                    finish()
                elif new_pipeline:
                    pipeline.activate(staging, operation_id, after_activate=finish)
                else:
                    self.activate_bundle(staging, operation_id, after_activate=finish)
                switched = True
            if new_pipeline and self.on_knowledge_activated:
                try:
                    run_id = self.on_knowledge_activated(operation_id)
                    self._update(operation_id, golden_generation_run_id=run_id)
                except Exception as error:
                    self._update(operation_id, golden_error=str(error))
            self._update(operation_id, status='completed', stage='completed', completed=1, total=1)
        except Exception as error:
            if stage == 'activate' and not switched and moved_to and moved_to.exists() and not moved_from.exists():
                moved_from.parent.mkdir(parents=True, exist_ok=True)
                os.replace(moved_to, moved_from)
            docs = self._operations[operation_id].get('documents', {})
            self._update(operation_id, status='failed', stage=self._operations[operation_id]['stage'] if stage == 'build' else stage,
                         error=str(error), failed_documents=[{'id': doc_id, **doc} for doc_id, doc in docs.items() if doc['status'] == 'failed'])
        finally:
            if not new_pipeline:
                shutil.rmtree(staging, ignore_errors=True)
            if self._operations[operation_id]['status'] in {'completed', 'failed'}:
                shutil.rmtree(pending, ignore_errors=True)
            if self._operations[operation_id]['status'] == 'completed':
                shutil.rmtree(versions / f'{operation_id}-checkpoints', ignore_errors=True)
            self._release()

    def _invalidate(self):
        if self.retriever is None:
            return
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
                pointer.unlink(missing_ok=True)
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
        if not self._claim():
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
            self._release()
