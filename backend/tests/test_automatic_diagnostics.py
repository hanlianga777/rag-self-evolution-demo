"""Offline diagnostic evidence fixtures; no imports of app.main or live stores."""
import unittest
from copy import deepcopy
import pytest
from app.diagnostics import diagnostic_view


def recall_case():
    source={'chunk_id':'covered','document_id':'manual','product':'device','chunk_text':'检查外壳'}
    missing={**source,'chunk_id':'missing','chunk_text':'检查传感器是否脏污'}
    final={**source,'content':source['chunk_text'],'matched_child_ids':['covered']}
    case={'test_category':'positive','passed':False,'primary_root_cause':'Unknown','diagnosis':{'status':'needs_review'},
        'standard_evidence':['检查外壳','检查传感器是否脏污'],'model_answer':'请检查外壳。','failure_tags':['Generation Failure'],
        'judge_result':{'correctness':2,'completeness':.5,'missing_points':['未列出“检查传感器是否脏污”。'],
            'evidence_sufficiency':{'status':'insufficient','source_applicable':True,'fact_support':[{'fact':'检查外壳','chunk_id':'covered','quote':'检查外壳'}]}},
        'programmatic_metrics':{'claim_assessment':{'pending':[]},'evidence_coverage':{'required_chunk_ids':['covered','missing']},
            'evidence_sufficiency':{'sufficient':False,'source_applicable':True,'unresolved_conflicts':[],
                'facts':[{'fact':'检查外壳','locations':[{'chunk_id':'covered'}]},{'fact':'检查传感器是否脏污','locations':[]}],
                'judge_support':[{'fact':'检查外壳','chunk_id':'covered','quote':'检查外壳'}]},
            'retrieval_trace':{'status':'completed','candidate_stage':'post_metadata_filter_fusion_candidate_cap_pre_rerank',
                'corpus_fingerprint':{'corpus':'one'},'candidates':[final],'reranked':[final],'final':[final]}}}
    return case,[source,missing]


class AutomaticDiagnosticTests(unittest.TestCase):
    def test_saved_text_ignores_current_corpus_and_original_case_is_unchanged(self):
        case,chunks=recall_case();before=deepcopy(case)
        from unittest.mock import patch
        with patch('app.diagnostics._current_corpus',side_effect=AssertionError('live KB must not be read')):
            view=diagnostic_view(case,corpus_chunks=[],corpus_fingerprint='changed')
        self.assertEqual(view['diagnosis_category'],'检索层问题')
        self.assertTrue(view['target_eligible'])
        self.assertEqual(view['retrieval_failure_stage'],'candidate_recall')
        self.assertEqual(case,before)

    def test_explicit_empty_stages_are_different_from_missing_stages(self):
        case,_=recall_case();trace=case['programmatic_metrics']['retrieval_trace']
        trace.update(candidates=[],final=[])
        self.assertEqual(diagnostic_view(case)['diagnosis_category'],'检索层问题')
        trace['candidates']=None
        self.assertEqual(diagnostic_view(case)['diagnosis_category'],'记录缺失')
        trace['candidates']=[]
        for status in ('failed','running','not_collected'):
            trace['status']=status
            self.assertEqual(diagnostic_view(case)['diagnosis_category'],'记录缺失')

    def test_candidate_missing_dominates_incorrect_answer_and_saved_cause(self):
        case,_=recall_case();case.update(model_answer='无需检查外壳。',primary_root_cause='Generation')
        case['judge_result'].update(behavior_pass=False,unsupported_claims=['无需检查外壳。'])
        self.assertEqual(diagnostic_view(case)['diagnosis_category'],'检索层问题')

    def test_saved_pending_or_disputed_status_does_not_hide_text_based_result(self):
        case,_=recall_case()
        for status in ('confirmed','needs_review','disputed'):
            case['diagnosis']['status']=status
            case['programmatic_metrics']['claim_assessment']['pending']=[{'claim':'未闭合的附加主张'}]
            self.assertEqual(diagnostic_view(case)['diagnosis_category'],'检索层问题')

    def test_final_source_ids_can_differ_and_parent_expansion_is_plain_saved_text(self):
        case,chunks=recall_case();trace=case['programmatic_metrics']['retrieval_trace']
        trace['candidates'].append({'chunk_id':'unrelated-id','content':chunks[1]['chunk_text']})
        trace['final']=[{'chunk_id':'parent','content':'父段落：检查外壳，检查传感器是否脏污。'}]
        trace['parent_expand']=True
        self.assertEqual(diagnostic_view(case)['diagnosis_category'],'生成层问题')

