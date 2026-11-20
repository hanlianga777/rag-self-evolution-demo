import json
import sqlite3
from contextlib import closing

import numpy as np
from fastapi.testclient import TestClient

from api_fixture import main
from app.corpus import CorpusStore
from app.governance import GovernanceStore


def chunk(key, path, body, document='ABB_IRB1300_产品手册.pdf'):
    return {'chunk_id': key, 'section_path': path, 'chunk_text': body, 'document_name': document}


def test_largest_remainder_respects_topic_minimum_and_cluster_capacity():
    from app.business_topics import topic_quotas, cluster_quotas

    assert topic_quotas([103, 33, 25, 94, 100, 867, 56, 15, 47]) == [2, 1, 1, 2, 2, 7, 2, 1, 2]
    assert topic_quotas([10_000, 1, 1]) == [18, 1, 1]
    assert cluster_quotas(3, [20, 5, 100, 6]) == [1, 0, 1, 1]
    assert cluster_quotas(5, [20, 5, 100]) == [1, 1, 3]


def test_clustering_stays_within_each_topic_and_merges_small_groups():
    from app.business_topics import build_topics

    chunks = [chunk(f'M{i:03}', '5 维修 / 5.4 更换 / 5.4.1 部件 / 装回盖板', f'正文 {i}') for i in range(120)]
    chunks += [chunk('M999-duplicate', '5 维修 / 5.9 其他', ' 正文　１ '),
               chunk('S', '1 安全', '正文 1'), chunk('N', '前言', '正文 2')]
    chunks += [chunk(f'Maint{i:02}', '4 维护', f'例行维护 {i}') for i in range(36)]
    vectors = np.repeat(np.eye(3, dtype='float32'), [59, 59, 2], axis=0)
    vectors = np.vstack([vectors, np.tile([0, 0, 1], (39, 1))])
    plan = build_topics(chunks, vectors)
    assert plan == build_topics(chunks[::-1], vectors[::-1])
    repair, = [topic for topic in plan['topics'] if topic['name'] == '维修']
    safety, = [topic for topic in plan['topics'] if topic['name'] == '安全']
    assert [repair['size'], repair['initial_k'], len(repair['clusters'])] == [120, 3, 2]
    assert sorted(group['size'] for group in repair['clusters']) == [59, 61]
    assert [safety['size'], safety['initial_k'], len(safety['clusters'])] == [1, 0, 0]
    maintenance, = [topic for topic in plan['topics'] if topic['name'] == '维护']
    assert [maintenance['size'], maintenance['initial_k'], len(maintenance['clusters'])] == [36, 1, 1]
    by_id = {row['chunk_id']: row for row in plan['assignments']}
    assert by_id['M999-duplicate']['is_duplicate_of'] == 'M001'
    assert by_id['M999-duplicate']['cluster_id'] == by_id['M001']['cluster_id']
    assert by_id['S']['is_duplicate_of'] is None
    assert 'N' not in by_id


def test_numbered_section_names_threshold_purity_and_duplicate_suffixes():
    from app.business_topics import build_topics

    paths = ['5 维修 / 5.1 更换 / 5.1.1 部件A / 装盖板',
             '5 维修 / 5.1 更换 / 5.1.2 部件B / 装盖板',
             '5 维修 / 5.1 更换 / 5.1.3 部件C']
    sections = [0] * 30 + [1] * 10 + [0] * 29 + [1] * 10 + [2]
    chunks = [chunk(f'C{i:03}', paths[s], f'正文 {i}') for i, s in enumerate(sections)]
    plan = build_topics(chunks, np.repeat(np.eye(2), 40, axis=0))
    first, second = plan['topics'][0]['clusters']
    assert [first['name'], second['name']] == ['5.1.1 部件A / 5.1.2 部件B（1）', '5.1.1 部件A / 5.1.2 部件B（2）']
    assert [first['purity'], second['purity']] == [.75, .725]
    assert second['sections'][-1] == ('5.1.3 部件C', .025)
    chunks[39]['section_path'] = paths[2]
    first = build_topics(chunks, np.repeat(np.eye(2), 40, axis=0))['topics'][0]['clusters'][0]
    assert first['name'] == '5.1.1 部件A（占 75.0%）'


def test_http_counts_only_current_frozen_imported_question_evidence(tmp_path, monkeypatch):
    store = GovernanceStore(tmp_path / 'test.db')
    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setattr(main, 'corpus', CorpusStore(tmp_path))
    chunks = [chunk(f'C{i:03}', '5 维修 / 5.1 更换', f'正文 {i}') for i in range(80)]
    chunks += [chunk('Dup', '5 维修 / 5.1 更换', '正文 1'), chunk('S', '1 安全', '安全步骤')]
    identity = {'corpus_snapshot_id': 'current', 'index_artifact_id': 'IDX-test', 'sources': {}}
    (tmp_path / 'manifest.json').write_text(json.dumps({'knowledge_identity': identity, 'sources': {}}))
    (tmp_path / 'chunks.json').write_text(json.dumps(chunks))
    vectors = np.repeat(np.eye(2), [40, 40], axis=0)
    np.save(tmp_path / 'embeddings.npy', np.vstack([vectors, [[1, 0], [1, 0]]]))
    client = TestClient(main.app)

    questions = [
        {'id': 'P', 'test_category': 'positive', 'evidence': [{'source_chunk_ids': ['C001', 'Dup', 'C045', 'S']}]},
        {'id': 'A', 'test_category': 'ablation', 'acceptable_evidence': [{'source_chunk_ids': ['Dup']}]},
        {'id': 'N', 'test_category': 'negative', 'evidence': [], 'coverage_anchor_chunk_ids': ['Dup']},
    ]

    def save(id_, *, status='approved', fingerprint=identity, imported=True):
        snapshot = {'corpus_fingerprint': fingerprint, 'question_ids': ['P', 'A', 'N'], 'questions': questions}
        if imported:
            snapshot['reviewed_import'] = {'source': '测试题卷.csv'}
        with closing(sqlite3.connect(store.database_path)) as db, db:
            db.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)', (id_, status, 'human_review', json.dumps(snapshot), id_))

    save('A', fingerprint={**identity, 'corpus_snapshot_id': 'old'})
    save('B', imported=False)
    save('C', status='draft')
    url = '/api/knowledge/topics'
    empty = client.get(url)
    assert empty.status_code == 200
    assert empty.json()['has_frozen_exam'] is False
    assert all(topic['questions'] is None for topic in empty.json()['topics'])

    save('D')
    before = store.database_path.read_bytes()
    result = client.get(url).json()
    assert result['has_frozen_exam'] is True
    repair, = [t for t in result['topics'] if t['name'] == '维修']
    assert repair['questions'] == {'positive': 1, 'ablation': 1, 'negative': 0}
    assert [g['questions'] for g in repair['clusters']] == [2, 1]
    safety, = [t for t in result['topics'] if t['name'] == '安全']
    assert safety['questions']['positive'] == 1
    assert store.database_path.read_bytes() == before
    assert client.post(url).status_code == 405
