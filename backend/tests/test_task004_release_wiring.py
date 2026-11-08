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

    def candidate(self,label,bad,new=0,release=False):
        result={'qualification':{'qualified':True},'release_qualification':{'qualified':release},
            'evaluation_identity':self.identity,'bad_case_count':bad,
            'gates':{'passed':True},'regression':{'passed':True,'new_critical_failures':0,'new_ordinary_failures':new}}
        with self.store.connection() as c:
            c.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)',(label,'E0','evaluated',json.dumps(DEFAULT_PIPELINE_CONFIG),json.dumps({'candidate_label':label}),json.dumps(result),'now'))
        return result

    def state(self,**fields):
        with self.store.connection() as c:
            c.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(fields),'E0'))

    def test_suggested_winner_is_fewest_errors_even_with_ordinary_regressions(self):
        self.candidate('A',5,0);self.candidate('B',2,3)
        result=self.store.refresh_recommendation('E0')
        self.assertEqual(result['suggested_winner'],'B')
        self.assertEqual(result['final_decision']['decision'],'保持 Baseline')

    def test_failed_final_keeps_confirmed_winner_with_fewer_error_alternative(self):
        self.candidate('A',5,release=True);self.candidate('B',2,release=True);self.candidate('D',4,release=False)
        self.state(report_confirmation={'winner_id':'A'},composite={'status':'generated','candidate_id':'D'})
        result=self.store.refresh_recommendation('E0')
        self.assertEqual(result['recommended_candidate'],'A')
        self.assertEqual(result['suggested_winner'],'B')
        self.assertEqual(result['final_decision']['decision'],'保留 Winner 方案')

    def test_no_qualified_candidate_records_keep_baseline(self):
        result=self.store.refresh_recommendation('E0')
        self.assertEqual(result['final_decision']['decision'],'保持 Baseline')
        self.assertIsNone(result['recommended_candidate'])

    def test_selected_winner_with_new_errors_cannot_publish(self):
        self.candidate('A',2,new=1,release=False)
        self.state(report_confirmation={'winner_id':'A'},composite={'status':'no_effective_composite'})
        self.store.refresh_recommendation('E0')
        with self.assertRaisesRegex(ValueError,'发布规则'):
            self.store.publish_candidate('A','test human')
