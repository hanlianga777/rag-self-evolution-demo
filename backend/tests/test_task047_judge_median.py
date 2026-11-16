"""2026-11-16 晚用户同意：Judge 每题固定判 3 次取中间值；负向题多数决定；边界分标记。纯逻辑，不连模型。"""
import pytest

from app.rubric_judge import aggregate_samples, borderline, reuse_parts, rubric_verdict


def pos(c, f, comp, tag=''):
    return {'correctness': c, 'correctness_reason': f'正确性{tag}', 'faithfulness': f, 'faithfulness_reason': f'忠实度{tag}',
            'completeness': comp, 'completeness_reason': f'完整性{tag}', 'over_refusal': False, 'hallucination': False}


def neg(ok, unsafe, tag=''):
    return {'behavior_correct': ok, 'behavior_reason': f'行为{tag}', 'safety_violation': unsafe, 'safety_reason': f'安全{tag}'}


def test_median_per_dimension_and_reason_follows_median():
    result = aggregate_samples('positive', [pos(80, 100, 60, 'a'), pos(100, 80, 80, 'b'), pos(80, 100, 80, 'c')])
    assert (result['correctness'], result['faithfulness'], result['completeness']) == (80, 100, 80)
    assert result['completeness_reason'] == '完整性b'      # 第一次等于中间值的判分
    assert result['aggregation'] == {'version': 'median-of-n-1', 'count': 3, 'unanimous': False}
    assert len(result['samples']) == 3
    assert rubric_verdict('positive', result)['passed'] is True


def test_one_outlier_cannot_flip_verdict():
    result = aggregate_samples('positive', [pos(100, 100, 100), pos(100, 100, 40), pos(100, 100, 100)])
    assert result['completeness'] == 100 and rubric_verdict('positive', result)['passed'] is True


def test_negative_majority():
    result = aggregate_samples('negative', [neg(True, False, 'a'), neg(False, True, 'b'), neg(True, False, 'c')])
    assert result['behavior_correct'] is True and result['safety_violation'] is False
    assert result['behavior_reason'] == '行为a' and result['safety_reason'] == '安全a'
    assert rubric_verdict('negative', result)['passed'] is True


def test_even_count_rejected():
    with pytest.raises(ValueError):
        aggregate_samples('positive', [pos(80, 80, 80), pos(80, 80, 80)])


def test_borderline_flags():
    unanimous_safe = aggregate_samples('positive', [pos(100, 100, 100)] * 3)
    assert borderline('positive', unanimous_safe) is False
    near_line = aggregate_samples('positive', [pos(100, 100, 80)] * 3)      # 完整性 80，门槛 75，差 5 < 20
    assert borderline('positive', near_line) is True
    split_negative = aggregate_samples('negative', [neg(True, False), neg(True, False), neg(False, False)])
    assert borderline('negative', split_negative) is True


def test_reuse_key_is_per_sample_and_distinct():
    args = ('问', '参考', '答', 'positive', None, ['资料'], {'thinking': 'low'})
    keys = [reuse_parts(*args, sample) for sample in (1, 2, 3)]
    assert len({str(k) for k in keys}) == 3
    assert reuse_parts(*args) == keys[0][:-2]


def test_ai_service_judges_three_times(monkeypatch):
    from app import ai_service
    from app.rubric_judge import RUBRIC_VERSION
    calls = []
    outputs = iter([pos(100, 100, 60), pos(100, 100, 80), pos(100, 100, 80)])
    service = ai_service.AiService.__new__(ai_service.AiService)
    monkeypatch.setattr(ai_service.AiService, '_judge_uncached', lambda self, *a, **k: calls.append(1) or {**next(outputs), 'token_usage': [{'n': 1}], 'estimated_cost': 0.001})
    monkeypatch.setenv('JUDGE_SAMPLES', '3')
    result = ai_service.AiService.judge.__wrapped__(service, '问', '参考', '答', 'positive', context={'contract_version': RUBRIC_VERSION, 'final_texts': ['资料']}) \
        if hasattr(ai_service.AiService.judge, '__wrapped__') else service.judge('问', '参考', '答', 'positive', context={'contract_version': RUBRIC_VERSION, 'final_texts': ['资料']})
    assert len(calls) == 3
    assert result['completeness'] == 80 and result['aggregation']['count'] == 3
    assert len(result['token_usage']) == 3 and result['estimated_cost'] == pytest.approx(0.003)


def test_enhancement_effect_counts_only_new_hits():
    from app.retrieval import enhancement_effect
    from app.evaluation import enhancement_summary
    sources = [{'chunk_ids': {'vector': ['a', 'b'], 'bm25': ['b']}},          # 原问题
               {'chunk_ids': {'vector': ['b', 'c'], 'bm25': []}},             # multi_query 第 1 条
               {'chunk_ids': {'vector': ['d'], 'bm25': ['e']}}]               # hyde
    effect = enhancement_effect(sources, ['multi_query', 'hyde'], [{'chunk_id': x} for x in 'abcde'],
                                [{'chunk_id': 'a', 'matched_child_ids': ['a', 'c']}, {'chunk_id': 'e'}])
    assert effect['by_method']['multi_query'] == {'queries': 1, 'new_candidates': 1, 'new_final_hits': 1}
    assert effect['by_method']['hyde'] == {'queries': 1, 'new_candidates': 2, 'new_final_hits': 1}
    assert effect['new_final_hits'] == 2 and effect['effective'] is True
    none = enhancement_effect(sources[:1], [], [{'chunk_id': 'a'}], [{'chunk_id': 'a'}])
    assert none['enabled'] == [] and none['effective'] is False
    case = {'programmatic_metrics': {'retrieval_trace': {'enhancement': effect}}}
    summary = enhancement_summary([case, {'programmatic_metrics': {}}])
    assert summary['by_method']['hyde']['effective_questions'] == 1 and summary['effective_questions'] == 1
