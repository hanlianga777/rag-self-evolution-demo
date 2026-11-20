import json
import sqlite3
from contextlib import closing

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api_fixture import main
from app.corpus import CorpusStore
from app.governance import GovernanceStore


def chunk(key, path, body, document='ABB_IRB1300_产品手册.pdf'):
    return {'chunk_id': key, 'section_path': path, 'chunk_text': body, 'document_name': document}


def test_largest_remainder_respects_topic_minimum_and_distributes_groups_by_fragments():
    from app.business_topics import topic_quotas, cluster_quotas

    assert topic_quotas([103, 33, 25, 94, 100, 867, 56, 15, 47]) == [2, 1, 1, 2, 2, 7, 2, 1, 2]
    assert topic_quotas([10_000, 1, 1]) == [18, 1, 1]
    assert cluster_quotas(3, [20, 5, 100]) == [1, 0, 2]
    assert cluster_quotas(5, [20, 5, 100]) == [1, 0, 4]


def test_section_clustering_keeps_small_groups_and_keeps_one_assignment_per_section(monkeypatch):
    from app.business_topics import build_topics

    monkeypatch.setattr('app.business_topics.topic_quotas', lambda sizes: [1, 19])
    repair = '5 维修 / 5.6 电机 / '
    chunks = [
        chunk('M1', repair + '5.6.1 更换轴 1 电机 / 5.6.1.1 拆除', '正文 1'),
        chunk('M2', repair + '5.6.1 更换轴 1 电机 / 5.6.1.2 安装', '正文 2'),
        chunk('M3', repair + '5.6.2 更换轴 2 电机', '正文 3'),
        chunk('M4', repair + '5.6.10 更换轴 6 电机', '正文 4'),
        chunk('M5', repair + '5.6.1 更换轴 1 电机', ' 正文　１ '),
        chunk('S', '1 安全 / 1.1 简介', '正文 1'),
        chunk('N', '前言', '正文 2'),
    ]
    vectors = np.array([[0, 0], [20, 10], [10, 6], [0, 1], [-20, -10], [1, 1], [1, 1]])
    plan = build_topics(chunks, vectors)
    assert plan == build_topics(chunks[::-1], vectors[::-1])
    safety, repair = plan['topics']
    assert len(repair['clusters']) == repair['initial_k'] == 3
    assert [group['size'] for group in repair['clusters']] == [2, 1, 1]
    assert [group['sections'][0]['number'] for group in repair['clusters']] == ['5.6.1', '5.6.2', '5.6.10']
    assert [group['name'] for group in repair['clusters']] == ['电机更换'] * 3
    assert safety['clusters'] == []
    assert safety['sections'] == [{'number': '1.1', 'title': '简介'}]
    by_id = {row['chunk_id']: row for row in plan['assignments']}
    assert by_id['M5']['is_duplicate_of'] == 'M1'
    assert by_id['M5']['cluster_id'] == by_id['M1']['cluster_id']
    assert by_id['S']['is_duplicate_of'] is None
    assert 'N' not in by_id


def test_section_clustering_reports_collapsed_vectors():
    from app.business_topics import build_topics

    chunks = [chunk('A1', '5 维修 / 5.6.1 更换电机', '甲'),
              chunk('A2', '5 维修 / 5.6.1 更换电机', '乙'),
              chunk('A3', '5 维修 / 5.6.1 更换电机', '甲'),
              chunk('B', '5 维修 / 5.6.2 更换电机', '丙'),
              chunk('C', '5 维修 / 5.7.2 更换齿轮箱', '丁')]
    with pytest.raises(ValueError, match=r'维修.*k=3.*实得 2 组.*向量.*重复'):
        build_topics(chunks, [[2, 0], [0, 2], [8, 8], [1, 1], [0, 1]])


