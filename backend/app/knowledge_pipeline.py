"""Versioned remote Knowledge Pipeline; legacy artifacts are never rewritten."""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
import json
import http.client
import ipaddress
import socket
import ssl
import urllib.parse
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np

from .corpus import EMBEDDING_MODEL, source_fingerprint, _split_long_part
from .full_text import CORPUS_LOCK, checksum, validate_bundle, write_full_text
from .providers import ProviderUnavailable

CONFIG = {'parser': 'MinerU', 'parser_mode': 'vlm', 'table_normalize': 'table-kv-v1',
          'chunk_strategy': 'Parent-Child', 'parent_tokens': 1400, 'child_tokens': 400,
          'overlap_tokens': 80, 'tokenizer_model': EMBEDDING_MODEL,
          'embedding_model': 'text-embedding-v4', 'dimension': 1024,
          'rerank_model': 'qwen3-rerank', 'candidate_k': 12, 'top_k': 4}


def digest(value):
    return checksum(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def settings():
    from .config import load_values
    return load_values()


def provider_status(values=None):
    values = settings() if values is None else values
    return {name: 'configured' if values.get(key, '').strip() else 'missing' for name, key in
            [('mineru', 'MINERU_API_KEY'), ('embedding', 'DASHSCOPE_API_KEY'), ('rerank', 'DASHSCOPE_API_KEY'), ('deepseek', 'DEEPSEEK_API_KEY')]}


def version_identity(sources, config):
    pipeline = 'KP-' + digest(config)[:20]
    return {'pipeline_version_id': pipeline, 'corpus_snapshot_id': 'CORPUS-' + digest([sources, pipeline])[:20], 'sources': sources}


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.row = []; self.cell = None; self.complex = False

    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        if tag in ('td', 'th'):
            self.cell = []
            if any(k in ('rowspan', 'colspan') and v != '1' for k, v in attrs): self.complex = True

    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(self.cell).strip()); self.cell = None
        if tag == 'tr' and self.row: self.rows.append(self.row)


def normalize_table(html):
    reader = TableReader(); reader.feed(html)
    if not reader.rows: return ''
    headers = reader.rows[0]
    if reader.complex or len(reader.rows) < 2 or not all(headers):
        return '\n'.join(' | '.join(row) for row in reader.rows)
    return '\n'.join('；'.join(f'{key}={value}' for key, value in zip(headers, row))
                     if len(row) == len(headers) else ' | '.join(row) for row in reader.rows[1:])


def parent_child(document, blocks, counter, *, parent_tokens=1400, child_tokens=400, overlap=80):
    if not 0 <= overlap < child_tokens <= parent_tokens: raise ValueError('Invalid Parent-Child token limits')
    parsed, units, section = [], [], ''
    for index, block in enumerate(blocks):
        page = int(block.get('page_idx', 0)) + 1
        if page < 1: raise ValueError('Invalid parser page')
        raw_text = block.get('text', '')
        if block.get('type') == 'table': raw_text = normalize_table(block.get('table_body', ''))
        if not raw_text:
            raw_text = '\n'.join(block.get('list_items', []) + block.get('image_caption', []) + block.get('table_caption', [])) or block.get('code_body', '') or block.get('latex', '')
        if block.get('text_level') and raw_text: section = raw_text.strip()
        block_id = f"{document['id']}-BLOCK-{index + 1:05d}"
        parsed.append({'block_id': block_id, 'page': page, 'section_path': section, 'text': raw_text, 'raw': block})
        for part in _split_long_part(raw_text.strip(), page, counter, parent_tokens) if raw_text.strip() else []:
            units.append({**part, 'section_path': section, 'block_id': block_id})
    parents, children, current = [], [], []

    def flush():
        if not current: return
        parent_id = f"{document['id']}-P-{len(parents) + 1:05d}"
        text = '\n'.join(unit['text'] for unit in current)
        metadata = {key: document.get(key) for key in ('product', 'vendor')}
        metadata.update(document_id=document['id'], document_name=document['name'], section_path=current[0]['section_path'], section=current[0]['section_path'])
        spans, offset = [], 0
        for unit in current:
            spans.append((offset, offset + len(unit['text']), unit['page'], unit['block_id']))
            offset += len(unit['text']) + 1
        parent = {**metadata, 'chunk_id': parent_id, 'chunk_text': text, 'text': text, 'token_count': counter(text),
                  'page_start': min(u['page'] for u in current), 'page_end': max(u['page'] for u in current),
                  'block_ids': list(dict.fromkeys(u['block_id'] for u in current))}
        parents.append(parent)
        start = 0
        while start < len(text):
            end = start + 1
            while end < len(text) and counter(text[start:end + 1]) <= child_tokens: end += 1
            if counter(text[start:end]) > child_tokens: raise ValueError('Tokenizer cannot fit one character')
            covered = [span for span in spans if span[0] < end and span[1] > start]
            children.append({**metadata, 'chunk_id': f"{document['id']}-C-{len(children) + 1:05d}", 'parent_chunk_id': parent_id,
                             'chunk_text': text[start:end], 'text': text[start:end], 'token_count': counter(text[start:end]),
                             'page_start': min(s[2] for s in covered), 'page_end': max(s[2] for s in covered),
                             'block_ids': list(dict.fromkeys(s[3] for s in covered)), 'embedding_status': 'Indexed'})
            if end == len(text): break
            next_start = end
            while next_start > start + 1 and counter(text[next_start - 1:end]) <= overlap: next_start -= 1
            start = next_start

    for unit in units:
        if current and (current[0]['section_path'] != unit['section_path'] or counter('\n'.join(u['text'] for u in current + [unit])) > parent_tokens):
            flush(); current = []
        current.append(unit)
    flush()
    return parents, children, parsed


