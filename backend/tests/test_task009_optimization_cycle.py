"""Future batch control uses in-memory doubles, never real model calls."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch


class CycleTests(unittest.TestCase):
    def run_cycle(self, *, qualified_at=None, used=0, empty=False, technical=False):
        from app.optimization_cycle import run_until_qualified
        experiment = {'id':'exp','baseline_run_id':'base','result':{},'evaluation_budget':{'used':used},'candidates':[]}
        calls, states = [], []
        class Store:
            def experiment(self, _, **kwargs): return deepcopy(experiment)
            def require_current_baseline(self, _): return {'id':'base'}
        class Agent:
            def __init__(self, *args): pass
            def generate(self, *args, **kwargs):
                calls.append('analysis')
                if empty: return
                count=min(3,11-experiment['evaluation_budget']['used'])
                for n in range(count):
                    experiment['candidates'].append({'id':str(len(experiment['candidates'])),'status':'generated','reasoning':{'candidate_label':'ABC'[n]},'result':{}})
        class Runner:
            def __init__(self,*args): pass
            def run_candidate(self, cid, **kwargs):
                c=next(c for c in experiment['candidates'] if c['id']==cid)
                calls.append(cid);experiment['evaluation_budget']['used']+=1
                c.update(status='failed' if technical else 'evaluated',result={'qualification':{'qualified':qualified_at is not None and int(cid)>=qualified_at}})
                return c
        with patch('app.optimization_cycle.wait_for_off_peak'),patch('app.optimization_cycle.claim_cycle'),patch('app.optimization_cycle._save_state',side_effect=lambda s,e,**kw:states.append(kw)),patch('app.optimization_cycle.OptimizationAgent',Agent),patch('app.optimization_cycle.EvaluationRunner',Runner):
            result=run_until_qualified(Store(), SimpleNamespace(provider=object()), 'exp')
        return result,experiment,calls,states

    def test_no_qualified_returns_to_analysis_and_reserves_d(self):
        result,exp,calls,states=self.run_cycle()
        self.assertEqual(exp['evaluation_budget']['used'],9)
        self.assertEqual(calls.count('analysis'),3)
        self.assertEqual(result['status'],'budget_exhausted')
        self.assertEqual(result['remaining'],3)
        self.assertEqual(result['reserved_for_d'],1)

    def test_qualified_stops_after_current_batch(self):
        result,exp,calls,_=self.run_cycle(qualified_at=3)
        self.assertEqual(exp['evaluation_budget']['used'],6)
        self.assertEqual(calls.count('analysis'),2)
        self.assertEqual(result['status'],'qualified')

    def test_empty_drafts_are_bounded_without_consuming_evaluation_budget(self):
        result,exp,calls,_=self.run_cycle(empty=True)
        self.assertEqual(calls.count('analysis'),3)
        self.assertEqual(exp['evaluation_budget']['used'],0)
        self.assertEqual(result['status'],'analysis_exhausted')

    def test_failure_without_checkpoint_stops_safely(self):
        result,exp,calls,_=self.run_cycle(technical=True)
        self.assertEqual(exp['evaluation_budget']['used'],1)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['last_error'])

if __name__=='__main__':unittest.main()