class SavedEvidenceCompatibilityTests(unittest.TestCase):
    def test_legacy_frozen_acceptable_evidence_supplies_saved_quotes(self):
        from app.diagnostics import standard_evidence
        question = {'acceptable_evidence': [{'source_chunk_ids': ['frozen-child'], 'evidence_key_points': ['先停止设备再检查。']}]}
        self.assertEqual(standard_evidence(question), ['先停止设备再检查。'])


def generation_case(answer, evidence, *, final=None, judge=None, **question):
    return {
        'question_id': 'Q01', 'passed': False, 'test_category': 'positive',
        'model_answer': answer, 'standard_evidence': [evidence], **question,
        'judge_result': {'verdict': 'FAIL', **(judge or {})},
        'programmatic_metrics': {'retrieval_trace': {
            'candidates': [{'content': evidence}],
            'final': [{'content': final or evidence}],
        }},
    }


@pytest.mark.parametrize('quote, kind, description, expected', [
    ('项目=检查密封圈；周期=12个月', 'contradiction', '维护周期填成36个月', '表格读取或归类错误'),
    ('检查密封圈 | 12个月', 'unsupported', '多列了两个项目', '表格读取或归类错误'),
    ('每12个月检查密封圈', 'contradiction', '维护周期填成36个月', '答案出现幻觉'),
    ('项目=检查密封圈；周期=12个月', None, '维护周期填成36个月', '答案出现幻觉'),
    ('项目=检查密封圈；周期=12个月', 'contradiction', '答成润滑密封圈 [1]', '答案出现幻觉'),
    ('项目=检查密封圈；周期=12个月', 'omission', '将36个月的项目归入12个月', '答案出现幻觉'),
])
def test_table_issue_requires_table_evidence_and_a_quantitative_issue(quote, kind, description, expected):
    answer = '请润滑密封圈 [1]。'
    issue = {'failure_kind': kind, 'description': description, 'answer_quotes': [answer]}
    judge = {'hallucination': True, 'reason': description, 'issues': [issue] if kind else []}
    view = diagnostic_view(generation_case(answer, quote, judge=judge))
    assert view['subfeature'] == expected
    if expected == '表格读取或归类错误':
        assert view['display_subtype'] == expected
        assert 'TableCheck' not in view['tuning_directions']
        assert 'TableCheck' not in view['repair_hint']


@pytest.mark.parametrize('quote, reason, expected', [
    ('项目=更换密封圈；周期=36个月', '把每 36 个月的更换项目算进了每 12 个月的清单。', '表格读取或归类错误'),
    ('检查密封圈 | 12个月', '维护清单多列了四项。', '表格读取或归类错误'),
    ('每36个月更换密封圈', '把每36个月的更换项目算进了每12个月的清单。', '答案出现幻觉'),
    ('项目=更换密封圈；周期=36个月', '更换周期错写成12个月。', '答案出现幻觉'),
    ('检查密封圈 | 12个月', '多列了润滑步骤 13 [1]。', '答案出现幻觉'),
])
def test_table_reason_fallback_requires_table_quantity_and_classification(quote, reason, expected):
    judge = {'hallucination': True, 'reason': reason, 'issues': []}
    view = diagnostic_view(generation_case('请润滑密封圈 [1]。', quote, judge=judge))
    assert view['subfeature'] == expected
    if expected == '表格读取或归类错误':
        assert view['display_subtype'] == expected
        assert 'TableCheck' not in view['tuning_directions']


