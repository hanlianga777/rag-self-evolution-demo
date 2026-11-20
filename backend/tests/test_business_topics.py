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
    assert safety['clusters'] == []
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
    assert plan['assignments'][1]['cluster_id'] == '06-01'


def test_small_group_merges_into_nearest_weighted_centroid(monkeypatch):
    # Initial groups are [0, 1], [2.6], [5]. Only the weighted center of [0, 1] is farther from 2.6 than 5 is.
    repair = repair_groups(monkeypatch, 3, [
        (0, 45, '电机', 0), (1, 1, '电机', 0), (2.6, 2, '电机', 0), (5, 52, '电机', 0),
    ])
    assert repair['initial_k'] == 3
    assert [group['size'] for group in repair['clusters']] == [46, 54]
    assert [s['number'] for s in repair['clusters'][1]['sections']] == ['5.1.3', '5.1.4']
    assert [group['quota'] for group in repair['clusters']] == [1, 2]


def test_small_group_at_exactly_five_percent_stays(monkeypatch):
    repair = repair_groups(monkeypatch, 3, [(0, 45, '电机', 0), (5, 5, '电机', 0), (10, 50, '电机', 0)])
    assert [group['size'] for group in repair['clusters']] == [45, 5, 50]


@pytest.mark.parametrize(('position', 'expected_sizes'), [(4, [40, 40, 20]), (2, [60, 20, 20])])
def test_large_mixed_group_is_split_only_once(monkeypatch, position, expected_sizes):
    repair = repair_groups(monkeypatch, 2, [
        (0, 20, '电机', 0), (1, 20, '电机' if position == 4 else '机械限位', 0),
        (position, 20, '齿轮箱', 0), (8, 20, '齿轮箱', 0), (20, 20, '电缆', 0),
    ])
    assert repair['initial_k'] == 2
    assert [group['size'] for group in repair['clusters']] == expected_sizes


def test_only_oversized_mixed_group_is_split(monkeypatch):
    repair = repair_groups(monkeypatch, 2, [
        (0, 52, '电机', 0), (10, 24, '齿轮箱', 0), (11, 24, '机械限位', 0),
    ])
    assert [group['size'] for group in repair['clusters']] == [52, 24, 24]


def test_oversized_group_split_uses_fragment_weights(monkeypatch):
    repair = repair_groups(monkeypatch, 2, [
        (0, 68, '电机', 0), (4, 8, '齿轮箱', 0), (10, 4, '机械限位', 0), (30, 20, '电缆', 0),
    ])
    assert [group['size'] for group in repair['clusters']] == [68, 12, 20]


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
    (['工作范围', '空间限制', '以机械方式限制工作范围'], ('工作范围限制', 1, False)),
    (['机器人退役介绍', '废弃机器人', '环境信息'], ('停用与废弃', 1, False)),
    (['适用标准', '单位转换', '重量规格', '标准工具包', '特殊工具'], ('参考资料与工具', 1, False)),
    (['松闸', '按钮卡滞', '制动器'], ('制动闸', 1, False)),
    (['载荷', '负载', '转动惯量', '加速度', '速度', '性能', 'ISO 9283'], ('负载与性能', 1, False)),
    (['技术数据', '型号', '关于 IRB 1200'], ('产品与技术数据', 1, False)),
    (['同步标记', '检查同步位置'], ('同步位置检查', 1, False)),
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
