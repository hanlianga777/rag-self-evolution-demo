"""Exercise persisted recommendations and release rules on a disposable database."""
import json
import tempfile
import unittest
from pathlib import Path

from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG
from identity_fixture import completed_baseline


class ReleaseWiringTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=GovernanceStore(Path(self.temp.name)/'test.db')
        completed_baseline(self.store,run_id='B0')
        self.identity=self.store.evaluation_run('B0')['judge']['evaluation_identity']
        with self.store.connection() as c:
            c.execute('INSERT INTO experiments VALUES (?,?,?,?,?)',('E0','B0','active','{}','now'))

    def candidate(self,label,bad,new=0,qualified=True):
        result={'qualification':{'qualified':qualified},'release_qualification':{'qualified':qualified},
            'evaluation_identity':self.identity,'bad_case_count':bad,
            'gates':{'passed':True},'regression':{'passed':True,'new_critical_failures':0,'new_ordinary_failures':new}}
        with self.store.connection() as c:
            c.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)',(label,'E0','evaluated',json.dumps(DEFAULT_PIPELINE_CONFIG),json.dumps({'candidate_label':label}),json.dumps(result),'now'))
        return result

    def state(self,**fields):
        with self.store.connection() as c:
            c.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(fields),'E0'))

    def test_suggested_winner_is_fewest_errors_even_with_ordinary_regressions(self):
        self.candidate('A',5,0);self.candidate('B',2,1)
        result=self.store.refresh_recommendation('E0')
        self.assertEqual(result['suggested_winner'],'B')
        self.assertEqual(result['final_decision']['candidate_id'],'B')

    def test_failed_final_selects_best_qualified_even_if_gate2_chose_another(self):
        self.candidate('A',5,qualified=True);self.candidate('B',2,qualified=True);self.candidate('D',4,qualified=False)
        self.state(report_confirmation={'winner_id':'A'},composite={'status':'generated','candidate_id':'D'})
        result=self.store.refresh_recommendation('E0')
        self.assertEqual(result['recommended_candidate'],'B')
        self.assertEqual(result['suggested_winner'],'B')
        self.assertEqual(result['final_decision']['decision'],'保留 Winner 方案')

    def test_no_qualified_candidate_records_agent_failure(self):
        result=self.store.refresh_recommendation('E0')
        self.assertEqual(result['final_decision']['decision'],'本次 Agent 优化失败')
        self.assertIsNone(result['recommended_candidate'])

    def test_selected_winner_with_one_ordinary_error_has_release_qualification(self):
        self.candidate('A',2,new=1)
        self.state(report_confirmation={'winner_id':'A'},composite={'status':'no_effective_composite'})
        self.store.refresh_recommendation('E0')
        state=self.store.release_state(self.store.candidate('A'))
        self.assertTrue(state['qualified'])
        self.assertTrue(state['recommended'])
        self.assertFalse(state['human_release'])