@pytest.mark.parametrize('answer, judge_behavior', [
    ('无法确认维护清单。', None),
    ('资料不足。', 'refusal'),
])
def test_table_reason_fallback_preserves_refusal(answer, judge_behavior):
    judge = {'reason': '维护清单少列了4项。', 'issues': [], 'answer_behavior': judge_behavior}
    view = diagnostic_view(generation_case(answer, '检查密封圈 | 12个月', judge=judge))
    assert view['subfeature'] == '模型过度拒绝（已检索到相关切片仍拒答）'


@pytest.mark.parametrize('answer, expected', [
    ('滤芯每月检查。说明书里没有给出“更换滤芯”的具体步骤。', '错误否定（资料有却说没有）'),
    ('滤芯每月检查，手册未提到更换滤芯的方法。', '错误否定（资料有却说没有）'),
    ('滤芯每月检查。说明书里未给出更换电池的步骤。', '答案出现幻觉'),
    ('滤芯每月检查。说明书里未给出更换电池的步骤，无法确认这一部分。', '答案出现幻觉'),
    ('**资料核对结果**\n说明书里没有给出更换滤芯的方法。建议联系售后。', '模型过度拒绝（已检索到相关切片仍拒答）'),
])
def test_wrong_denial_requires_substantive_answer_and_matching_final_object(answer, expected):
    case = generation_case(answer, '滤芯每月检查', final='滤芯每月检查。更换滤芯见第80页。',
                           judge={'hallucination': True})
    view = diagnostic_view(case)
    assert view['subfeature'] == expected
    if expected == '错误否定（资料有却说没有）':
        assert view['display_subtype'] == expected
        assert 'Grounded' not in view['tuning_directions']


@pytest.mark.parametrize('question, missing, saved_check, expected', [
    ('多久检查？怎么更换？', '更换前先关阀', True, '漏子问'),
    ('请分别说明检查频率和更换要求。', '更换前先关阀', False, '漏子问'),
    ('多久检查？怎么更换？', '可使用扳手', True, '召回成功但答案漏要点'),
    ('多久检查？怎么更换？', '可使用扳手', False, '召回成功但答案漏要点'),
    ('多久检查一次？', '更换前先关阀', True, '召回成功但答案漏要点'),
])
def test_missed_subquestion_requires_multiple_questions_and_a_required_omission(question, missing, saved_check, expected):
    judge = ({'checks': [{'requirement': missing, 'met': False}]} if saved_check
             else {'completeness_reason': f'回答遗漏了“{missing}”这一要点。'})
    case = generation_case('每月检查。', '更换前先关阀', judge=judge, question=question,
                           reference_answer='1. 每月检查\n2. 更换前先关阀\n（补充）可使用扳手')
    view = diagnostic_view(case)
    assert view['subfeature'] == expected
    if expected == '漏子问':
        assert view['display_subtype'] == expected
        assert 'Stepwise' not in view['tuning_directions']


def test_round_one_agent_receives_the_current_diagnosis_and_action():
    from app.agent_inputs import prepare_baseline_rows
    from app.optimization import build_agent_prompt
    from app.policy import DEFAULT_PIPELINE_CONFIG
    from app.rules import AGENT

    case = generation_case('滤芯每月检查。说明书未提到更换滤芯。', '滤芯每月检查',
                           final='滤芯每月检查。更换滤芯见第80页。')
    rows = prepare_baseline_rows(None, [{'id': 1, 'question_id': 'Q01', 'result': case}])
    system, prompt = build_agent_prompt(rows, DEFAULT_PIPELINE_CONFIG, [], [], AGENT['candidate_labels'],
                                       round_number=1)
    assert prompt['bad_case_groups'] == [
        {'layer': '生成层问题', 'subtype': '错误否定（资料有却说没有）', 'question_ids': ['Q01'], 'count': 1}
    ]
    assert 'Grounded' not in system