@pytest.mark.parametrize(('titles', 'expected'), [
    (['更换电机'] * 3 + ['换油', '清洁工具'], ('电机更换', .6, False)),
    (['更换电机'] * 2 + ['更换齿轮箱'] * 2 + ['清洁工具'], ('电机更换 与 齿轮箱维修', .4, False)),
    (['拆除上臂'] * 2 + ['更换电机', '清洁工具', '例行介绍'], ('混合：机械结构与密封件、电机更换 等', .4, True)),
    (['简介', '通用要求'], ('混合：未归类', 0, True)),
    (['齿轮箱润滑油的类型', '油类型'], ('润滑剂', 1, False)),
])
def test_business_names_follow_section_family_thresholds(titles, expected):
    from app.business_topics import business_group_name

    assert business_group_name(titles) == expected


def test_deepest_section_used_outside_repair_and_maintenance():
    from app.business_topics import build_topics

    chunks = [chunk('I', '3 安装 / 3.1 机械 / 3.1.1 安装 / 3.1.1.1 提升', '甲'),
              chunk('M', '4 维护 / 4.2 计划 / 4.2.1 维护计划 / 4.2.1.1 说明', '乙')]
    installation, maintenance = build_topics(chunks, [[1, 1], [1, 0]])['topics']
    assert installation['sections'] == [{'number': '3.1.1.1', 'title': '提升'}]
    assert maintenance['sections'] == [{'number': '4.2.1', 'title': '维护计划'}]


def test_http_counts_only_frozen_question_metadata(tmp_path, monkeypatch):
    store = GovernanceStore(tmp_path / 'test.db')
    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setattr(main, 'corpus', CorpusStore(tmp_path))
    chunks = [chunk('C1', '5 维修 / 5.1.1 更换电机', '正文 1'),
              chunk('C2', '5 维修 / 5.1.2 更换齿轮箱', '正文 2'),
              chunk('S', '1 安全 / 1.1 简介', '安全步骤')]
    identity = {'corpus_snapshot_id': 'current', 'index_artifact_id': 'IDX-test', 'sources': {}}
    (tmp_path / 'manifest.json').write_text(json.dumps({'knowledge_identity': identity, 'sources': {}}))
    (tmp_path / 'chunks.json').write_text(json.dumps(chunks))
    np.save(tmp_path / 'embeddings.npy', [[1, 0], [0, 1], [1, 0]])
    client = TestClient(main.app)
    questions = [
        {'id': 'A', 'test_category': 'ablation', 'paired_question': 'Q01', 'business_topic': '安全',
         'business_group': '05-02', 'evidence': [{'source_chunk_ids': ['S']}]},
        {'id': 'P', 'coverage_slot': 'Q01', 'test_category': 'positive', 'business_topic': '维修',
         'business_group': '06-01', 'evidence': [{'source_chunk_ids': ['C1', 'C2', 'S']}]},
        {'id': 'N', 'test_category': 'negative', 'business_topic': '安全', 'evidence': []},
        {'id': 'N2', 'test_category': 'negative', 'business_topic': '知识库外', 'evidence': []},
        {'id': 'Old', 'test_category': 'positive', 'evidence': [{'source_chunk_ids': ['S']}]},
        {'id': 'A2', 'test_category': 'ablation', 'source_positive_id': 'Old', 'business_topic': '安全'},
    ]

    def save(id_, *, status='approved', fingerprint=identity, imported=True):
        snapshot = {'corpus_fingerprint': fingerprint, 'questions': questions}
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
    assert all(topic['questions'] is None and topic['quota'] > 0 for topic in empty.json()['topics'])

    save('D')
    before = store.database_path.read_bytes()
    result = client.get(url).json()
    assert result['has_frozen_exam'] is True
    safety, repair, outside = result['topics']
    assert repair['questions'] == {'positive': 1, 'ablation': 1, 'negative': 0}
    assert [g['questions'] for g in repair['clusters']] == [2, 0]
    assert safety['questions'] == {'positive': 0, 'ablation': 0, 'negative': 1}
    assert outside['name'] == '知识库外（负向）'
    assert outside['questions'] == {'positive': 0, 'ablation': 0, 'negative': 1}
    assert store.database_path.read_bytes() == before
    assert client.post(url).status_code == 405
