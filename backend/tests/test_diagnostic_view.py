"""Read-only task004 presentation view; fixtures use temporary databases."""
import unittest
from copy import deepcopy
from app.diagnostics import diagnostic_view
from diagnostic_fixture import generation_case, retrieval_case


class DiagnosticViewTests(unittest.TestCase):
    def test_every_failure_exposes_conclusion_reason_and_root(self):
        for case in (generation_case(),retrieval_case()[0],{'passed':False}):
            before=deepcopy(case);view=diagnostic_view(case)
            self.assertTrue(view['diagnosis_category'])
            self.assertTrue(view['analysis_reason'])
            self.assertNotIn(view['primary_root_cause'],('',None,'Unknown'))
            self.assertEqual(case,before)

    def test_missing_record_is_not_a_technical_optimization_target(self):
        view=diagnostic_view({'passed':False,'primary_root_cause':'Retrieval'})
        self.assertEqual(view['diagnosis_category'],'记录缺失')
        self.assertFalse(view['target_eligible'])
        self.assertFalse(view['diagnosis_complete'])
        self.assertFalse(view['optimization_directions'])
        self.assertTrue(view['evaluation_quality_audit']['issues'])

    def test_latency_separates_question_judge_and_nested_stages(self):
        case=generation_case();case['programmatic_metrics'].update(latency_ms=30000,ttft_ms=1000,
            stages=[{'stage_name':'retrieval','parent':None,'duration_ms':2000},
                    {'stage_name':'generation','parent':None,'duration_ms':27000},
                    {'stage_name':'rerank','parent':'retrieval','duration_ms':1000}],
            judge_stages=[{'stage_name':'judge','duration_ms':240000}])
        view=diagnostic_view(case)
        self.assertEqual(view['latency']['bottleneck']['stage_name'],'generation')
        self.assertEqual(view['latency']['question_ms'],30000)
        self.assertEqual(view['latency']['judge_stages'][0]['duration_ms'],240000)

    def test_retrieval_metrics_do_not_change_saved_verdict_or_gates(self):
        from app.evaluation_contract import VERSIONS
        case=generation_case();case.update(passed=True,judge_result={'verdict':'PASS'})
        case['programmatic_metrics']['retrieval_trace'].update(candidates=[],final=[])
        before=deepcopy(case);versions=deepcopy(VERSIONS);view=diagnostic_view(case)
        self.assertEqual(view['diagnosis_category'],'通过')
        self.assertEqual(view['retrieval_metrics']['recall_at_k'],0)
        self.assertFalse(view['is_technical_bad_case'])
        self.assertEqual(case,before);self.assertEqual(VERSIONS,versions)

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
