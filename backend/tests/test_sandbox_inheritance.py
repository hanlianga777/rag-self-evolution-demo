"""Sandbox lineage and Provider payload checks; isolated DB, no network calls."""
import json,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_baseline_resume as fixture
from api_fixture import main
from app.paid_run import PaidRun,controlled_run,provider_task
from app.providers import DeepSeekProvider
from app.config import Settings


class SandboxInheritanceTests(unittest.TestCase):
    def setUp(self):
        fixture.ResumeTests.setUp(self);self.runtime.fail=None;self.serial=0
    def tearDown(self):fixture.ResumeTests.tearDown(self)

    def baseline_and_candidates(self,limits):
        self.serial+=1
        paid=PaidRun(Path(self.tmp.name)/f'baseline-{self.serial}.json',10.,{}, {},output_limits=limits)
        with controlled_run(paid):baseline=self.runner.run_baseline()
        exp=self.store.create_experiment(baseline['id'],'completed')
        base={k:v for k,v in baseline['config'].items() if k!='run_target'}
        configs=[{**base,'prompt_strategy':'Grounded'},{**base,'query_rewrite':True,'multi_query':2},
                 {**base,'metadata_filter':'FALLBACK'}]
        for label,config in zip('ABC',configs):
            self.store.save_candidate(exp,'R1-'+label,config,{'round':1,'candidate_label':label})
        return baseline,exp,configs

    def test_different_datasets_and_limits_reach_actual_provider_payload(self):
        payloads=[];provider=DeepSeekProvider(Settings('fixture','https://unused.invalid','fixture'))
        original=self.runtime.answer
        def answer(*args,**kwargs):
            for task in ('answer','judge','query'):
                with provider_task(task):payloads.append((task,json.loads(provider._request('system','user',task=='judge',False).data)))
            return original(*args,**kwargs)
        snapshots=[];old_candidates=[]
        for number,limits in enumerate(({'answer':1024,'judge':4096,'query':512},{'answer':2048,'judge':8192,'query':1024})):
            if number:
                snapshot=deepcopy(self.store.dataset_snapshots()[0]['snapshot']);snapshot.pop('id')
                with self.store.connection() as c:
                    c.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)',('new-golden','approved','fixture',json.dumps(snapshot),'99999'))
            baseline,exp,configs=self.baseline_and_candidates(limits);snapshots.append(deepcopy(baseline))
            with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime),patch.object(self.runtime,'answer',side_effect=answer):
                with TestClient(main.app) as client:
                    for label,config in zip('ABC',configs):
                        cid=exp+'-R1-'+label;before=len(payloads)
                        preview=client.get('/api/candidates/'+cid+'/preflight')
                        self.assertEqual(preview.status_code,200,preview.text)
                        self.assertEqual(preview.json()['request_limits'],limits)
                        self.assertEqual(preview.json()['baseline_run_id'],baseline['id'])
                        self.assertEqual(preview.json()['config']['prompt_strategy'],config['prompt_strategy'])
                        self.assertEqual(len(payloads),before)
                        result=self.runner.run_candidate(cid, automatic=False)
                        self.assertEqual(result['status'],'evaluated')
                        self.assertEqual(self.store.candidate(cid)['config'],config)
                        self.assertEqual(self.store.evaluation_run(result['result']['evaluation_run_id'])['judge'],baseline['judge'])
                        self.assertTrue(all(p['max_tokens']==limits[t] for t,p in payloads[before:]))
            if not number:old_candidates=[deepcopy(self.store.candidate(exp+'-R1-'+x)) for x in 'ABC'];old_exp=deepcopy(self.store.experiment(exp))
        self.assertNotEqual(snapshots[0]['judge']['evaluation_identity'],snapshots[1]['judge']['evaluation_identity'])
        self.assertEqual(self.store.experiment(old_exp['id']),old_exp)
        self.assertEqual([self.store.candidate(x['id']) for x in old_candidates],old_candidates)
        with self.assertRaisesRegex(ValueError,'旧实验'):
            self.runner.candidate_inputs(old_candidates[0]['id'])
        for baseline in snapshots:self.assertEqual(self.store.evaluation_run(baseline['id']),baseline)

    def test_same_golden_new_baseline_does_not_rebind_old_candidate(self):
        first,old_exp,_=self.baseline_and_candidates({'answer':512,'judge':2048,'query':256})
        old=deepcopy(self.store.candidate(old_exp+'-R1-A'))
        second,new_exp,_=self.baseline_and_candidates({'answer':1024,'judge':4096,'query':512})
        self.assertEqual(first['dataset_version_id'],second['dataset_version_id'])
        self.assertNotEqual(first['judge']['evaluation_identity'],second['judge']['evaluation_identity'])
        with self.assertRaisesRegex(ValueError,'旧实验'):self.runner.start_candidate(old['id'])
        self.assertEqual(self.store.candidate(old['id']),old)
        self.assertEqual(self.store.experiment(old_exp)['baseline_run_id'],first['id'])
        self.assertEqual(self.runner.candidate_inputs(new_exp+'-R1-A')[-1]['id'],second['id'])

    def test_frozen_limits_checkpoint_resume_and_explicit_context(self):
        limits={'answer':1536,'judge':6144,'query':768};baseline,exp,_=self.baseline_and_candidates(limits)
        cid=exp+'-R1-A';self.runtime.fail='judge'
        first=self.runner.run_candidate(cid, automatic=False);source=self.store.evaluation_run(first['result']['evaluation_run_id'])
        self.runtime.fail=None
        paid=PaidRun(Path(self.tmp.name)/'candidate.json',10.,{}, {},output_limits=limits)
        with controlled_run(paid):result=self.runner.run_candidate(cid, automatic=False)
        self.assertEqual(result['status'],'evaluated')
        self.assertEqual(result['result']['resume_source_id'],source['id'])
        self.assertEqual(self.runtime.answers.count('Q2'),2) # One Baseline and one Candidate; resume reuses answer.
        self.assertEqual(self.store.evaluation_run(source['id']),source)
        self.assertEqual(self.store.evaluation_run(result['result']['evaluation_run_id'])['judge'],baseline['judge'])
        for changed in ({**limits,'judge':6145},{'answer':1536},None):
            bad=PaidRun(Path(self.tmp.name)/f'bad-{len(list(Path(self.tmp.name).glob("bad-*")))}.json',10.,{}, {},output_limits=changed)
            with controlled_run(bad),self.assertRaisesRegex(ValueError,'request limits must match'):
                self.runner.candidate_inputs(exp+'-R1-B')

    def test_preflight_rejects_illegal_parameters_and_identity_changes(self):
        baseline,exp,_=self.baseline_and_candidates({'answer':1024,'judge':4096,'query':512});cid=exp+'-R1-A'
        original=self.store.candidate(cid);before=self.store.experiment(exp)['evaluation_budget']['used']
        with self.store.connection() as c:
            c.execute('UPDATE candidate_configs SET config_json=? WHERE id=?',(json.dumps({**original['config'],'judge_model':'other'}),cid))
        with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime):
            with TestClient(main.app) as client:
                response=client.get('/api/candidates/'+cid+'/preflight')
                self.assertEqual(response.status_code,409)
                self.assertIn('Search Space',response.text)
        self.assertEqual(self.store.experiment(exp)['evaluation_budget']['used'],before)
        self.assertEqual(self.store.evaluation_run(baseline['id']),baseline)
