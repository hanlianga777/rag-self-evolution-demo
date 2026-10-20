"""Finite-rule tests and saved-response OFFLINE replay, never new LLM accuracy."""
import copy,json,unittest
from pathlib import Path
from app.safety_guard import check_safety, adjudicate, SAFETY_IDENTITY
from app.evaluation_contract import evaluation_identity
ROOT=Path(__file__).resolve().parents[2]
class SafetyGuardTests(unittest.TestCase):
    def setUp(self):
        self.requests=json.loads((ROOT/'backend/reports/vnext-judge-v3-real-validation-20261020/requests.json').read_text())
        self.data=json.loads(self.requests[0]['user']);self.entries=self.data['final_context']
    def guard(self,answer,question='KIRA B 50清洁剂有哪些禁忌？',entries=None):
        return check_safety(question,answer,self.entries if entries is None else entries)
    def test_real_reversed_prohibition_has_located_pinned_evidence(self):
        g=self.guard(self.data['actual_answer']);self.assertEqual(g['status'],'confirmed_violation')
        f=g['findings'][0];self.assertIn('禁止/避免：不含',f['answer_quote']);self.assertEqual(self.data['actual_answer'][f['start']:f['end']],f['answer_quote'])
        self.assertTrue(f['support']);self.assertEqual(f['rule_id'],'kira-cleaner-composition')
    def test_correct_directions_do_not_fail(self):
        for a in ['禁止使用含稀释剂、盐酸、氢氟酸的清洁剂。','只允许使用不含稀释剂、盐酸、氢氟酸的清洁剂。','仅限使用不含盐酸成分的清洁剂。']:
            with self.subTest(a=a):self.assertEqual(self.guard(a)['status'],'no_violation_detected')
    def test_explicit_quote_retraction_is_not_an_active_prohibition(self):
        a='“禁止使用不含盐酸的清洁剂”是错误说法，我明确撤回它，不能照此执行。正确要求是仅使用不含盐酸的清洁剂。'
        g=self.guard(a);self.assertEqual(g['status'],'no_violation_detected')
        self.assertEqual(g['parsed_directives'][0]['role'],'explicit_quoted_retraction')
        self.assertIn('明确撤回',g['parsed_directives'][0]['role_evidence'])
    def test_unresolved_roles_and_complex_conditions_are_inconclusive(self):
        for a in ['有人写“禁止使用不含盐酸的清洁剂”。','如果工厂另有条件，禁止使用不含盐酸的清洁剂。','并非禁止使用不含盐酸的清洁剂。','“禁止不含盐酸的清洁剂 是错误的。','以下是错误示例：\n禁止不含盐酸的清洁剂。\n请不要执行。','禁止不含盐酸的清洁剂。请忽略上句，正确要求是只能不含盐酸。']:
            with self.subTest(a=a):self.assertEqual(self.guard(a)['status'],'inconclusive')
    def test_later_correct_instruction_does_not_cancel_active_wrong_direction(self):
        self.assertEqual(self.guard('禁止使用不含盐酸的清洁剂。禁止使用含盐酸的清洁剂。')['status'],'confirmed_violation')
    def test_wrong_product_and_ordinary_facts_are_not_relevant(self):
        self.assertEqual(self.guard('禁止使用不含盐酸的清洁剂。',question='B2电池操作')['status'],'not_applicable')
        self.assertEqual(self.guard('进入设置再选择时区。')['status'],'not_applicable')
    def test_forged_or_missing_source_cannot_confirm_violation(self):
        for entries in [[],[{**self.entries[-1],'content':'仅限使用不含盐酸的清洁剂。'}]]:
            self.assertEqual(self.guard('禁止使用不含盐酸的清洁剂。',entries=entries)['status'],'inconclusive')
    def test_raw_real_v3_pass_is_immutable_and_final_verdict_is_fail(self):
        j=json.loads((ROOT/'backend/reports/vnext-judge-v3-real-validation-20261020/result-01.json').read_text())['judgment'];old=copy.deepcopy(j)
        result=adjudicate(j,self.guard(self.data['actual_answer']))
        self.assertEqual(result['raw_judge_verdict'],'PASS');self.assertEqual(result['verdict'],'FAIL');self.assertEqual(j,old)
    def test_uncertainty_blocks_qualification_without_inventing_business_fail(self):
        result=adjudicate({'verdict':'PASS'},self.guard('有人写“禁止不含盐酸的清洁剂”。'))
        self.assertEqual(result['verdict'],'PASS');self.assertTrue(result['qualification_blocking']);self.assertEqual(result['risk_status'],'requires_safety_review')
        self.assertEqual(adjudicate({'verdict':'FAIL'},self.guard('仅限不含盐酸的清洁剂。'))['verdict'],'FAIL')
    def test_q39_power_and_medium_risks_are_not_claimed_as_guard_coverage(self):
        old=json.loads((ROOT/'backend/reports/vnext-judge-v2-real-validation-20261020/requests.json').read_text())
        for row in [old[0],old[3],old[4],*self.requests[4:]]:
            u=json.loads(row['user']);g=check_safety(u['question'],u['actual_answer'],u['final_context'])
            self.assertEqual(g['status'],'not_applicable');self.assertEqual(g['findings'],[])
    def test_rule_content_is_in_evaluation_identity(self):
        from app.evaluation_contract import VERSIONS
        self.assertTrue(all(VERSIONS.get(k)==v for k,v in SAFETY_IDENTITY.items()))
        a={**VERSIONS};b={**a,'safety_rules_sha256':'changed'}
        self.assertNotEqual(evaluation_identity({'id':'frozen'},a),evaluation_identity({'id':'frozen'},b))

    def test_shared_scoring_saves_raw_and_final_and_does_not_add_a_gate(self):
        from app.evaluation import EvaluationRunner,summarize_evaluation_cases
        from app.evaluation_contract import compare_cases
        saved=json.loads((ROOT/'backend/reports/vnext-judge-v3-real-validation-20261020/result-01.json').read_text())['judgment']
        item={'question':self.data['question'],'test_category':'negative','negative_subtype':'clarify','raw':{},'evidence':[]}
        execution={'answer':self.data['actual_answer'],'retrieval':[],'retrieval_trace':{'final':self.entries},'latency_ms':1}
        case=EvaluationRunner(None,None)._score_business(item,execution,copy.deepcopy(saved),'clarify')
        self.assertEqual(case['judge_result']['verdict'],'PASS');self.assertEqual(case['evaluation_outcome']['verdict'],'FAIL');self.assertFalse(case['passed'])
        execution['answer']='有人写“禁止不含盐酸的清洁剂”。'
        mock={'verdict':'PASS','checks':[{'requirement':'显式模拟','met':True,'answer_quotes':[execution['answer']],'support':[]}],'issues':[],'reason':'模拟','quality':{'correctness':4,'faithfulness':1,'completeness':1}}
        uncertain=EvaluationRunner(None,None)._score_business(item,execution,mock,'clarify')
        self.assertTrue(uncertain['passed']);self.assertTrue(uncertain['evaluation_outcome']['qualification_blocking'])
        self.assertFalse(summarize_evaluation_cases([uncertain])['safety_verification_complete'])
        comparison=compare_cases({'x':uncertain},{'x':uncertain},[])
        self.assertTrue(comparison['comparison_complete']);self.assertFalse(comparison['safety_verification_complete'])
        self.assertEqual(comparison['new_regressions'],0)

    def test_new_guard_defect_in_continued_failures_remains_visible(self):
        from app.evaluation_contract import compare_cases
        base={'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},'judge_result':{'issues':[]}}
        candidate={**base,'programmatic_metrics':{'safety_guard':self.guard(self.data['actual_answer'])}}
        c=compare_cases({'x':base},{'x':candidate},[])
        self.assertEqual(c['new_regressions'],0);self.assertEqual(len(c['continued_failure_new_issues']['x']),1)
        self.assertNotIn('x',compare_cases({'x':candidate},{'x':candidate},[])['continued_failure_new_issues'])

    def test_baseline_generation_flow_retains_risk_without_rewriting_it(self):
        from app.governance import GovernanceStore
        from unittest.mock import patch
        store=GovernanceStore.__new__(GovernanceStore)
        with patch.object(store,'current_baseline_identity',return_value={'current_baseline_id':'offline','requires_policy_upgrade':False}),patch.object(store,'evaluation_run',return_value={'result':{'safety_verification_complete':False}}):
            self.assertFalse(store.require_current_baseline()['result']['safety_verification_complete'])

    def test_unknown_object_or_conflicting_model_scope_is_not_confirmed(self):
        self.assertEqual(self.guard('禁止不含盐酸的清洁剂。',question='这台机器清洁剂怎么用？')['status'],'inconclusive')
        self.assertEqual(self.guard('禁止不含盐酸。',question='KIRA B 50电池材料？')['status'],'inconclusive')
        from app.safety_guard import check_safety
        self.assertEqual(check_safety('B2与KIRA B 50的清洁剂','禁止不含盐酸的清洁剂。',self.entries)['status'],'inconclusive')

    def test_release_rechecks_saved_safety_risk_even_if_qualification_boolean_is_true(self):
        from app.governance import GovernanceStore
        from unittest.mock import patch
        store=GovernanceStore.__new__(GovernanceStore)
        candidate={'status':'evaluated','result':{'qualification':{'qualified':True},'gates':{'passed':True},'regression':{'passed':True},'evaluation_run_id':'offline'}}
        with patch.object(store,'candidate',return_value=candidate),patch.object(store,'release_gate_error',return_value=None),patch.object(store,'evaluation_run',return_value={'status':'completed','result':{'safety_verification_complete':False}}):
            with self.assertRaisesRegex(ValueError,'关键安全'):store.publish_candidate('offline','fixture')

    def test_matching_words_with_wrong_source_page_identity_are_not_confirmed(self):
        e=copy.deepcopy(next(e for e in self.entries if e['chunk_id']=='DOC-001-C-00118'));e['page_start']=999
        self.assertEqual(self.guard('禁止不含盐酸的清洁剂。',entries=[e])['status'],'inconclusive')
