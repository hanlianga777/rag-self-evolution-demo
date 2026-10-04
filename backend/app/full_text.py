"""Raw parser pages and complete bundle integrity; no embedding/model work here."""
import hashlib
import json
import re
import threading
from pathlib import Path

# ponytail: one process-wide lock pins short corpus reads/activation; use a RW lock only if measured contention warrants it.
CORPUS_LOCK = threading.RLock()
ARTIFACTS = ('documents.json', 'chunks.json', 'faiss.index', 'full_text.json')


def checksum(value):
    return hashlib.sha256(value).hexdigest()


def write_full_text(index_dir, manifest, documents, pages):
    value = {'artifact_schema_version': 1, 'corpus_fingerprint': manifest['sources'],
             'parser_identity': 'PyMuPDF+RapidOCR/page-text-v1', 'pages': pages,
             'coverage': {'total_pages': sum(doc.get('pages') or 0 for doc in documents),
                          'parsed_pages': sum(bool(page['text'].strip()) for page in pages),
                          'status': 'complete' if all(doc.get('pages') is not None for doc in documents) and len(pages) == sum(doc.get('pages') or 0 for doc in documents) and all(page['text'].strip() for page in pages) else 'insufficient',
                          'limitation': 'Text extraction/OCR coverage is not a guarantee of table or semantic fidelity.'}}
    (index_dir / 'full_text.json').write_text(json.dumps(value, ensure_ascii=False, indent=2))
    manifest = {**manifest, 'artifact_schema_version': 3, 'artifacts': {name: checksum((index_dir / name).read_bytes()) for name in ARTIFACTS}}
    (index_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return value


def validate_bundle(index_dir, *, require_full_text=False):
    index_dir = Path(index_dir)
    manifest = json.loads((index_dir / 'manifest.json').read_text())
    documents = json.loads((index_dir / 'documents.json').read_text())
    chunks = json.loads((index_dir / 'chunks.json').read_text())
    if not (index_dir / 'faiss.index').is_file():
        raise ValueError('Bundle missing FAISS index')
    import faiss
    if faiss.read_index(str(index_dir / 'faiss.index')).ntotal != len(chunks):
        raise ValueError('FAISS vector count differs from Chunk count')
    full_text = None
    if require_full_text or manifest.get('artifact_schema_version', 0) >= 3 or (index_dir / 'full_text.json').exists():
        hashes = manifest.get('artifacts', {})
        if any(not hashes.get(name) or checksum((index_dir / name).read_bytes()) != hashes[name] for name in ARTIFACTS):
            raise ValueError('Bundle artifact checksum mismatch')
        full_text = json.loads((index_dir / 'full_text.json').read_text())
        if full_text.get('corpus_fingerprint') != manifest.get('sources'):
            raise ValueError('Full-text Corpus fingerprint mismatch')
        by_id = {doc['id']: doc for doc in documents}
        if set(by_id) != set(manifest['sources']) or any(doc.get('source_fingerprint') != manifest['sources'][key] for key, doc in by_id.items()):
            raise ValueError('Document Corpus fingerprint mismatch')
        seen = set()
        for page in full_text.get('pages', []):
            key = (page['document_id'], page['page'])
            doc = by_id.get(page['document_id'])
            if key in seen or not doc or type(page['page']) is not int or not 1 <= page['page'] <= (doc.get('pages') or 0) or page.get('source_fingerprint') != manifest['sources'][page['document_id']] or page.get('text_checksum') != checksum(page['text'].encode()):
                raise ValueError('Full-text page identity/checksum mismatch')
            seen.add(key)
        if any(chunk.get('document_id') not in by_id for chunk in chunks):
            raise ValueError('Chunk document identity mismatch')
        total = sum(doc.get('pages') or 0 for doc in documents)
        parsed = sum(bool(page['text'].strip()) for page in full_text['pages'])
        coverage = full_text.get('coverage', {})
        if coverage.get('total_pages') != total or coverage.get('parsed_pages') != parsed or (coverage.get('status') == 'complete' and (len(seen) != total or parsed != total)):
            raise ValueError('Full-text coverage mismatch')
    if manifest.get('knowledge_identity'):
        import numpy as np
        hashes = manifest.get('artifacts', {})
        required = {'parents.json', 'embeddings.npy', 'coverage.json', *ARTIFACTS}
        if not required.issubset(hashes) or any(not (index_dir/name).is_file() or checksum((index_dir/name).read_bytes()) != value for name, value in hashes.items()):
            raise ValueError('Knowledge artifact checksum mismatch')
        parents = json.loads((index_dir/'parents.json').read_text())
        by_parent = {p['chunk_id']: p for p in parents}
        if len(by_parent) != len(parents) or len({c['chunk_id'] for c in chunks}) != len(chunks):
            raise ValueError('Duplicate Parent/Child identity')
        config = manifest['knowledge_config']
        vectors = np.load(index_dir/'embeddings.npy', allow_pickle=False)
        index = faiss.read_index(str(index_dir/'faiss.index'))
        if vectors.shape != (len(chunks), config['dimension']) or index.d != config['dimension'] or not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) == 0):
            raise ValueError('Knowledge embedding dimension/value mismatch')
        if not np.allclose(index.reconstruct_n(0, index.ntotal), vectors):
            raise ValueError('FAISS differs from Embedding artifact')
        for chunk in chunks:
            parent = by_parent.get(chunk.get('parent_chunk_id'))
            if not parent or chunk['document_id'] != parent['document_id'] or not parent['page_start'] <= chunk['page_start'] <= chunk['page_end'] <= parent['page_end'] or chunk['chunk_text'] not in parent['chunk_text']:
                raise ValueError('Invalid Child to Parent traceability')
        plan = json.loads((index_dir/'coverage.json').read_text())
        if plan['corpus_fingerprint'] != manifest['knowledge_identity'] or plan['plan_id'] != manifest['coverage_plan_id'] or set(plan['chunk_clusters']) != {c['chunk_id'] for c in chunks}:
            raise ValueError('Coverage does not belong to Knowledge bundle')
    return {'path': index_dir, 'manifest': manifest, 'chunks': chunks, 'documents': documents, 'full_text': full_text}


