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
    assert topic_quotas([10_000, 0, 1]) == [19, 0, 1]
    assert cluster_quotas(3, [20, 5, 100]) == [1, 0, 2]
    assert cluster_quotas(5, [20, 5, 100]) == [2, 1, 2]
    assert cluster_quotas(4, [5, 20, 100]) == [0, 2, 2]
    assert cluster_quotas(5, [20, 100]) == [2, 2]


def test_section_clustering_keeps_one_assignment_per_section(monkeypatch):
    from app.business_topics import build_topics

    monkeypatch.setattr('app.business_topics.topic_quotas', lambda sizes: [1, 6])
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
    assert sum(group['quota'] for group in safety['clusters']) == 1
    assert safety['sections'] == [{'number': '1.1', 'title': '简介'}]
    by_id = {row['chunk_id']: row for row in plan['assignments']}
    assert by_id['M5']['is_duplicate_of'] == 'M1'
    assert by_id['M5']['cluster_id'] == by_id['M1']['cluster_id']
    assert by_id['S']['is_duplicate_of'] is None
    assert 'N' not in by_id


def repair_groups(monkeypatch, quota, observations):
    from app.business_topics import build_topics

    monkeypatch.setattr('app.business_topics.topic_quotas', lambda sizes: [quota])
    chunks, vectors = [], []
    for section, (position, size, title, copies) in enumerate(observations, 1):
        for i in range(size + copies):
            body = f'正文 {section}-{i % size}'
            chunks.append(chunk(f'{section}-{i:03d}', f'5 维修 / 5.1.{section} {title}', body))
            vectors.append([position])
    return build_topics(chunks, vectors)['topics'][0]


def test_section_clustering_uses_deduplicated_fragment_weights(monkeypatch):
    # Unweighted, or weighted with the duplicates, 4 joins 0. With [85, 10, 5] it joins 10.
    repair = repair_groups(monkeypatch, 2, [(0, 85, '电机', 0), (4, 10, '电机', 0), (10, 5, '电机', 90)])
    assert [group['size'] for group in repair['clusters']] == [85, 15]
    assert [s['number'] for s in repair['clusters'][1]['sections']] == ['5.1.2', '5.1.3']


def test_section_with_only_cross_section_duplicates_stays_in_plan(monkeypatch):
    from app.business_topics import build_topics

    monkeypatch.setattr('app.business_topics.topic_quotas', lambda sizes: [2])
    chunks = [chunk('A', '5 维修 / 5.6.1 更换电机', '同一段'),
              chunk('B', '5 维修 / 5.6.2 更换电机', '同一段')]
    plan = build_topics(chunks, [[0], [1]])
    repair = plan['topics'][0]
    assert repair['initial_k'] == 2
    assert len(repair['clusters']) == 1
    assert repair['clusters'][0]['size'] == 1
    assert repair['clusters'][0]['sections'] == repair['sections']
    assert plan['assignments'][1]['cluster_id'] == f"{plan['topic_plan_version']}/06-01"


def test_consistent_small_group_is_preserved(monkeypatch):
    repair = repair_groups(monkeypatch, 3, [(0, 45, '电机', 0), (5, 2, '机械限位', 0), (10, 53, '齿轮箱', 0)])
    assert [group['size'] for group in repair['clusters']] == [45, 2, 53]
    assert repair['clusters'][1]['small_group'] is True
    assert repair['clusters'][1]['name'] == '机械限位'


def test_infeasible_quota_stops_without_exceeding_group_cap(monkeypatch):
    with pytest.raises(ValueError, match=r'维修配额不可行（5 题，2 个有效组）'):
        repair_groups(monkeypatch, 5, [(0, 20, '电机', 0), (10, 80, '齿轮箱', 0)])


def test_index_fragments_are_marked_excluded_and_do_not_suppress_spec_tables(monkeypatch):
    from app.business_topics import build_topics

    monkeypatch.setattr('app.business_topics.topic_quotas', lambda sizes: [2])
    rows = [
        chunk('A', '11 备件 / 11.1 备件列表和插图', '索引\n限位, 23电缆, 34机架, 45'),
        chunk('B', '11 备件 / 11.1 备件列表和插图', 'ABB Robotics\nTelephone: +1 615 237 6360'),
        chunk('C', '11 备件 / 11.1 备件列表和插图', '间隔=预计使用周期, 12；工作量=4,000；范围=负载, 10'),
        chunk('D', '9 参考信息 / 9.4 螺钉接头', '查阅规范并确认类型。'),
    ]
    plan = build_topics(rows, [[0], [1], [2], [3]])
    topic = plan['topics'][0]
    assert (topic['size'], topic['auxiliary_index_fragments']) == (2, 2)
    assert [(r['chunk_id'], r.get('fragment_kind'), r['cluster_id']) for r in plan['assignments'][:2]] == [
        ('A', '辅助索引片段', None), ('B', '辅助索引片段', None),
    ]


