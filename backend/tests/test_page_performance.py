"""Read models must scope the working pool and omit duplicated payloads."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.governance import GovernanceStore

class PagePerformanceTests(unittest.TestCase):
    def test_working_pool_uses_run_ids_not_historical_lineages(self):
        with tempfile.TemporaryDirectory() as temp:
            store = GovernanceStore(Path(temp) / 'test.db')
            run = {'id':'medium-current','question_ids':[f'Q{i:02}' for i in range(50)],'profile':{'name':'medium','expected_count':50}}
            with patch.object(store, 'working_generation_run', return_value=run, create=True), patch.object(store, 'candidate_rows', side_effect=lambda ids=None: [{'id':q} for q in (ids or ['old','new'])]) as read:
                self.assertEqual(len(store.working_pool_rows()), 50)
                read.assert_called_once_with(run['question_ids'])

    def test_light_evaluation_omits_checkpoints_and_full_snapshot_questions(self):
        with tempfile.TemporaryDirectory() as temp:
            store = GovernanceStore(Path(temp) / 'test.db')
            snapshot={'id':'gd','question_ids':['Q1'],'questions':[{'id':'Q1','test_category':'positive','evidence':['large']} ]}
            run_id=store.create_evaluation_run(snapshot, {'run_target':'baseline'}, {})
            store.finish_evaluation_run(run_id,'completed',{'checkpoints':{'Q1':{'trace':'large'}},'completed':1})
            light=store.evaluation_run(run_id, light=True)
            self.assertNotIn('checkpoints', light['result'])
            self.assertNotIn('result_json', light)
            self.assertNotIn('evidence',light['dataset_snapshot']['questions'][0])
            self.assertIn('checkpoints',store.evaluation_run(run_id)['result'])

    def test_snapshot_list_keeps_membership_without_full_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            store=GovernanceStore(Path(temp)/'test.db')
            snapshot={'question_ids':['Q1'],'questions':[{'id':'Q1','test_category':'positive','evidence':['large']}],'coverage_plan':{'planner_version':'v2','clusters':['large']}}
            with store.connection() as db:db.execute("INSERT INTO dataset_versions VALUES ('gd','approved','fixture',?,'now')",(json.dumps(snapshot),))
            value=store.dataset_snapshots(light=True)[0]
            self.assertEqual(value['snapshot']['question_ids'],['Q1'])
            self.assertNotIn('snapshot_json',value)
            self.assertNotIn('evidence',value['snapshot']['questions'][0])
            self.assertIn('evidence',store.dataset_snapshots()[0]['snapshot']['questions'][0])

    def test_light_planning_reuses_case_diagnosis_and_preserves_full_audit(self):
        from api_fixture import main
        from unittest.mock import Mock
        store=Mock()
        store.current_baseline_identity.return_value={'current_experiment_id':'exp'}
        store.recommendation.return_value={'result_json':'duplicate','result':{'status':'Not Recommended','comparison':{'trace':'large'}}}
        experiment={'id':'exp','result':{'all_bad_case_audit':['full']},'candidates':[{'id':'A','result':{'completed':50,'checkpoints':{'full':'trace'}},'reasoning':{'target_diagnosis':{'full':'trace'}}}]}
        row={'id':'bad','result_json':'duplicate','result':{'passed':False,'programmatic_metrics':{'retrieval_trace':{'large':'trace'}},'judge_result':{'raw_provider_response':'large','correctness':3}},'diagnostic_view':{'status':'saved'}}
        original=json.dumps(experiment,sort_keys=True)
        with patch.object(main,'store',store), patch('app.agent_coverage.coverage_inputs',return_value=(experiment,{},[row],{}, {'status':'complete'})), patch.object(main,'experiment_resume_view',side_effect=lambda value:value), patch.object(main,'diagnostic_view',side_effect=AssertionError('must reuse computed diagnosis')):
            value=main.optimization(light=True,planning=True)
        self.assertEqual(value['bad_cases'][0]['result']['diagnostic_view'],row['diagnostic_view'])
        self.assertNotIn('result_json',value['bad_cases'][0])
        self.assertNotIn('retrieval_trace',value['bad_cases'][0]['result']['programmatic_metrics'])
        self.assertNotIn('raw_provider_response',value['bad_cases'][0]['result']['judge_result'])
        self.assertNotIn('checkpoints',value['candidates'][0]['result'])
        self.assertNotIn('comparison',value['recommendation']['result'])
        self.assertEqual(json.dumps(experiment,sort_keys=True),original)

if __name__=='__main__':unittest.main()