def search_full_text(question, full_text):
    if full_text is None:
        return {'status': 'not_collected', 'coverage': None, 'matches': [], 'signal_only': True, 'reason': 'raw_full_text_unavailable'}
    # General anchors only: identifiers, numbers/units, Chinese phrases (6-8 chars), bounded at 24.
    anchors = re.findall(r'[A-Za-z][A-Za-z0-9_.-]*|\d+(?:\.\d+)?\s*[A-Za-z%℃伏瓦安米秒]*', question)
    for phrase in re.findall(r'[\u4e00-\u9fff]+', question):
        anchors.extend(phrase[i:i + size] for size in (8, 6) for i in range(max(0, len(phrase) - size + 1)))
        if 2 <= len(phrase) < 6:
            anchors.append(phrase)
    anchors = list(dict.fromkeys(anchors))[:24]
    matches = []
    for page in full_text['pages']:
        terms = [term for term in anchors if term.lower() in page['text'].lower()]
        if not terms:
            continue
        position = min(page['text'].lower().index(term.lower()) for term in terms)
        matches.append({**{key: page[key] for key in ('document_id', 'page', 'parser', 'text_checksum')},
                        'matched_terms': terms, 'method': 'raw_page_anchor',
                        'content': page['text'], 'content_preview': page['text'][max(0, position - 100):position + 300]})
    return {'status': 'searched', 'corpus_fingerprint': full_text['corpus_fingerprint'], 'coverage': full_text['coverage'], 'anchors': anchors, 'matches': matches, 'signal_only': True}
