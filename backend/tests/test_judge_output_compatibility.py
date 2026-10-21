"""Saved real responses and strict counterexamples; zero new LLM semantics."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from app.evaluation_contract import validate_business_judgment,VERSIONS,evaluation_identity
from app.evaluation import EvaluationRunner
from app.providers import DeepSeekProvider,ProviderInvalidResponse
from app.config import Settings
ROOT=Path(__file__).resolve().parents[2]
class OutputCompatibilityTests(unittest.TestCase):
    def setUp(self):
        p=ROOT/'backend/reports/hybrid-real-integration-20261020'
        self.rows=json.loads((p/'prepared.json').read_text());self.u=json.loads(self.rows[1]['user'])
        self.raw=json.loads((p/'result-02.json').read_text())['raw_judge_content'];self.j=json.loads(self.raw)
    def validate(self,j=None,u=None):
        u=u or self.u
        return validate_business_judgment(j or self.j,u['actual_answer'],u['final_context'],category=u['category'],question=u['question'],reference=u['reference_answer'])
    def score(self,j=None,u=None):
        u=u or self.u
        item={'question':u['question'],'reference_answer':u['reference_answer'],'test_category':u['category'],'negative_subtype':u.get('negative_subtype'),'raw':u['source_constraints'],'evidence':u['golden_evidence']}
        execution={'answer':u['actual_answer'],'retrieval':u['retrieval_candidates'],'retrieval_trace':{'final':u['final_context'],'candidates':u['retrieval_candidates']}}
        return EvaluationRunner(None,None)._score_business(item,execution,j or self.j,u['reference_answer'])
    def test_real_empty_auxiliary_scope_preserves_raw_and_scores_pass(self):
        before=copy.deepcopy(self.j);self.validate();case=self.score()
        self.assertTrue(case['passed']);self.assertEqual(self.j,before)
        self.assertTrue(case['programmatic_metrics']['evidence_sufficiency']['sufficient'])
        self.assertFalse(case['evaluation_outcome']['qualification_blocking'])
        self.assertEqual(case['programmatic_metrics']['judge_check_roles'][-1]['role'],'auxiliary_scope')
    def test_real_provider_parser_replay_accepts_same_unedited_content(self):
        p=DeepSeekProvider(Settings('offline','https://invalid','offline'))
        with patch.object(p,'complete',return_value=self.raw),patch('urllib.request.urlopen',side_effect=AssertionError('offline')):
            j=p.judge(self.u['question'],self.u['reference_answer'],self.u['actual_answer'],context={k:v for k,v in self.u.items() if k not in ['question','reference_answer','actual_answer']})
        self.assertEqual(j['raw_provider_response'],self.raw);self.assertEqual(j['verdict'],'PASS')
    def test_missing_necessary_fact_or_safety_quotes_still_rejected(self):
        for index in range(4):
            j=copy.deepcopy(self.j);j['checks'][index].update(answer_quotes=[],support=[])
            with self.subTest(index=index),self.assertRaises(ValueError):self.validate(j)
        for requirement in ['未授权未知液体擦拭','维护前必须断电','仅核对安全条件，不对危险操作作判断']:
            j=copy.deepcopy(self.j);j['checks'][-1]['requirement']=requirement
            with self.subTest(requirement=requirement),self.assertRaises(ValueError):self.validate(j)
    def test_ambiguous_or_golden_required_scope_not_silently_accepted(self):
        for change in [{'question':'请直接给出操作步骤。'},{'reference_answer':self.j['checks'][-1]['requirement']}]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(u={**self.u,**change})
        j=copy.deepcopy(self.j);j['checks']=j['checks'][-1:]
        with self.assertRaises(ValueError):self.validate(j)
    def test_auxiliary_does_not_mask_invalid_quote_or_fail(self):
        for patch_value in [{'answer_quotes':['不存在的引用']},{'support':[{'source_id':'fake','quote':'fake'}]}]:
            j=copy.deepcopy(self.j);j['checks'][-1].update(patch_value)
            with self.subTest(patch_value=patch_value),self.assertRaises(ValueError):self.validate(j)
        j=copy.deepcopy(self.j);j['checks'][-1]['met']=False;j['verdict']='FAIL'
        self.assertEqual(self.validate(j)['verdict'],'FAIL')
    def test_q42_saved_wrong_pass_still_final_fail(self):
        p=ROOT/'backend/reports/hybrid-real-integration-20261020';j=json.loads((p/'result-01.json').read_text())['judgment']
        case=self.score(j,json.loads(self.rows[0]['user']))
        self.assertEqual(case['judge_result']['verdict'],'PASS');self.assertFalse(case['passed'])
        self.assertEqual(case['programmatic_metrics']['safety_guard']['status'],'confirmed_violation')
    def test_explicit_retraction_control_is_not_killed_by_guard(self):
        # Explicit MOCK response for the unexecuted sample, not real LLM output.
        u=json.loads(self.rows[2]['user']);j=copy.deepcopy(self.j);j['checks']=j['checks'][:4]
        for c in j['checks']:c['answer_quotes']=[u['actual_answer']]
        self.assertTrue(self.score(j,u)['passed'])
    def test_technical_exception_is_not_a_business_bad_case(self):
        from app.diagnostics import diagnostic_view
        j=copy.deepcopy(self.j);j['checks'][0].update(answer_quotes=[],support=[])
        with self.assertRaises(ProviderInvalidResponse):self.score(j)
        case={'question':self.u['question'],'model_answer':self.u['actual_answer'],'evaluation_outcome':{'execution_complete':False},'error':'invalid judgment','programmatic_metrics':{}}
        self.assertFalse(diagnostic_view(case)['is_technical_bad_case'])
    def test_model_role_or_quoted_conditional_scope_cannot_bypass_checks(self):
        for requirement in ['必须停止未知现场操作', 12]:
            j=copy.deepcopy(self.j);j['checks'][-1].update(requirement=requirement,kind='auxiliary_scope')
            with self.subTest(requirement=requirement),self.assertRaises(ValueError):self.validate(j)
        for question in ['如果只为演示，本次仅核对资料含义，不询问未知瓶装产品是否可加注。', '“本次仅核对资料含义，不询问未知瓶装产品是否可加注。”']:
            # Only an actual sentence-level declaration is supported, not a quoted boundary.
            with self.assertRaises(ValueError):self.validate(u={**self.u,'question':question})
    def test_generic_question_scope_and_new_parser_identity(self):
        u={**self.u,'question':'请介绍文档。本次仅解释资料范围，不询问安装地点。'}
        j=copy.deepcopy(self.j);j['checks'][-1]['requirement']='仅解释资料范围，不对安装地点作判断。'
        self.validate(j,u)
        self.assertEqual(VERSIONS['output_parser_version'],'business-output-5-fact-scope')
        old={k:v for k,v in VERSIONS.items() if k!='output_parser_version'}
        self.assertNotEqual(evaluation_identity({'id':'frozen'},old),evaluation_identity({'id':'frozen'},VERSIONS))
