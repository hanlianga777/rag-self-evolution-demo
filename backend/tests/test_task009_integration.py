import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from api_fixture import main
from app.governance import GovernanceStore
from app.evaluation import EvaluationRunner
from app.providers import judge_thinking, thinking_config
from app.evaluation_contract import evaluation_identity
from identity_fixture import completed_baseline

class IntegrationTests(unittest.TestCase):
    def test_pin_audited_one_transaction_preserves_scores_ignores_newer(self):
        from diagnostic_fixture import install_corpus
        install_corpus(self)
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'synthetic.db')
            high=completed_baseline(store);other=completed_baseline(store)
            for key in (high,other):
                run=store.evaluation_run(key)
                store.finish_evaluation_run(key,'completed',{**run['result'],'evaluation_complete':True,'technical_failed':0})
            before={key:store.evaluation_run(key) for key in (high,other)}
            store.save_pipeline_draft({'config':{'generation_thinking':'max'},'identity':store.current_baseline_identity()})
            client=TestClient(main.app)
            with patch.object(main,'store',store):
                response=client.post('/api/baseline-designation',json={'baseline_run_id':high,'comparison_run_id':other,'actor':'fixture','reason':'测试明确指定'})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['actor'],'fixture')
                self.assertIsNone(store.pipeline_draft())
                newer=completed_baseline(store)
                self.assertNotEqual(high,newer)
                for page in ('workspace','overview','pipeline','evaluation?light=true','optimization'):
                    with patch.object(main,'knowledge',return_value={'index':{},'identity':'test','coverage_status':'ready'}):
                        data=client.get('/api/'+page).json()
                    self.assertEqual(data['current_baseline_id'],high,page)
            self.assertEqual({key:store.evaluation_run(key) for key in before},before)
            with store.connection() as connection:
                self.assertEqual(connection.execute('select count(*) from baseline_designations').fetchone()[0],1)
            with self.assertRaises(ValueError):store.designate_baseline('missing',other,'fixture','测试')
            self.assertEqual(store.baseline_designation()['baseline_run_id'],high)
    def test_execute_uses_saved_judge_after_env_change(self):
        store=Mock();run={'status':'running','judge':{'judge_thinking':thinking_config('judge','low')},'result':{}}
        store.evaluation_run.return_value=run
        runner=EvaluationRunner(store,Mock())
        runner._require_generation_contract=Mock()
        runner._execute_baseline=lambda *_:thinking_config('judge')['reasoning_effort']
        with judge_thinking('max'):
            self.assertEqual(runner.execute_baseline('fixture',[],{}),'low')
            self.assertEqual(thinking_config('judge')['reasoning_effort'],'max')
    def test_replay_source_effort_validated_before_target_changes_and_saved(self):
        from app.judge_replay import replay_eligibility
        store=Mock();source={'judge':{'judge_thinking':thinking_config('judge','max')},'dataset_snapshot_json':json.dumps({'question_ids':[],'questions':[]}), 'config':{}}
        store.evaluation_run.return_value=source
        runner=EvaluationRunner(store,Mock())
        def inputs(_):
            self.assertEqual(thinking_config('judge')['reasoning_effort'],'max')
            return {'corpus_fingerprint':'f'},[],{}, {'judge_thinking':thinking_config('judge')}
        runner.baseline_inputs=inputs
        store.connection.return_value.__enter__=Mock(return_value=Mock())
        store.connection.return_value.__exit__=Mock(return_value=False)
        def eligibility(_source,_cases,snapshot,config,judge,*_):
            self.assertEqual(judge['judge_thinking']['reasoning_effort'],'low')
            self.assertEqual(judge['evaluation_identity'],evaluation_identity(snapshot,judge))
            return {'can_replay':True,'new_judge':judge,'executions':{}}
        with patch('app.judge_replay.replay_eligibility',side_effect=eligibility),patch('app.diagnostics._current_corpus',return_value=([],'f')):
            plan=runner.judge_replay_preflight('fixture',judge_thinking='low')
        self.assertTrue(plan['can_replay']);self.assertNotIn('executions',plan)
    def test_cycle_endpoint_claim_before_thread_and_manual_duplicate_blocked(self):
        store=Mock();store.experiment.return_value={'baseline_run_id':'fixture','result':{'optimization_cycle':{'status':'running'}}}
        client=TestClient(main.app)
        with patch.object(main,'store',store),patch.object(main,'require_current_baseline'),patch('app.optimization_cycle.claim_cycle',return_value={'status':'running'}) as claim,patch.object(main,'threading',SimpleNamespace(Thread=Mock())) as threading_mock:
            thread=threading_mock.Thread
            thread.reset_mock()
            self.assertEqual(client.post('/api/experiments/e/run-cycle').status_code,201)
            claim.assert_called_once_with(store,'e',current_round_only=False);thread.return_value.start.assert_called_once()
            self.assertEqual(client.post('/api/experiments/e/continue').status_code,409)
    def test_judge_target_api_validates_without_calls(self):
        runner=Mock();runner.start_judge_replay.return_value=('fixture',[],{})
        client=TestClient(main.app)
        with patch.object(main,'EvaluationRunner',return_value=runner),patch.object(main,'threading',SimpleNamespace(Thread=Mock())):
            self.assertEqual(client.post('/api/evaluations/source/judge-replay',json={'judge_thinking':'low'}).status_code,201)
            runner.start_judge_replay.assert_called_once_with('source',judge_thinking='low')
            self.assertEqual(client.post('/api/evaluations/source/judge-replay',json={'judge_thinking':'off'}).status_code,422)

    def test_selected_review_attaches_only_to_source_preserving_scores(self):
        from diagnostic_fixture import install_corpus
        install_corpus(self)
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'synthetic.db');key=completed_baseline(store)
            run=store.evaluation_run(key)
            store.finish_evaluation_run(key,'completed',{**run['result'],'evaluation_complete':True,'technical_failed':0,'completed':1})
            before=store.evaluation_run(key);cases=store.evaluation_case_results(key)
            runner=EvaluationRunner(store,Mock());runner._require_generation_contract=Mock()
            runner.snapshot_items=Mock(return_value=[{'id':'Q1'}])
            def review(item,initial,config,checkpoint,stage_id,check_stop,save):
                checkpoint['regression_review']={'status':'confirmed_regression'};save()
            runner.review_regression=Mock(side_effect=review)
            with patch('app.evaluation.policy_current',return_value=True):
                result=runner.review_baseline_errors(key,question_ids=['Q01'])
            self.assertEqual(set(result['cases']),{'Q1'});runner.review_regression.assert_called_once()
            after=store.evaluation_run(key)
            self.assertEqual({k:v for k,v in after['result'].items() if k!='baseline_review'},before['result'])
            self.assertEqual(store.evaluation_case_results(key),cases)
