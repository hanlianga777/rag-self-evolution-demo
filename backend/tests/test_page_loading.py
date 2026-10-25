"""Read-side performance boundaries; no Provider, migrations or formal writes."""
import json
import unittest
from unittest.mock import Mock,patch
from app.evidence_resolver import persisted_inputs


class PageLoadingTests(unittest.TestCase):
    def test_restore_queries_active_tasks_without_discarding_history(self):
        import tempfile
        from pathlib import Path
        from app.governance import GovernanceStore
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'isolated.db')
            with store.connection() as db:
                for key,status in [('old','completed'),('live','validating')]:
                    db.execute('INSERT INTO candidate_revision_runs VALUES (?,?,?,?,?,?)',(key,'g',status,json.dumps({'status':status,'details':'retained'}),'now','now'))
                for key,status in [('old','completed'),('live','running')]:
                    db.execute('INSERT INTO evaluation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(key,status,'real','real','g','{}','{}','{}','{}',None,'now',None))
            self.assertEqual([r['id'] for r in store.revision_runs(active_only=True)],['live'])
            self.assertEqual([r['id'] for r in store.evaluation_history(active_only=True)],['live'])
            self.assertEqual(len(store.revision_runs()),2)
            self.assertEqual(len(store.evaluation_history()),2)

    def test_view_memo_is_request_scoped_and_does_not_share_mutable_results(self):
        from app.read_view import read_view,memoized_view
        calls=[]
        @memoized_view
        def render(value):calls.append(value);return {'rows':[value]}
        with read_view():
            render(1)['rows'].append('local change')
            self.assertEqual(render(1),{'rows':[1]})
            render(2)
        with read_view():render(1)
        render(1)
        self.assertEqual(calls,[1,2,1,1])

    def test_single_diagnostic_reads_only_its_case(self):
        store=Mock();snapshot={'questions':[{'id':'Q1'}],'corpus_fingerprint':{'source':'f'}}
        store.evaluation_run.return_value={'dataset_snapshot_json':json.dumps(snapshot),'judge':{},'config':{}}
        store.evaluation_case_result.return_value={'question_id':'Q1','model_answer':'saved'}
        store.evaluation_case_results.side_effect=AssertionError('must not parse the entire Run per question')
        case,_,_=persisted_inputs(store,'run','Q1',[],{'source':'f'})
        self.assertEqual(case['model_answer'],'saved')
        store.evaluation_case_result.assert_called_once_with('run','Q1')

    def test_light_optimization_does_not_recompute_agent_diagnostics(self):
        from api_fixture import main
        store=Mock();store.current_baseline_identity.return_value={'current_experiment_id':'exp'}
        store.experiment.return_value={'id':'exp','result':{},'candidates':[{'id':'A','status':'evaluated','result_json':'raw','result':{'completed':50,'checkpoints':{'large':'audit'},'qualification':{'qualified':False}}}]}
        with patch.object(main,'store',store),patch('app.agent_coverage.coverage_inputs',side_effect=AssertionError('overview must not recompute coverage')):
            result=main.optimization(light=True)
        self.assertEqual(result['candidates'][0]['result']['completed'],50)
        self.assertNotIn('checkpoints',result['candidates'][0]['result'])
        self.assertNotIn('result_json',result['candidates'][0])

    def test_workspace_profiles_reuse_backend_config_without_another_query(self):
        from api_fixture import main
        store=Mock();store.current_baseline_identity.return_value={'requires_new_golden':False,'current_baseline_id':'baseline'}
        store.active_production.return_value={'id':'active'}
        with patch.object(main,'store',store),patch.object(main.corpus,'documents',return_value=[]),patch.object(main.corpus_manager,'state',return_value={}):
            result=main.workspace()
        self.assertIs(result['generation_profiles'],main.GENERATION_PROFILES)
        self.assertEqual([result['generation_profiles'][key]['expected_count'] for key in ('mini','medium','full')],[20,50,100])
        store.connection.assert_not_called()
