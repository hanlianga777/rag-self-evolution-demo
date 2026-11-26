"""Restart the real Corpus worker against fake HTTP and embedding providers."""
import io
import json
import os
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pymupdf
import pytest

from app import knowledge_pipeline as kp
from app.full_text import validate_bundle


def worker(root, fault):
    from fastapi.testclient import TestClient
    from app.main import app

    def event(value):
        with (root / 'calls').open('a') as handle:
            handle.write(value + '\n')

    def crash(when):
        if when == fault:
            os.kill(os.getpid(), signal.SIGKILL)

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('content_list.json', json.dumps([
            {'type': 'text', 'text': '维护设备前先隔离电源并确认设备完全停止。' * 240, 'page_idx': 0},
        ]))

    def mineru_request(self, path, payload=None):
        if payload:
            doc = payload['files'][0]['data_id']
            event('create:' + doc)
            return {'batch_id': doc, 'file_urls': ['https://fixture.invalid/' + doc]}
        doc = path.rsplit('/', 1)[-1]
        event('poll:' + doc)
        crash('poll')
        return {'extract_result': [{'state': 'done', 'full_zip_url': 'https://fixture.invalid/result'}]}

    def upload(request, **_):
        event('upload:' + request.full_url.rsplit('/', 1)[-1])
        return io.BytesIO()

    class Embedder:
        batches = 0

        def embed(self, texts, dimension):
            self.batches += 1
            if self.batches == 2:
                crash('embedding')
            from hashlib import sha256
            event('embedding:' + sha256(json.dumps(texts).encode()).hexdigest())
            return np.tile(np.arange(1, dimension + 1, dtype=np.float32), (len(texts), 1))

    build = kp.KnowledgePipeline.build

    def fake_build(self, sources, **kwargs):
        return build(self, sources, {}, counter=len, embedder=Embedder(), **kwargs)

    saved = list((root / 'corpus_operations').glob('*.json'))
    with patch.object(kp.MinerUProvider, '_request', mineru_request), \
         patch.object(kp.urllib.request, 'urlopen', upload), \
         patch.object(kp, 'download_mineru_result', return_value=archive.getvalue()), \
         patch.object(kp.KnowledgePipeline, 'build', fake_build), TestClient(app) as client:
        if saved:
            operation_id = saved[0].stem
        else:
            response = client.post('/api/knowledge/rebuild', headers={'Origin': 'http://127.0.0.1:5174'})
            assert response.status_code == 202, response.text
            operation_id = response.json()['id']
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            operation = client.get(f'/api/corpus-operations/{operation_id}').json()
            if operation['status'] in {'completed', 'failed', 'interrupted'}:
                if operation['status'] != 'completed':
                    raise AssertionError(operation)
                return
            time.sleep(.02)
        raise AssertionError(operation)


def run_worker(root, fault=''):
    env = {**os.environ, 'RAG_DEMO_INDEX_DIR': str(root / 'index'),
           'RAG_DEMO_DOCUMENTS_DIR': str(root / 'documents'), 'RAG_DEMO_UPLOADS_DIR': str(root / 'uploads'),
           'RAG_DEMO_DB_PATH': str(root / 'demo.db'), 'RAG_DEMO_ENV_PATH': str(root / 'absent.env'),
           'RAG_SAFE_START': '0', 'RAG_FORCE_MOCK': '0', 'RAG_SKIP_AUTO_GOLDEN': '1'}
    return subprocess.run([sys.executable, __file__, str(root), fault], env=env, capture_output=True, text=True, timeout=25)


def source(root):
    folder = root / 'documents'
    folder.mkdir(parents=True)
    pdf = pymupdf.open()
    pdf.new_page()
    pdf.save(folder / 'fixture.pdf')
    pdf.close()


@pytest.mark.parametrize('fault', ['poll', 'embedding'])
def test_killed_corpus_operation_matches_clean_build(tmp_path, fault):
    clean = tmp_path / 'clean'
    source(clean)
    resumed = tmp_path / 'resumed'
    (resumed / 'documents').mkdir(parents=True)
    (resumed / 'documents' / 'fixture.pdf').write_bytes((clean / 'documents' / 'fixture.pdf').read_bytes())

    first = run_worker(resumed, fault)
    assert first.returncode == -signal.SIGKILL, first.stderr
    before = (resumed / 'calls').read_text().splitlines()
    assert any(line.startswith('embedding:') for line in before) == (fault == 'embedding')
    for root in (clean, resumed):
        done = run_worker(root)
        assert done.returncode == 0, done.stderr

    operation = next((resumed / 'corpus_operations').glob('*.json'))
    assert json.loads(operation.read_text())['resumed_at']
    baseline = validate_bundle(clean / 'index')
    recovered = validate_bundle(resumed / 'index')
    assert recovered['manifest']['knowledge_identity'] == baseline['manifest']['knowledge_identity']
    assert recovered['chunks'] == baseline['chunks']
    assert recovered['documents'] == baseline['documents']
    assert recovered['full_text'] == baseline['full_text']
    assert recovered['manifest']['coverage_plan_id'] == baseline['manifest']['coverage_plan_id']
    np.testing.assert_array_equal(np.load(clean / 'index' / 'embeddings.npy'), np.load(resumed / 'index' / 'embeddings.npy'))
    clean_calls = (clean / 'calls').read_text().splitlines()
    resumed_calls = (resumed / 'calls').read_text().splitlines()
    assert [v for v in clean_calls if not v.startswith('poll:')] == [v for v in resumed_calls if not v.startswith('poll:')]


