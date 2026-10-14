"""Read-only classification; fixtures never enter the real database."""
import unittest
from copy import deepcopy
from app.diagnostics import diagnostic_view
from app.evaluation_contract import VERSIONS

class DiagnosticViewTests(unittest.TestCase):
    def test_multiple_phenomena_preserve_unknown_confidence_and_original(self):
        case={'failure_tags':['Hallucination','Unsafe Answer'],'primary_root_cause':'Unknown','diagnosis':{'status':'needs_review'},'passed':False}
        before=deepcopy(case);v=diagnostic_view(case)
        self.assertEqual(case,before);self.assertEqual(v['primary_root_cause'],'Unknown')
        self.assertEqual(v['confidence'],'needs_review');self.assertEqual(len(v['phenomena']),2)
        self.assertFalse(v['target_eligible'])

    def test_final_omission_requires_actual_candidate_evidence(self):
        case={'programmatic_metrics':{'evidence_coverage':{'required_chunk_ids':['c'],'final_context':{'all_hit':False}},'retrieval_trace':{'candidates':[{'chunk_id':'c'}]}}}
        self.assertIn('检索失败',[x['name'] for x in diagnostic_view(case)['phenomena']])
        case['programmatic_metrics']['retrieval_trace']['candidates']=[]
        self.assertNotIn('检索失败',[x['name'] for x in diagnostic_view(case)['phenomena']])

    def test_refusal_and_noise_need_typed_evidence_not_low_precision(self):
        case={'failure_tags':['Over Refusal','Safety False Positive'],'model_answer':'先澄清','programmatic_metrics':{'retrieval_precision':1,'evidence_sufficiency':{'sufficient':False}},'diagnosis':{'status':'confirmed','answer_quote':'先澄清'}}
        v=diagnostic_view(case);self.assertFalse(any(x['name'] in {'模型过度拒答','安全边界误伤','检索噪声'} for x in v['phenomena']))
        case['programmatic_metrics']['evidence_sufficiency']['sufficient']=True
        self.assertEqual({'模型过度拒答','安全边界误伤'},{x['name'] for x in diagnostic_view(case)['phenomena']})
        self.assertNotIn('安全边界失守',{x['name'] for x in diagnostic_view(case)['phenomena']})

    def test_latency_separates_question_judge_and_nested_stages(self):
        case={'failure_tags':['Performance Failure'],'programmatic_metrics':{'latency_ms':30000,'ttft_ms':1000,'stages':[{'stage_name':'retrieval','parent':None,'duration_ms':2000},{'stage_name':'generation','parent':None,'duration_ms':27000},{'stage_name':'rerank','parent':'retrieval','duration_ms':1000}],'judge_stages':[{'stage_name':'judge','duration_ms':240000}]}}
        v=diagnostic_view(case);self.assertEqual(v['latency']['bottleneck']['stage_name'],'generation')
        self.assertEqual(v['latency']['question_ms'],30000);self.assertIn('延迟黑洞',[p['name'] for p in v['phenomena']])
        self.assertNotEqual(v['latency']['question_ms'],240000)

    def test_governance_and_capability_do_not_upgrade_root_or_rules(self):
        case={'primary_root_cause':'Unknown','diagnosis':{'status':'disputed'},'programmatic_metrics':{'claim_assessment':{'pending':[{'claim':'改写主张'}]}}}
        versions=deepcopy(VERSIONS);v=diagnostic_view(case)
        self.assertTrue(v['governance']);self.assertEqual(v['primary_root_cause'],'Unknown');self.assertFalse(v['target_eligible'])
        self.assertEqual(v['typical_detection']['检索噪声'],'not_collected');self.assertEqual(VERSIONS,versions)

    def test_readonly_api_exposes_same_view_without_persisting_it(self):
        import tempfile
        from pathlib import Path
        from api_fixture import main
        from identity_fixture import completed_baseline
        from app.governance import GovernanceStore
        from fastapi.testclient import TestClient
        with tempfile.TemporaryDirectory() as directory:
            original=main.store;store=GovernanceStore(Path(directory)/'fixture.db');main.store=store
            try:
                key=completed_baseline(store)
                before=store.evaluation_case_results(key)
                client=TestClient(main.app)
                detail=client.get('/api/evaluations/'+key).json()
                bad=client.get('/api/bad-cases').json()
                self.assertEqual(detail['cases'][0]['diagnostic_view']['primary_root_cause'],'Generation')
                self.assertIn('diagnostic_view',bad[0]['result'])
                self.assertEqual(store.evaluation_case_results(key),before)
                self.assertNotIn('diagnostic_view',store.bad_case_rows()[0]['result'])
            finally:main.store=original

    def test_verified_noise_does_not_map_generation_root_to_retrieval(self):
        case={'failure_tags':['Retrieval Noise'],'model_answer':'只能使用','primary_root_cause':'Generation','diagnosis':{'status':'confirmed','findings':[{'claim':'只能使用','support':[{'chunk_id':'c','quote':'可以使用'}]}]},'programmatic_metrics':{'retrieval_trace':{'final':[{'chunk_id':'c','content':'可以使用'}]}}}
        view=diagnostic_view(case)
        self.assertIn('检索噪声',[p['name'] for p in view['phenomena']]);self.assertEqual(view['primary_root_cause'],'Generation')
        case['diagnosis']['findings'][0]['support'][0]['quote']='不存在'
        self.assertNotIn('检索噪声',[p['name'] for p in diagnostic_view(case)['phenomena']])
