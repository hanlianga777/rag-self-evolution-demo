"""Real persistence and cycle policy with offline Agent/Sandbox transport."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from copy import deepcopy

import test_optimization_contract as contract
from app.optimization import validate_round_contract
from app.policy import DEFAULT_PIPELINE_CONFIG
from app.optimization_cycle import run_until_qualified
from app.paid_schedule import set_unattended_authorization
from test_task019a_agent import result_candidate


class UnattendedCycleTests(unittest.TestCase):
    setUp=contract.OptimizationContractTests.setUp

    def run_scenario(self, better=False, enabled=True, ordinary=False):
        store=self.store
        exp=store.create_experiment('EVAL-test')
        set_unattended_authorization(store,enabled,'用户 2026-11-05 授权')
        identity=store.evaluation_run('EVAL-test')['judge']['evaluation_identity']
        calls=[]
        class Agent:
            def __init__(self,*args):pass
            def generate(self,*args,**kwargs):
                previous=store.experiment(exp,light=True)['candidates']
                round_no=1+max([c['reasoning']['round'] for c in previous] or [0])
                drafts=deepcopy(contract.drafts()['candidates'])
                drafts[0]['config_diff']={'hyde':True} if round_no==1 else {'query_rewrite':True}
                if round_no==2:
                    drafts[1]['config_diff']={'generation_thinking':'high','hyde':True}
                    drafts[2]['config_diff']={'candidate_k':48}
                validate_round_contract(drafts,DEFAULT_PIPELINE_CONFIG,previous,[{'id':'latency_p99_seconds','actual':42,'operator':'<=','passed':True}])
                for draft in drafts:
                    store.save_candidate(exp,f"R{round_no}-{draft['id']}",{**DEFAULT_PIPELINE_CONFIG,**draft['config_diff']},
                        {'candidate_label':draft['id'],'round':round_no,'changed_parameters':draft['config_diff']})
        class Runner:
            def __init__(self,*args):pass
            def run_candidate(self,cid,**kwargs):
                c=store.candidate(cid);calls.append(cid)
                store.reserve_candidate_evaluation(cid)
                d=c['reasoning']['candidate_label']=='D'
                qualified=c['reasoning'].get('round')==2 or d
                result=result_candidate('D' if d else 'A',bad=1 if better and d else 2 if qualified else 6,
                                        p99=30 if d else 25,release=not ordinary or d)['result']
                result.update(evaluation_complete=True,evaluation_identity=identity,
                    gates={'passed':qualified,'gates':[{'id':'latency_p99_seconds','actual':25 if qualified else 72,'passed':qualified,'operator':'<='}]},
                    qualification={'qualified':qualified},regression={'passed':True,'new_critical_failures':0,'new_ordinary_failures':0},
                    all_fixed_question_ids=['Q1'])
                return store.finish_candidate(cid,'evaluated',result)
        def composite(eid,provider):
            confirmation=store.experiment(eid,light=True)['result']['report_confirmation']
            d=store.candidate(eid+'-D')
            if d:return d
            with store.connection() as db:
                db.execute('insert into candidate_configs values (?,?,?,?,?,?,?)',(eid+'-D',eid,'generated',json.dumps(DEFAULT_PIPELINE_CONFIG),json.dumps({'candidate_label':'D','winner_id':confirmation['winner_id']}),'{}','9999'))
            d=store.candidate(eid+'-D')
            with store.connection() as db:
                state=json.loads(db.execute('select result_json from experiments where id=?',(eid,)).fetchone()[0])
                state['composite']={'status':'generated','candidate_id':d['id']}
                db.execute('update experiments set result_json=? where id=?',(json.dumps(state),eid))
            return d
        with patch('app.optimization_cycle.OptimizationAgent',Agent),patch('app.optimization_cycle.EvaluationRunner',Runner),patch.object(store,'create_composite',side_effect=composite):
            state=run_until_qualified(store,SimpleNamespace(provider=object()),exp)
        return store.experiment(exp),state,calls

    def test_auto_next_round_early_skip_gate2_d_and_stop_before_publish(self):
        for better in (False,True):
            with self.subTest(better=better):
                exp,state,calls=self.run_scenario(better)
                self.assertEqual(state['status'],'recommended',state)
                self.assertEqual(exp['evaluation_budget']['used'],5)
                self.assertEqual([c['status'] for c in exp['candidates'] if c['reasoning'].get('round')==2],['evaluated','skipped','skipped'])
                confirmation=exp['result']['report_confirmation']
                self.assertIn('按用户授权自动确认',confirmation['actor'])
                recommendation=self.store.recommendation(exp['id'])['result']
                self.assertEqual(recommendation['recommended_candidate'],exp['id']+('-D' if better else '-R2-A'))
                with self.store.connection() as db:
                    self.assertEqual(db.execute("select count(*) from approvals where gate='human_release'").fetchone()[0],0)
                    self.assertEqual(db.execute('select count(*) from production_versions').fetchone()[0],1)

    def test_disabled_authorization_waits_for_manual_gate2(self):
        exp,state,calls=self.run_scenario(enabled=False)
        self.assertEqual(state['status'],'qualified',state)
        self.assertNotIn('report_confirmation',exp['result'])
        self.assertEqual(exp['evaluation_budget']['used'],4)

    def test_skip_only_unstarted_is_free_and_gate2_accepts_skips(self):
        exp=self.store.create_experiment('EVAL-test')
        self.store.save_candidate(exp,'A',DEFAULT_PIPELINE_CONFIG,{'candidate_label':'A','round':1})
        c=self.store.candidate(exp+'-A')
        self.store.skip_candidate(c['id'],'fixture','未运行跳过')
        self.assertEqual(self.store.experiment(exp)['evaluation_budget']['used'],0)
        with self.assertRaises(ValueError):self.store.reserve_candidate_evaluation(c['id'])

    def test_skip_and_authorization_api_are_persistent_and_origin_protected(self):
        from fastapi.testclient import TestClient
        from api_fixture import main
        exp=self.store.create_experiment('EVAL-test')
        self.store.save_candidate(exp,'A',DEFAULT_PIPELINE_CONFIG,{'candidate_label':'A','round':1})
        client=TestClient(main.app)
        with patch.object(main,'store',self.store):
            denied=client.post('/api/runtime-settings/unattended',headers={'Origin':'https://untrusted.invalid'},json={'enabled':True,'actor':'fixture'})
            self.assertEqual(denied.status_code,403)
            auth=client.post('/api/runtime-settings/unattended',json={'enabled':True,'actor':'用户 2026-11-05 授权'})
            self.assertEqual(auth.status_code,200,auth.text)
            self.assertTrue(client.get('/api/runtime-settings').json()['unattended_authorization']['enabled'])
            skipped=client.post('/api/candidates/'+exp+'-A/skip',json={'actor':'fixture'})
            self.assertEqual(skipped.status_code,200,skipped.text)
            self.assertEqual(skipped.json()['status'],'skipped')
            self.assertEqual(self.store.experiment(exp)['evaluation_budget']['used'],0)