def expand_parents(hits, parents, top_k):
    by_id = {p['chunk_id']: p for p in parents}; expanded = {}
    for hit in hits:
        key = hit['parent_chunk_id']
        if key not in by_id: raise ValueError('Missing Parent for retrieved Child')
        if key not in expanded:
            parent = by_id[key]
            expanded[key] = {**hit, 'parent_chunk_id': key, 'content': parent['chunk_text'], 'child_content': hit['content'],
                             'parent_page_start': parent['page_start'], 'parent_page_end': parent['page_end'], 'matched_child_ids': []}
        expanded[key]['matched_child_ids'].append(hit['chunk_id'])
    return list(expanded.values())[:top_k]


class AlibabaProvider:
    def __init__(self, values=None): self.values = settings() if values is None else values

    def _post(self, path, payload):
        key = self.values.get('DASHSCOPE_API_KEY', '').strip()
        base = self.values.get('DASHSCOPE_BASE_URL', '').rstrip('/')
        if not key or not base: raise ProviderUnavailable('Alibaba Key / business-space endpoint missing')
        request = urllib.request.Request(base + path, data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
        from .telemetry import record_usage
        started = time.perf_counter()
        call_started_at = datetime.now(timezone.utc).isoformat()
        try:
            with urllib.request.urlopen(request, timeout=60) as response: body = json.load(response)
            record_usage({**body.get('usage', {}), 'provider':'Alibaba', 'requested_model':payload['model'], 'call_started_at':call_started_at, 'status':'ok', 'latency_ms':round((time.perf_counter()-started)*1000)})
            return body
        except (urllib.error.URLError, TimeoutError) as error:
            record_usage({'provider':'Alibaba','requested_model':payload['model'],'call_started_at':call_started_at,'status':'failed','latency_ms':round((time.perf_counter()-started)*1000)})
            raise ProviderUnavailable(f'Alibaba request failed ({type(error).__name__})') from None

    def embed(self, texts, dimension):
        vectors = []
        for offset in range(0, len(texts), 10):
            batch = texts[offset:offset + 10]
            body = self._post('/compatible-mode/v1/embeddings', {'model': 'text-embedding-v4', 'input': batch, 'dimensions': dimension})
            rows = sorted(body.get('data', []), key=lambda r: r['index'])
            if [r['index'] for r in rows] != list(range(len(batch))): raise ValueError('Embedding response count/order mismatch')
            vectors.extend(r['embedding'] for r in rows)
        array = np.asarray(vectors, dtype='float32')
        if array.shape != (len(texts), dimension) or not np.isfinite(array).all() or np.any(np.linalg.norm(array, axis=1) == 0):
            raise ValueError('Embedding response dimension/value mismatch')
        return array / np.linalg.norm(array, axis=1)[:, None]

    def rerank(self, query, hits):
        if not hits: return []
        body = self._post('/compatible-api/v1/reranks', {'model': 'qwen3-rerank', 'query': query, 'documents': [h['content'] for h in hits], 'top_n': len(hits)})
        rows = body.get('results', [])
        if sorted(r['index'] for r in rows) != list(range(len(hits))): raise ValueError('Rerank response count/index mismatch')
        if any(not np.isfinite(float(r['relevance_score'])) for r in rows): raise ValueError('Invalid Rerank score')
        return [{**hits[r['index']], 'score': float(r['relevance_score']), 'rerank_score': float(r['relevance_score'])}
                for r in sorted(rows, key=lambda r: (-r['relevance_score'], r['index']))]


def download_mineru_result(url):
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    except urllib.error.URLError as error:
        target = urllib.parse.urlsplit(url)
        if not isinstance(error.reason, ssl.SSLEOFError) or target.scheme != 'https' or target.hostname != 'cdn-mineru.openxlab.org.cn':
            raise
    # ponytail: only this official CDN's observed VPN DNS/TLS failure uses a public DNS lookup.
    # The resolver receives the public hostname only; signed paths stay on the verified CDN connection.
    with urllib.request.urlopen('https://dns.alidns.com/resolve?name=cdn-mineru.openxlab.org.cn&type=A', timeout=15) as response:
        addresses = [row['data'] for row in json.load(response).get('Answer', []) if row['type'] == 1]
    for address in addresses[:3]:
        ipaddress.ip_address(address)
        connection = http.client.HTTPSConnection(target.hostname, timeout=120)
        try:
            connection.sock = ssl.create_default_context().wrap_socket(socket.create_connection((address, 443), timeout=120), server_hostname=target.hostname)
            connection.request('GET', target.path + ('?' + target.query if target.query else ''))
            response = connection.getresponse()
            if response.status == 200:
                return response.read()
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
    raise ProviderUnavailable('MinerU result CDN connection failed')


class MinerUProvider:
    def __init__(self, values=None): self.values = settings() if values is None else values

    def _request(self, path, payload=None):
        key = self.values.get('MINERU_API_KEY', '').strip()
        if not key: raise ProviderUnavailable('MinerU Token missing')
        base = self.values.get('MINERU_BASE_URL', 'https://mineru.net').rstrip('/')
        request = urllib.request.Request(base + '/api/v4/' + path, data=json.dumps(payload).encode() if payload is not None else None,
                                         headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response: body = json.load(response)
        except (urllib.error.URLError, TimeoutError): raise ProviderUnavailable('MinerU request failed') from None
        if body.get('code') != 0: raise ProviderUnavailable('MinerU rejected parsing request')
        return body['data']

    def parse(self, path, document_id):
        task = self._request('file-urls/batch', {'files': [{'name': path.name, 'data_id': document_id}], 'model_version': 'vlm', 'enable_table': True, 'enable_formula': True})
        # Signed upload expects an empty Content-Type; urllib otherwise inserts form-urlencoded.
        request = urllib.request.Request(task['file_urls'][0], data=path.read_bytes(), headers={'Content-Type': ''}, method='PUT')
        try:
            with urllib.request.urlopen(request, timeout=120): pass
            deadline = time.monotonic() + 1200
            while time.monotonic() < deadline:
                batch = self._request('extract-results/batch/' + task['batch_id'])
                item = batch['extract_result'][0]
                if item['state'] == 'failed': raise ProviderUnavailable('MinerU VLM parsing failed')
                if item['state'] == 'done':
                    archive = download_mineru_result(item['full_zip_url'])
                    with zipfile.ZipFile(BytesIO(archive)) as bundle:
                        names = [n for n in bundle.namelist() if n.endswith('_content_list.json') or n.endswith('/content_list.json') or n == 'content_list.json']
                        if len(names) != 1: raise ValueError('MinerU structured content list missing/ambiguous')
                        blocks = json.loads(bundle.read(names[0]))
                        if not isinstance(blocks, list): raise ValueError('MinerU content list invalid')
                    return blocks, archive
                time.sleep(2)
        except (urllib.error.URLError, TimeoutError): raise ProviderUnavailable('MinerU upload/download failed') from None
        raise ProviderUnavailable('MinerU parsing timed out; task retained remotely')


class KnowledgePipeline:
    def __init__(self, index_dir, retriever):
        self.index_dir = Path(index_dir); self.retriever = retriever

    def build(self, documents, values=None, *, progress=lambda *args: None, parser=None, embedder=None, counter=None):
        import faiss
        from .governance import GENERATION_PROFILES
        from .golden_v2 import build_plan
        values = settings() if values is None else values
        if not documents: raise ValueError('Corpus has no source documents')
        if parser is None and provider_status(values)['mineru'] == 'missing': raise ProviderUnavailable('MinerU Token missing')
        if embedder is None and (not values.get('DASHSCOPE_API_KEY') or not values.get('DASHSCOPE_BASE_URL')): raise ProviderUnavailable('Alibaba Key / business-space endpoint missing')
        tokenizer_identity = None
        if counter is None:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL, local_files_only=True)
            tokenizer_identity = checksum(tokenizer.backend_tokenizer.to_str().encode())
            counter = lambda text: len(tokenizer.encode(text, add_special_tokens=False, truncation=False))
        config = dict(CONFIG)
        if tokenizer_identity: config['tokenizer_artifact_id'] = tokenizer_identity
        identity = version_identity({doc['id']: source_fingerprint(doc) for doc in documents}, config)
        if any(not value for value in identity['sources'].values()): raise ValueError('Source PDF missing')
        operation_id = 'KNOW-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        staging = self.index_dir.parent/'index_versions'/(operation_id + '-building'); staging.mkdir(parents=True)
        parser = parser or MinerUProvider(values); embedder = embedder or AlibabaProvider(values)
        parents, children, records, pages = [], [], [], []
        try:
            for number, doc in enumerate(documents, 1):
                from .corpus import DOCUMENTS_DIR, UPLOADS_DIR
                path = Path(doc['_source_path']) if doc.get('_source_path') else (UPLOADS_DIR if doc.get('storage') == 'uploads' else DOCUMENTS_DIR)/doc['name']
                progress('parse', number - 1, len(documents))
                blocks, archive = parser.parse(path, doc['id'])
                (staging/(doc['id'] + '-mineru.zip')).write_bytes(archive)
                progress('chunk', number - 1, len(documents))
                ps, cs, parsed = parent_child(doc, blocks, counter, parent_tokens=config['parent_tokens'], child_tokens=config['child_tokens'], overlap=config['overlap_tokens'])
                if not cs: raise ValueError('MinerU produced no searchable Child text')
                parents.extend(ps); children.extend(cs)
                (staging/(doc['id'] + '-blocks.json')).write_text(json.dumps(parsed, ensure_ascii=False))
                import pymupdf
                with pymupdf.open(path) as pdf: page_count = len(pdf)
                if any(p['page'] > page_count for p in parsed): raise ValueError('MinerU page outside source PDF')
                records.append({**{k: v for k, v in doc.items() if not k.startswith('_')}, 'pages': page_count, 'chunks': len(cs), 'parent_chunks': len(ps), 'status': 'Indexed', 'parser': 'MinerU · VLM', 'chunk_strategy': 'Parent-Child', 'source_fingerprint': identity['sources'][doc['id']]})
                for page in range(1, page_count + 1):
                    text = '\n'.join(p['text'] for p in parsed if p['page'] == page)
                    pages.append({'document_id': doc['id'], 'page': page, 'parser': 'MinerU/vlm', 'text': text, 'text_checksum': checksum(text.encode()), 'source_fingerprint': identity['sources'][doc['id']]})
            progress('embedding', 0, len(children))
            vectors = embedder.embed([c['chunk_text'] for c in children], config['dimension'])
            if vectors.shape != (len(children), config['dimension']): raise ValueError('Embedding artifact mismatch')
            np.save(staging/'embeddings.npy', vectors)
            progress('index', len(children), len(children))
            index = faiss.IndexFlatIP(vectors.shape[1]); index.add(vectors); faiss.write_index(index, str(staging/'faiss.index'))
            identity = {**identity, 'chunk_artifact_id': 'CHUNK-' + digest([parents, children])[:20], 'embedding_artifact_id': 'EMB-' + checksum(vectors.tobytes())[:20], 'index_artifact_id': 'IDX-' + checksum((staging/'faiss.index').read_bytes())[:20]}
            identity['pipeline_version_id'] = 'KP-' + digest([config, identity['chunk_artifact_id'], identity['embedding_artifact_id'], identity['index_artifact_id']])[:20]
            identity['corpus_snapshot_id'] = 'CORPUS-' + digest([identity['sources'], identity['pipeline_version_id']])[:20]
            for name, data in [('documents.json', records), ('chunks.json', children), ('parents.json', parents)]: (staging/name).write_text(json.dumps(data, ensure_ascii=False))
            manifest = {'schema': 4, 'sources': identity['sources'], 'embedding_model': config['embedding_model'], 'tokenizer_model': config['tokenizer_model'], 'knowledge_config': config, 'knowledge_identity': identity, 'target_tokens': config['child_tokens'], 'overlap_tokens': config['overlap_tokens']}
            write_full_text(staging, manifest, records, pages)
            full = json.loads((staging/'full_text.json').read_text()); full['parser_identity'] = 'MinerU/vlm'; (staging/'full_text.json').write_text(json.dumps(full, ensure_ascii=False))
            manifest = json.loads((staging/'manifest.json').read_text()); manifest['artifacts']['full_text.json'] = checksum((staging/'full_text.json').read_bytes())
            progress('coverage', 0, len(children))
            coverage = build_plan(children, vectors, {'name': 'full', **GENERATION_PROFILES['full']}, identity, identity['embedding_artifact_id'])
            (staging/'coverage.json').write_text(json.dumps(coverage, ensure_ascii=False))
            manifest['coverage_plan_id'] = coverage['plan_id']
            manifest['artifacts'].update({p.name: checksum(p.read_bytes()) for p in staging.iterdir() if p.is_file() and p.name != 'manifest.json'})
            (staging/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False))
            if {doc['id']: source_fingerprint(doc) for doc in documents} != identity['sources']:
                raise ValueError('Source PDFs changed during build')
            validate_bundle(staging, require_full_text=True)
            return staging, operation_id
        except Exception:
            # ponytail: failed staging retained for diagnosis; no automatic destructive cleanup.
            raise

    def activate(self, staging, operation_id, *, after_activate=None):
        from .corpus_management import CorpusManager
        manager = CorpusManager(self.retriever, index_dir=self.index_dir)
        with CORPUS_LOCK:
            manifest_path = self.index_dir/'manifest.json'
            legacy = manifest_path.exists() and not json.loads(manifest_path.read_text()).get('knowledge_identity')
            legacy_path = self.index_dir.resolve() if self.index_dir.is_symlink() else self.index_dir.parent/'index_versions'/(operation_id + '-previous')
            binding = self.index_dir.parent/'legacy_index.json'
            old_binding = binding.read_bytes() if binding.exists() else None
            def finish():
                if legacy: (self.index_dir.parent/'legacy_index.json').write_text(json.dumps({'path': str(legacy_path)}))
                if after_activate: after_activate()
            try:
                manager.activate_bundle(staging, operation_id, after_activate=finish)
            except Exception:
                if old_binding is None: binding.unlink(missing_ok=True)
                else: binding.write_bytes(old_binding)
                raise


def index_for_config(index_dir, config):
    """Unbound historical configurations belong to Legacy; never borrow active vectors."""
    index_dir = Path(index_dir)
    target = config.get('knowledge_identity')
    active_manifest = json.loads((index_dir/'manifest.json').read_text())
    if target:
        candidates = [index_dir, *(index_dir.parent/'index_versions').glob('*')]
        for path in candidates:
            if (path/'manifest.json').is_file() and json.loads((path/'manifest.json').read_text()).get('knowledge_identity') == target:
                return path
        raise ValueError('Bound Knowledge version unavailable')
    if not active_manifest.get('knowledge_identity'): return index_dir
    legacy = index_dir.parent/'legacy_index.json'
    if not legacy.exists(): raise ValueError('Legacy Production index binding missing')
    path = Path(json.loads(legacy.read_text())['path'])
    if not (path/'manifest.json').exists(): raise ValueError('Legacy Production index unavailable')
    return path