def test_mineru_retries_transient_upload_poll_and_download_on_the_same_batch(tmp_path):
    import ssl
    from collections import Counter

    source(tmp_path)
    pdf = tmp_path / 'documents' / 'fixture.pdf'
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('content_list.json', '[]')
    counts = Counter()

    def transient(stage, result):
        counts[stage] += 1
        if counts[stage] == 1:
            raise ssl.SSLEOFError(stage)
        return result

    def request(path, payload=None):
        if payload:
            counts['create'] += 1
            return {'batch_id': 'original', 'file_urls': ['https://fixture.invalid/upload']}
        assert path == 'extract-results/batch/original'
        return transient('poll', {'extract_result': [{'state': 'done', 'full_zip_url': 'https://fixture.invalid/result'}]})

    parser = kp.MinerUProvider({})
    with patch.object(parser, '_request', side_effect=request), \
         patch.object(kp.urllib.request, 'urlopen', side_effect=lambda *a, **kw: transient('upload', io.BytesIO())), \
         patch.object(kp, 'download_mineru_result', side_effect=lambda *_: transient('download', archive.getvalue())), \
         patch('app.providers._retry_sleep'):
        assert parser.parse(pdf, 'doc', checkpoint=tmp_path / 'mineru.json') == ([], archive.getvalue())
    assert counts == {'create': 1, 'upload': 2, 'poll': 2, 'download': 2}
    assert json.loads((tmp_path / 'mineru.json').read_text())['batch_id'] == 'original'


@pytest.mark.parametrize('persistent', [False, True])
def test_failed_document_is_retried_after_other_documents(tmp_path, persistent):
    source(tmp_path)
    path = tmp_path / 'documents' / 'fixture.pdf'
    documents = [{'id': key, 'name': key + '.pdf', '_source_path': str(path)} for key in ('first', 'second')]
    seen, statuses = [], []

    class Parser:
        def parse(self, _path, key):
            seen.append(key)
            if key == 'first' and (persistent or seen.count(key) == 1):
                raise TimeoutError('fake document failed')
            return [{'type': 'text', 'text': f'{key} 维护设备前先隔离电源并确认设备完全停止。' * 20, 'page_idx': 0}], b'fixture'

    class Embedder:
        def embed(self, texts, dimension):
            return np.ones((len(texts), dimension), dtype=np.float32)

    active = tmp_path / 'index'
    pipeline = kp.KnowledgePipeline(active, None)
    def build():
        return pipeline.build(documents, {}, counter=len, parser=Parser(), embedder=Embedder(),
                              on_document=lambda key, name, state, phase, error: statuses.append((key, state)))

    if persistent:
        with pytest.raises(ValueError, match='first.pdf'):
            build()
        assert statuses[-2:] == [('first', 'failed'), ('second', 'completed')]
        assert not active.exists()
    else:
        stage, _ = build()
        assert len(validate_bundle(stage)['documents']) == 2
    assert seen == ['first', 'second', 'first']
    assert statuses[:2] == [('first', 'retry_wait'), ('second', 'completed')]


def test_switch_rebuilds_the_database_bound_index_from_saved_artifacts(tmp_path):
    import sqlite3
    from app.corpus_management import CorpusManager, require_consistent_switch

    correct = tmp_path / 'correct'
    source(correct)
    result = run_worker(correct)
    assert result.returncode == 0, result.stderr
    bundle = validate_bundle(correct / 'index')
    identity = bundle['manifest']['knowledge_identity']
    original_faiss = (correct / 'index' / 'faiss.index').read_bytes()
    (correct / 'index' / 'faiss.index').unlink()

    other = tmp_path / 'other'
    source(other)
    result = run_worker(other)
    assert result.returncode == 0, result.stderr
    assert validate_bundle(other / 'index')['manifest']['knowledge_identity'] != identity
    (correct / 'index').unlink()
    (correct / 'index').symlink_to((other / 'index').resolve())
    database = correct / 'demo.db'
    with sqlite3.connect(database) as db:
        db.execute('INSERT INTO schema_migrations (name,applied_at) VALUES (?,?)',
                   ('experiment-reset-v1:' + identity['corpus_snapshot_id'], 'fixture'))
    state_path = correct / 'corpus_state.json'
    state = json.loads(state_path.read_text())
    del state['operation_id']
    state_path.write_text(json.dumps(state))
    (correct / 'q02-switch.json').write_text(json.dumps({'phase': 'completed', 'new_identity': identity}))
    with pytest.raises(ValueError):
        require_consistent_switch(correct / 'index', database)

    result = CorpusManager(None, index_dir=correct / 'index').repair_switch(database)
    assert result['status'] == 'repaired'
    require_consistent_switch(correct / 'index', database)
    assert (correct / 'index' / 'faiss.index').read_bytes() == original_faiss
    assert database.is_file()


if __name__ == '__main__':
    worker(Path(sys.argv[1]), sys.argv[2])
