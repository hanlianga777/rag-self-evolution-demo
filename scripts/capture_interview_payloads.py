#!/usr/bin/env python3
"""Capture current GET responses from a disposable copy of the saved real Demo.

Never start lifespan, contact Provider, execute Preview, or mutate real storage.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from test_v14_offline import isolated_corpus
import socket
import sys
import tempfile
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'output/playwright/interview-demo/browser'


def fingerprint(path):
    stat = path.stat()
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def block_tcp(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError('Interview capture prohibits all TCP; TestClient is in-process')
    return original_connect(self, address)


def block_tcp_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError('Interview capture prohibits all TCP; TestClient is in-process')
    return original_connect_ex(self, address)


original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, default=ROOT / 'backend/data/interview-demo-before-20261003.bak')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    assert args.backup.is_file(), 'Saved real backup required; never initialize a blank DB'
    args.output.mkdir(parents=True, exist_ok=True)
    resources = args.output / 'resources'; resources.mkdir(exist_ok=True)
    protected = [args.backup, ROOT / 'backend/data/demo.db', ROOT / 'backend/data/corpus_state.json']
    protected += [path for path in (ROOT / 'backend/data/index').rglob('*') if path.is_file()]
    protected = [path for path in protected if path.is_file()]
    before = {str(path): fingerprint(path) for path in protected}
    responses = {}
    with tempfile.TemporaryDirectory(prefix='rag-interview-capture-', dir='/private/tmp') as temp:
        copy = Path(temp) / 'demo-copy.db'
        with sqlite3.connect(args.backup.resolve().as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(copy) as destination:
            source.backup(destination)
        environment = {'RAG_DEMO_DB_PATH': str(copy), 'RAG_FORCE_MOCK': '1', 'DEEPSEEK_API_KEY': '', 'DASHSCOPE_API_KEY': '', 'MINERU_API_KEY': '', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
        sys.path.insert(0, str(ROOT / 'backend'))
        with patch.dict(os.environ, environment), patch.object(socket.socket, 'connect', block_tcp), patch.object(socket.socket, 'connect_ex', block_tcp_ex), isolated_corpus(temp) as isolated_paths:
            assert os.environ['RAG_DEMO_DB_PATH'] == str(copy) and copy.is_file()
            from fastapi.testclient import TestClient
            from app import main as api
            for route in api.app.routes:
                if getattr(route, 'path', None) == '/documents':
                    route.app.directory = str(isolated_paths['DOCUMENTS_DIR'])
                    route.app.all_directories = [str(isolated_paths['DOCUMENTS_DIR'])]
            assert api.corpus.index_dir == isolated_paths['INDEX_DIR']
            assert api.corpus_manager.index_dir == isolated_paths['INDEX_DIR']
            assert api.store.database_path == copy, 'Import must bind only the disposable DB'
            assert not api.ai_service.provider.settings.api_key
            client = TestClient(api.app)  # Deliberately no context manager/lifespan/startup.

            def capture(url, allow_read_error=False):
                path = urlsplit(url).path
                response = client.get(url)
                assert response.status_code == 200 or allow_read_error and response.status_code in (404, 409), f'GET {url}: {response.status_code} {response.text[:180]}'
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    value = response.json()
                    responses[path] = {'kind': 'json', 'body': value, 'status': response.status_code, 'content_type': content_type}
                    return value
                file = resources / (hashlib.sha256(path.encode()).hexdigest()[:16] + '.bin')
                file.write_bytes(response.content)
                responses[path] = {'kind': 'file', 'file': str(file.relative_to(args.output)), 'content_type': content_type, 'sha256': hashlib.sha256(response.content).hexdigest()}

            for path in ['/api/workspace', '/api/overview', '/api/documents', '/api/dataset?light=true', '/api/governance/candidates', '/api/evaluation', '/api/bad-cases', '/api/optimization', '/api/versions', '/api/readiness', '/api/monitoring', '/api/pipeline', '/api/governance/generation-runs', '/api/governance/snapshots', '/api/governance/revisions', '/api/evaluations']:
                capture(path)
            documents = responses['/api/documents']['body']
            for doc in documents:
                capture('/api/documents/' + doc['id'])
                if doc.get('pdf_url'): capture(doc['pdf_url'])
            for run in responses['/api/governance/generation-runs']['body']:
                capture('/api/governance/generation-runs/' + run['id'])
                capture('/api/governance/generation-runs/' + run['id'] + '/questions', allow_read_error=True)
                if run['status'] == 'completed': capture('/api/governance/generation-runs/' + run['id'] + '/export?format=json')
            for run in responses['/api/evaluations']['body']:
                capture('/api/evaluations/' + run['id'])
            for row in responses['/api/governance/revisions']['body']:
                capture('/api/governance/revisions/' + row['id'])
            for row in responses['/api/bad-cases']['body']:
                capture('/api/bad-cases/' + row['id'])
            for row in responses['/api/monitoring']['body'].get('triggers', []):
                if row.get('optimization_context_id'): capture('/api/experiments/' + row['optimization_context_id'])
            for slot in ('business', 'technical'):
                meta = capture('/api/overview/architecture/' + slot)
                if meta.get('image_url'): capture(meta['image_url'])
            client.close()
    after = {str(path): fingerprint(path) for path in protected}
    assert before == after, 'Protected real DB/backup/index files changed'
    workspace = responses['/api/workspace']['body']
    snapshots = responses['/api/governance/snapshots']['body']
    current = next(row for row in snapshots if row['id'] == workspace['current_golden_id'])
    candidates = responses['/api/optimization']['body'].get('candidates', [])
    production = next(row for row in responses['/api/versions']['body'] if row['status'] == 'active')
    golden_ids = set(current['snapshot']['question_ids'])
    golden_rows = [row for row in responses['/api/dataset']['body'] if row['id'] in golden_ids]
    capture_proof = {'provenance': 'Current new-code GET responses from a disposable copy of the saved real DB; no lifecycle replay', 'backup': str(args.backup), 'provider_disabled': True, 'tcp_disabled': True, 'lifespan_started': False, 'get_response_count': len(responses), 'protected_files_unchanged': True, 'before': before, 'after': after, 'golden': {'id': current['id'], 'count': len(current['snapshot']['question_ids']), 'planner_version': current['snapshot'].get('planner_version') or (current['snapshot'].get('coverage_plan') or {}).get('planner_version'), 'categories': {category: sum(row.get('test_category') == category for row in golden_rows) for category in ('positive', 'ablation', 'negative')}, 'category_source': 'Persisted /api/dataset rows joined by frozen question_ids; legacy raw snapshot omitted categories'}, 'production': {'id': production['id'], 'candidate_id': production.get('snapshot', {}).get('candidate_id')}, 'candidates': [{'label': row.get('reasoning', {}).get('candidate_label'), 'id': row['id'], 'gates': row.get('result', {}).get('gates'), 'qualification': row.get('result', {}).get('qualification'), 'regression': row.get('result', {}).get('regression')} for row in candidates], 'index': responses['/api/pipeline']['body']['index'], 'readiness_note': 'Runtime readiness reflects safety environment with empty API key and forced mock; it is not a live Provider readiness claim'}
    (args.output / 'payloads.json').write_text(json.dumps(responses, ensure_ascii=False))
    (args.output / 'capture-proof.json').write_text(json.dumps(capture_proof, ensure_ascii=False, indent=2))
    print(json.dumps({'get_responses': len(responses), 'protected_unchanged': True, 'golden': capture_proof['golden'], 'production': capture_proof['production'], 'payloads': str(args.output / 'payloads.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
