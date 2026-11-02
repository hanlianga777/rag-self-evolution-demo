"""Low baseline imports and review admission, with synthetic inputs only."""
from copy import deepcopy
import unittest
from app import agent_inputs
from app.optimization import build_agent_prompt, baseline_diagnosis_summary, optimization_priorities
from scripts import judge_calibration
import test_task009_judge_configuration as judge_fixture


class LowImportTests(unittest.TestCase):
    setUp = judge_fixture.JudgeScriptTests.setUp

    def test_calibration_import_reuses_answers_and_rejects_missing_or_changed(self):
        state = {'complete': True, 'plan': judge_calibration.calibration_plan(self.source, self.cases, 'low'),
                 'cases': {c['question_id']: {'scored_result': {k: v for k, v in c.items() if k not in {'question_id', 'run_id'}}} for c in self.cases}}
        # Review metadata was appended while calibration ran; scores/executions are unchanged.
        self.source['result']['baseline_review'] = {'complete': True}
        rows = judge_calibration.calibrated_cases(self.source, self.cases, state, 'low')
        self.assertEqual(len(rows), len(self.cases))
        missing = deepcopy(state); missing['cases'].pop(self.cases[0]['question_id'])
        with self.assertRaises(ValueError):
            judge_calibration.calibrated_cases(self.source, self.cases, missing, 'low')
        changed = deepcopy(state); changed['cases'][self.cases[0]['question_id']]['scored_result']['model_answer'] = 'changed'
        with self.assertRaises(ValueError):
            judge_calibration.calibrated_cases(self.source, self.cases, changed, 'low')

    def test_import_is_complete_idempotent_and_preserves_original(self):
        from app.governance import GovernanceStore
        from unittest.mock import patch
        from pathlib import Path
        store = GovernanceStore(Path(self.tmp.name) / 'import.db')
        source_id = store.create_evaluation_run(self.snapshot, self.source['config'], self.source['judge'])
        for case in self.cases:
            result = {k: v for k, v in case.items() if k not in {'question_id', 'run_id'}}
            result.update(severity='ordinary', root_cause={'primary': 'Generation'},
                          test_category='positive', judge_result={'correctness':4, 'faithfulness':1, 'completeness':1})
            store.record_evaluation_case(source_id, case['question_id'], result)
        store.finish_evaluation_run(source_id, 'completed', {'evaluation_complete':True, 'technical_failed':0})
        source, cases = judge_calibration.read_baseline(store.database_path, source_id)
        state = {'complete':True, 'plan':judge_calibration.calibration_plan(source,cases,'low'),
                 'cases':{c['question_id']:{'attempts':[], 'scored_result':{k:v for k,v in c.items() if k not in {'question_id','run_id'}}} for c in cases}}
        before = store.evaluation_run(source_id)
        with patch('app.evaluation.EvaluationRunner.score_execution', side_effect=AssertionError('must reuse calibration')):
            run = judge_calibration.import_calibration(store, source_id, state)
            again = judge_calibration.import_calibration(store, source_id, state)
        self.assertEqual(run['id'], again['id'])
        self.assertEqual(len(store.evaluation_runs()), 2)
        self.assertEqual(len(store.evaluation_case_results(run['id'])), len(cases))
        self.assertEqual(len(store.bad_case_rows(run['id'])), sum(c['passed'] is False for c in cases))
        self.assertTrue(run['result']['evaluation_complete'])
        self.assertEqual(run['judge']['judge_thinking']['reasoning_effort'], 'low')
        self.assertEqual(store.evaluation_run(source_id), before)


class ReviewAdmissionTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for key, status in [('Q01','confirmed_regression'),('Q02','fluctuation')]:
            rows.append({'id':'BC-'+key,'question_id':key,'result':{'passed':False,'question':key,'test_category':'positive'},
                'diagnostic_view':{'diagnosis_category':'生成','primary_root_cause':'Generation','analysis_reason':'fixture','display_question_id':key,'priority':3},
                'retrieval_facts':{'baseline_review':{'status':status,'conclusion':'真错题' if key=='Q01' else '随机波动','failed_votes':3 if key=='Q01' else 1,'total_votes':3}}})
        return rows

    def test_unstable_has_no_target_and_no_priority_promotion(self):
        rows=self.rows()
        gate={'metric':'positive_correctness','actual':80,'threshold':90,'operator':'>=','passed':False}
        system,prompt=build_agent_prompt(rows,{},[],[gate],list('ABC'))
        self.assertEqual([r['question_id'] for r in prompt['bad_cases']],['Q01'])
        self.assertEqual([r['question_id'] for r in prompt['unstable_cases']],['Q02'])
        self.assertIn('不稳定题：方案需保持判对，不作为必修目标',str(prompt))
        summary=baseline_diagnosis_summary(rows[1:],[gate])[0]
        self.assertIn('复核多数判对',summary['root_cause_note'])
        self.assertNotEqual(summary['root_causes'][0]['priority'],1)
        self.assertEqual(baseline_diagnosis_summary(rows,[gate])[0]['root_causes'][0]['priority'],1)

    def test_prepared_review_admission_is_shared(self):
        import json
        baseline={'dataset_snapshot_json':json.dumps({'questions':[]}), 'result':{'baseline_review':{'cases':{'Q02':{'regression_review':{'status':'fluctuation','failed_votes':1,'total_votes':3}}}}}}
        prepared=agent_inputs.prepare_baseline_rows(baseline,[{'id':'b','question_id':'Q02','result':{'passed':False}}])[0]
        self.assertFalse(agent_inputs.is_optimization_target(prepared))
        self.assertEqual(prepared['result']['baseline_review']['status'],'fluctuation')

