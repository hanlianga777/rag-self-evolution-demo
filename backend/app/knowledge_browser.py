"""Read-only views of current chunks and anchors from the latest frozen Golden."""
import json
import sqlite3
from collections import Counter
from contextlib import closing
from .sqlite_support import open_database
from .corpus import _read_json


def frozen_evidence_ids(question):
    anchors = set()
    for source in (question.get('evidence') or []) + (question.get('acceptable_evidence') or []):
        anchors.update(source.get('source_chunk_ids') or [])
    for source in (question.get('business_requirements') or {}).get('sources') or []:
        if source.get('chunk_id'):
            anchors.add(source['chunk_id'])
    return anchors


def chunk_diagnostics(corpus):
    parents = _read_json(corpus.index_dir/'parents.json', [])
    children = corpus.chunks()
    counts = Counter(c.get('parent_chunk_id') for c in children)
    tokens = [c.get('token_count') for c in children]
    complete = bool(tokens) and all(isinstance(n, (int, float)) for n in tokens)
    return {'parent_count': len(parents), 'child_count': len(children),
            'fragment_count': sum(c['token_count'] < 60 and not c.get('table') for c in children) if complete else None,
            'fragment_threshold_tokens': 60, 'fragment_excludes_tables': True,
            'average_children_per_parent': sum(counts[p['chunk_id']] for p in parents)/len(parents) if parents else None,
            'single_child_parent_ratio': sum(counts[p['chunk_id']] == 1 for p in parents)/len(parents) if parents else None,
            'average_child_tokens': sum(tokens)/len(tokens) if complete else None}


def chunk_browser(corpus, store):
    parents = _read_json(corpus.index_dir/'parents.json', [])
    children = corpus.chunks()
    by_id = {c['chunk_id']: c for c in children}
    parent_ids = {p['chunk_id'] for p in parents}
    with closing(open_database(store.database_path, read_only=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        row = connection.execute("SELECT id,snapshot_json FROM dataset_versions WHERE status='approved' ORDER BY created_at DESC,rowid DESC LIMIT 1").fetchone()
    snapshot = json.loads(row['snapshot_json']) if row else {}
    questions, unmatched = [], set()
    for q in snapshot.get('questions', []):
        anchors = frozen_evidence_ids(q)
        unmatched.update(anchors - by_id.keys())
        hits = [c for c in children if c['chunk_id'] in anchors]
        # Project frozen data; never join mutable candidate/probe/QC records here.
        question = {key: q.get(key) for key in ('id', 'display_id', 'question', 'reference_answer', 'test_category', 'evaluation_group', 'expected_behavior', 'negative_subtype', 'topic_cluster')}
        question['display_id'] = q.get('display_id') or q.get('coverage_slot') or '题号未记录'
        question['test_category'] = q.get('evaluation_group') or q.get('test_category')
        question.update(child_ids=[c['chunk_id'] for c in hits],
                        parent_ids=list(dict.fromkeys(c['parent_chunk_id'] for c in hits if c.get('parent_chunk_id') in parent_ids)),
                        raw={'business_requirements': q.get('business_requirements', {})},
                        evidence_details=[{'chunks': hits}])
        questions.append(question)
    grouped = {}
    for child in children: grouped.setdefault(child.get('parent_chunk_id'), []).append(child)
    records = [{**p, 'children': sorted(grouped.get(p['chunk_id'], []), key=lambda c: c.get('char_start', 0))} for p in parents]
    return {'documents': corpus.documents(), 'parents': records, 'questions': questions,
            'dataset_id': row['id'] if row else None, 'unmatched_anchor_count': len(unmatched),
            'saved_topic_clusters': {c['cluster_id']: c.get('chunk_ids', []) for c in (snapshot.get('coverage_plan') or {}).get('clusters', [])}}


def cluster_browser(cluster, browser):
    child_ids = set(cluster.get('chunk_ids', []))
    parents = [p for p in browser['parents'] if any(c['chunk_id'] in child_ids for c in p['children'])]
    # Topic IDs alone are not stable across plans. Include unanchored questions
    # only when the saved topic membership equals the current topic membership.
    same_topic = set(browser['saved_topic_clusters'].get(cluster['cluster_id'], [])) == child_ids and bool(child_ids)
    questions = [q for q in browser['questions'] if child_ids.intersection(q['child_ids']) or same_topic and q.get('topic_cluster') == cluster['cluster_id']]
    paths = [part.strip() for p in parents for part in (p.get('section_path') or p.get('chapter') or '').split(' / ') if part.strip() and not part.lower().endswith('.pdf')]
    keywords = [word for word, _ in Counter(paths).most_common(6)]
    label = cluster.get('semantic_label') or cluster.get('label') or '说明书知识'
    return {'description': f'这个主题汇集了与“{label}”相关的说明书内容。', 'keywords': keywords, 'parents': [{key: p.get(key) for key in ('chunk_id', 'document_id', 'document_name', 'chapter', 'section_path', 'page_start', 'page_end')} | {'child_count': len(p['children'])} for p in parents],
            'questions': questions, 'dataset_id': browser['dataset_id']}