def test_small_fallback_merges_into_largest_peer_in_same_manual_unit():
    from app.business_topics import _group_topic

    sections = [
        {'number': number, 'title': title, 'manual_unit': (unit, unit_title)}
        for number, title, unit, unit_title in [
            ('5.2.1', '密封件', '5.2', '通用操作程序'),
            ('5.2.2', '下臂', '5.2', '通用操作程序'),
            ('5.2.3', '松闸按钮卡滞', '5.2', '通用操作程序'),
            ('5.5.1', '外壳', '5.5', '上臂和下臂'),
            ('5.6.1', '电机', '5.6', '电机'),
        ]
    ]
    _, groups = _group_topic(5, sections, np.array([[0.], [0.], [10.], [0.], [10.]]),
                             dict(zip((row['number'] for row in sections), [30, 30, 2, 30, 50])), 2)
    structure = groups[0]
    assert [s['number'] for s in structure['sections']] == ['5.2.1', '5.2.2', '5.2.3', '5.5.1']
    assert structure['homogeneity'] == .75
    assert structure['weighted_homogeneity'] == 90 / 92


def test_deepest_section_used_outside_repair_and_maintenance(monkeypatch):
    from app.business_topics import build_topics

    monkeypatch.setattr('app.business_topics.topic_quotas', lambda sizes: [1, 1])
    chunks = [chunk('I', '3 安装 / 3.1 机械 / 3.1.1 安装 / 3.1.1.1 提升', '甲'),
              chunk('M', '4 维护 / 4.2 计划 / 4.2.1 维护计划 / 4.2.1.1 说明', '乙')]
    installation, maintenance = build_topics(chunks, [[1, 1], [1, 0]])['topics']
    assert installation['sections'] == [{'number': '3.1.1.1', 'title': '提升'}]
    assert maintenance['sections'] == [{'number': '4.2.1', 'title': '维护计划'}]


def test_unclassified_small_group_uses_nearest_weighted_centroid_without_same_unit():
    from app.business_topics import _group_topic

    sections = [
        {'number': '5', 'title': '通用概述', 'manual_unit': ('5', '通用概述')},
        {'number': '5.2.1', 'title': '更换电机', 'manual_unit': ('5.2', '通用操作')},
        {'number': '5.2.2', 'title': '拆下电机', 'manual_unit': ('5.2', '通用操作')},
        {'number': '5.7.1', 'title': '更换齿轮箱', 'manual_unit': ('5.7', '齿轮箱')},
        {'number': '5.7.2', 'title': '拆下齿轮箱', 'manual_unit': ('5.7', '齿轮箱')},
    ]
    _, groups = _group_topic(5, sections, np.array([[2.6], [0.], [1.], [5.], [5.]]),
                             dict(zip((row['number'] for row in sections), [2, 45, 1, 26, 26])), 3)
    gearbox = next(group for group in groups if group['name'] == '齿轮箱维修')
    assert [member['number'] for member in gearbox['sections']] == ['5', '5.7.1', '5.7.2']
    assert gearbox['weighted_homogeneity'] == 52 / 54


def test_http_counts_only_frozen_question_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr('app.business_topics.topic_quotas', lambda sizes: [1, 2])
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
    from app.business_topics import index_topics, validate_import_groups

    plan = index_topics(tmp_path, 'IDX-test')
    repair_group = next(t for t in plan['topics'] if t['name'] == '维修')['clusters'][0]['id']
    questions = [
        {'id': 'A', 'test_category': 'ablation', 'paired_question': 'Q01', 'business_topic': '安全',
         'business_group': '05-02', 'evidence': [{'source_chunk_ids': ['S']}]},
        {'id': 'P', 'coverage_slot': 'Q01', 'test_category': 'positive', 'business_topic': '维修',
         'business_group': repair_group, 'evidence': [{'source_chunk_ids': ['C1', 'C2', 'S']}]},
        {'id': 'N', 'test_category': 'negative', 'business_topic': '安全', 'negative_subtype': 'safety_critical', 'evidence': []},
        {'id': 'N2', 'test_category': 'negative', 'business_topic': '知识库外', 'negative_subtype': 'prompt_injection', 'cross_model': True, 'evidence': []},
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
    assert outside['cross_model'] is True
    assert result['risk_counts'] == {'safety_critical': 1, 'prompt_injection': 1}
    assert result['group_version_mismatch'] is False
    assert result['topic_plan_version'] == plan['topic_plan_version']
    assert store.database_path.read_bytes() == before
    assert client.post(url).status_code == 405

    validate_import_groups([questions[1]], tmp_path)
    questions[1]['business_group'] = 'TP-obsolete/' + repair_group.split('/')[1]
    with pytest.raises(ValueError, match='Q01 分组版本已变化，需要重新映射'):
        validate_import_groups([questions[1]], tmp_path)
    save('E')
    stale = client.get(url).json()
    assert stale['group_version_mismatch'] is True
    assert stale['topics'][1]['questions'] == {'positive': 0, 'ablation': 0, 'negative': 0}
    assert all(g['questions'] is None for g in stale['topics'][1]['clusters'])


def test_101f_dual_threshold_falls_back_to_manual_headings():
    from app.business_topics import _group_topic

    sections = [
        {'number': '5.3.1', 'title': '电缆', 'manual_unit': ('5.3', '电缆线束')},
        {'number': '5.3.2', 'title': 'SMB', 'manual_unit': ('5.3', '电缆线束')},
        {'number': '5.4.1', 'title': '底座', 'manual_unit': ('5.4', '摆动部和底座')},
    ]
    _, groups = _group_topic(5, sections, np.array([[0.], [1.], [2.]]),
                             {'5.3.1': 20, '5.3.2': 15, '5.4.1': 65}, 1)
    assert [group['name'] for group in groups] == ['电缆线束', '摆动部和底座']
    assert all(group['homogeneity'] == group['weighted_homogeneity'] == 1 for group in groups)
