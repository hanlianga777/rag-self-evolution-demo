"""Offline A/B/C recovery checks: completed Stub questions never repeat."""
import unittest
import tempfile
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch


class CycleRecoveryTests(unittest.TestCase):
    def exercise(self, *, repeated=False, stopped=False, restart=False, account_failure=False, current_round_only=False):
        from app.optimization_cycle import run_until_qualified
        candidates = [{'id':label, 'status':'generated', 'reasoning':{'candidate_label':label, 'round':1}, 'result':{}}
                      for label in 'ABC']
        exp = {'id':'exp', 'baseline_run_id':'base', 'result':{}, 'evaluation_budget':{'used':0}, 'candidates':candidates}
        if current_round_only:exp['result']['optimization_cycle']={'current_round_only':True}
        completed = {label:set() for label in 'ABC'}
        calls, tries, states = [], {}, []
        class Store:
            def experiment(self, _, **kwargs): return deepcopy(exp)
            def require_current_baseline(self, _): return {'id':'base'}
            def candidate(self, cid): return deepcopy(next(c for c in candidates if c['id']==cid))
            def evaluation_run(self, rid):
                cid=rid.split('-')[-1]
                return {'id':rid, 'status':'partial', 'result':{'stop_request':{'reason':'user'} if stopped else None,
                    'technical_errors':[{'error':'database is locked', 'error_type':'OperationalError',
                        'provider_error':{'http_status':402} if account_failure else {}}]}, 'error_message':'database is locked'}
        class Runner:
            def __init__(self, *_): pass
            def candidate_resume_plan(self, cid): return {'can_resume':True, 'source_run_id':'run-'+cid}
            def run_candidate(self, cid, **_):
                candidate=next(c for c in candidates if c['id']==cid)
                tries[cid]=tries.get(cid,0)+1
                for q in range(50):
                    if q in completed[cid]: continue
                    if cid=='A' and q==25 and (tries[cid]==1 or repeated):
                        candidate.update(status='failed', result={'evaluation_complete':False, 'evaluation_run_id':'run-A'})
                        return deepcopy(candidate)
                    completed[cid].add(q);calls.append((cid,q))
                exp['evaluation_budget']['used']+=1
                candidate.update(status='evaluated', result={'evaluation_complete':True, 'qualification':{'qualified':cid=='C' and not current_round_only}})
                return deepcopy(candidate)
            def recover_run(self, rid):
                return self.run_candidate(rid.split('-')[-1])
        if restart:
            candidates[0].update(status='running',result={'evaluation_run_id':'run-A'})
            completed['A'].update(range(25));calls.extend(('A',q) for q in range(25))
            tries['A']=1
        with patch('app.optimization_cycle.claim_cycle'), patch('app.optimization_cycle._save_state', side_effect=lambda s,e,**kw:states.append(kw)), \
             patch('app.optimization_cycle.EvaluationRunner',Runner), patch('app.optimization_cycle.OptimizationAgent') as agent:
            if current_round_only:agent.return_value.generate.side_effect=AssertionError('本轮续跑不能重新生成方案')
            result=run_until_qualified(Store(),SimpleNamespace(provider=object()),'exp')
        return result, exp, calls, tries

    def test_a_50_question_checkpoint_continues_through_b_c_without_duplicate_calls(self):
        result,exp,calls,tries=self.exercise()
        self.assertEqual(result['status'],'qualified')
        self.assertEqual(len(calls),150)
        self.assertEqual(len(set(calls)),150)
        self.assertEqual(exp['evaluation_budget']['used'],3)
        self.assertEqual(tries,{'A':2,'B':1,'C':1})

    def test_explicit_current_round_stops_after_abc_without_generating_new_plans(self):
        result,exp,calls,tries=self.exercise(current_round_only=True)
        self.assertEqual(result['status'],'round_completed')
        self.assertEqual(len(set(calls)),150)
        self.assertEqual(exp['evaluation_budget']['used'],3)

    def test_repeated_same_failure_stops_after_two_resumes(self):
        result,_,calls,tries=self.exercise(repeated=True)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(tries,{'A':3})
        self.assertEqual(len(calls),25)
        self.assertIn('2',result['last_error'])

    def test_user_stop_does_not_resume(self):
        result,_,_,tries=self.exercise(stopped=True)
        self.assertEqual(result['status'],'stopped')
        self.assertEqual(tries,{'A':1})

    def test_provider_balance_failure_does_not_resume(self):
        result,_,_,tries=self.exercise(account_failure=True)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(tries,{'A':1})

    def test_restart_running_a_uses_saved_questions_then_continues_b_c(self):
        result,exp,calls,_=self.exercise(restart=True)
        self.assertEqual(result['status'],'qualified')
        self.assertEqual(len(calls),150)
        self.assertEqual(len(set(calls)),150)
        self.assertEqual(exp['evaluation_budget']['used'],3)

    def test_restart_monitor_claims_dead_cycle_once_in_temporary_database(self):
        from app.governance import GovernanceStore
        from app.optimization_cycle import recover_optimization_cycles, _save_state
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'temporary.sqlite')
            experiment_id=store.create_experiment('fixture-baseline')
            _save_state(store,experiment_id,status='running',owner_pid=99999999,worker_thread=7)
            with patch('app.optimization_cycle.threading.Thread') as thread:
                recover_optimization_cycles(store,SimpleNamespace(provider=object()))
                recover_optimization_cycles(store,SimpleNamespace(provider=object()))
            self.assertEqual(thread.call_count,1)
            thread.return_value.start.assert_called_once()
            state=store.experiment(experiment_id)['result']['optimization_cycle']
            self.assertEqual(state['status'],'running')
            self.assertIsNone(state['worker_thread'])


if __name__=='__main__':unittest.main()
