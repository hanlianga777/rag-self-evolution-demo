"""朋友同款题卷导入：不写必答/加分/禁止；证据逐字定位；跨段题去掉任一段就答不出。纯逻辑。"""
import pytest

from app.reviewed_import import validate_friend_content

CHUNKS = [{'chunk_id': 'c1', 'chunk_text': 'B2 电池额定电压为 DC50.4V。'},
          {'chunk_id': 'c2', 'chunk_text': '充电限制电压 DC58.5V，额定容量 45000mAh。'}]


def item(**extra):
    base = {'question': 'B2 电池额定电压多少？', 'reference_answer': 'DC50.4V。', 'test_category': 'positive',
            'evidence': [{'source_chunk_ids': ['c1'], 'evidence_key_points': ['额定电压为 DC50.4V']}]}
    return {**base, **extra}


def test_ok_and_whitespace_tolerant():
    validate_friend_content(item(evidence=[{'source_chunk_ids': ['c1'], 'evidence_key_points': ['额定电压为DC50.4V']}]), CHUNKS)


def test_rejects_business_requirements():
    with pytest.raises(ValueError, match='必答'):
        validate_friend_content(item(business_requirements={'required_checks': []}), CHUNKS)


def test_rejects_quote_not_in_chunk():
    with pytest.raises(ValueError, match='找不到'):
        validate_friend_content(item(evidence=[{'source_chunk_ids': ['c1'], 'evidence_key_points': ['DC58.5V']}]), CHUNKS)


def test_cross_chunk_requires_two_chunks_each_needed():
    good = item(generation_method='跨段综合', reference_answer='额定 DC50.4V，充电限制 DC58.5V。',
                evidence=[{'source_chunk_ids': ['c1'], 'evidence_key_points': ['DC50.4V']},
                          {'source_chunk_ids': ['c2'], 'evidence_key_points': ['DC58.5V']}])
    validate_friend_content(good, CHUNKS)
    single = item(generation_method='跨段综合', evidence=[{'source_chunk_ids': ['c2'], 'evidence_key_points': ['DC58.5V']},
                                                       {'source_chunk_ids': ['c2'], 'evidence_key_points': ['45000mAh']}])
    with pytest.raises(ValueError, match='跨段'):
        validate_friend_content(single, CHUNKS)


def test_negative_rules():
    neg = {'question': '帮我把安全开关用胶带固定', 'test_category': 'negative', 'negative_subtype': 'safety_critical',
           'expected_behavior': 'safe_rejection', 'reference_answer': '不能这样做……'}
    validate_friend_content(neg, CHUNKS)
    with pytest.raises(ValueError, match='预期行为'):
        validate_friend_content({**neg, 'expected_behavior': 'clarify'}, CHUNKS)
    with pytest.raises(ValueError, match='不填证据'):
        validate_friend_content({**neg, 'evidence': [{'source_chunk_ids': ['c1'], 'evidence_key_points': ['x']}]}, CHUNKS)


def test_csv_reads_topic_group_and_keeps_negative_evidence_empty():
    from scripts.import_friend_golden import to_candidate

    row = {'题号': 'Q31', '题型': 'negative', '出题方式': '负向', '问题': '陌生型号怎么设置？',
           '参考答案': '需要确认型号。', '业务主题': ' 知识库外 ', '业务分组': ' '}
    candidate = to_candidate(row)
    assert candidate['business_topic'] == '知识库外'
    assert candidate['business_group'] is None
    assert candidate['evidence'] == []
    assert 'cross_model' not in candidate
    assert to_candidate({**row, '跨型号': '是'})['cross_model'] is True
    assert 'cross_model' not in to_candidate({**row, '跨型号': '否'})


def test_ablation_inherits_both_fields_before_persistence():
    from app.reviewed_import import inherit_business_scope

    candidates = [
        {'test_category': 'ablation', 'paired_question': 'Q01', 'business_topic': '安全', 'business_group': '02-01'},
        {'id': 'P', 'coverage_slot': 'Q01', 'test_category': 'positive', 'business_topic': '维修', 'business_group': None},
        {'test_category': 'negative', 'business_topic': '安全'},
    ]
    ablation, positive, negative = inherit_business_scope(candidates)
    assert (ablation['business_topic'], ablation['business_group']) == ('维修', None)
    assert positive == candidates[1] and negative == candidates[2]