class BudgetTests(unittest.TestCase):
    def test_budget_is_available_without_experiment(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        from unittest.mock import Mock, patch
        store=Mock()
        store.current_baseline_identity.return_value={'current_experiment_id':None,'baseline_unavailable_reason':None}
        with patch.object(main,'store',store):
            response=TestClient(main.app).get('/api/optimization?light=true')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['evaluation_budget'],{'used':0,'max':12,'reserved_for_d':1,'remaining':12,'remaining_for_abc':11})
        store.create_experiment.assert_not_called()

class ActualAgentAdmissionTests(unittest.TestCase):
    def setUp(self):
        import test_optimization_contract as fixture
        fixture.OptimizationContractTests.setUp(self)

    def test_random_case_is_preserved_but_never_a_candidate_target(self):
        import json
        import test_optimization_contract as fixture
        from app.optimization import OptimizationAgent
        self.store.record_bad_case('EVAL-test','unstable','Retrieval','ordinary',fixture.trace_case())
        run=self.store.evaluation_run('EVAL-test')
        run['result']['baseline_review']={'cases':{'Q1':{'regression_review':{'status':'confirmed_regression','failed_votes':3,'total_votes':3}},
            'unstable':{'regression_review':{'status':'fluctuation','failed_votes':1,'total_votes':3}}}}
        self.store.finish_evaluation_run('EVAL-test','completed',run['result'])
        provider=fixture.FixedProvider(json.dumps(fixture.drafts()))
        experiment=OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual([r['question_id'] for r in provider.prompt['bad_cases']],['Q1'])
        self.assertEqual([r['question_id'] for r in provider.prompt['unstable_cases']],['unstable'])
        self.assertEqual(set(experiment['result']['source_bad_case_ids']),{'BC-EVAL-test-Q1'})
        self.assertEqual(experiment['result']['processing_progress']['baseline_failed_question_ids'],['Q1'])
        self.assertEqual(len(self.store.bad_case_rows('EVAL-test')),2)

class CompositeAdmissionTests(unittest.TestCase):
    def setUp(self):
        import test_evaluation_context as fixture
        fixture.CompositeTests.setUp(self)

    def result(self):
        import test_evaluation_context as fixture
        return fixture.CompositeTests.result(self)

    def test_d_uses_same_review_targets(self):
        import json
        import test_evaluation_context as fixture
        from diagnostic_fixture import retrieval_case
        self.store.record_bad_case(self.baseline,'unstable','Retrieval','ordinary',retrieval_case()[0])
        run=self.store.evaluation_run(self.baseline)
        run['result']['baseline_review']={'cases':{'q':{'regression_review':{'status':'confirmed_regression','failed_votes':3,'total_votes':3}},
            'unstable':{'regression_review':{'status':'fluctuation','failed_votes':1,'total_votes':3}}}}
        self.store.finish_evaluation_run(self.baseline,'completed',run['result'])
        provider=fixture.CompositeTests.provider(self,generate=False)
        self.store.create_composite(self.experiment,provider,True)
        prompt=json.loads(provider.complete.call_args.args[1])
        self.assertEqual([r['question_id'] for r in prompt['bad_cases']],['q'])
        self.assertEqual([r['question_id'] for r in prompt['unstable_cases']],['unstable'])


class FollowupSelectionTests(unittest.TestCase):
    def test_review_group_selects_all_failed_cases(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from app.followups import FollowupJobs
        with TemporaryDirectory() as directory:
            jobs=FollowupJobs(SimpleNamespace(database_path=Path(directory)/'fixture.db'),None)
            runner=Mock()
            def review(run_id, *, on_progress, stop_on_error):
                on_progress({'cases':{}, 'complete':True})
            runner.review_baseline_errors.side_effect=review
            with patch('app.followups.read_baseline',return_value=({'judge':{'model':'fixture'}},[{'passed':False}]*3+[{'passed':True}])),patch('app.followups.EvaluationRunner',return_value=runner):
                jobs._run('fixture','review')
            self.assertEqual(runner.review_baseline_errors.call_args.args,('fixture',))
            self.assertEqual(jobs.progress('fixture','review')['planned'],6)
