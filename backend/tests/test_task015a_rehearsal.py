"""Synthetic-only post-Agent rehearsal. No network Provider and no formal DB."""
import json, os, unittest
from pathlib import Path
from unittest.mock import patch
import test_v14_api_lifecycle as fixtures
from test_v14_api_lifecycle import LifecycleService, LifecycleProvider, main
from app.optimization_cycle import run_until_qualified

class Stub(LifecycleProvider):
    class Settings(LifecycleProvider.Settings):
        baseline_thinking='max'
        judge_thinking='low'
    settings=Settings()
    def __init__(self): self.calls=[]
    def complete(self, system, prompt, **kwargs):
        if 'RAG优化Agent' not in system and '唯一Optimization Agent' not in system:
            return super().complete(system,prompt,**kwargs)
        data=json.loads(prompt); self.calls.append(data)
        if '唯一Optimization Agent' in system:
            winner=data['winner']; source=next(c for c in data['sources'] if c['reasoning'].get('direction')=='效率（降档 + 检索补偿）')
            return json.dumps(dict(should_generate_d=True,source_candidates=[winner['id'],source['id']],
                source_reasons={s['id']:'retain whole quality/efficiency source' for s in (winner,source)},
                proposed_config_diff={'generation_thinking':'off','hyde':True},hypothesis='组合质量与效率',
                root_cause='检索层问题',intervention_direction='stage_performance',
                evidence_assertions=[],root_cause_alignment='相同冻结题卷',complementary_capabilities='质量加降档补偿',
                expected_improvement='减少错题并降低耗时',risks='需完整回归',explanation='仅组合来源验证值'))
        n=len([c for c in self.calls if 'prior_sandbox_results' in c]); targets=[c['id'] for c in data['bad_cases']]
        diffs=[({'top_k':6,'prompt_strategy':'Tiered'},{'candidate_k':24},{'generation_thinking':'off','hyde':True}),
               ({'top_k':6,'prompt_strategy':'Completeness'},{'multi_query':2},{'generation_thinking':'high','rerank':'query_only'}),
               ({'min_score':0.1,'prompt_strategy':'Tiered'},{'multi_query':4},{'generation_thinking':'low','hyde':True})][min(n-1,2)]
        rows=[]
        for label,diff,direction in zip('ABC',diffs,['回答策略','检索召回增强','效率（降档 + 检索补偿）']):
            rows.append(dict(id=label,direction=direction,review_conclusion_ids=['L1'],action_name=f'离线第{n}轮{label}',config_diff=diff,
                hypothesis=f'第{n}轮{label}保存证据支持假设',why='验证保存的检索与安全错题',target_bad_cases=targets,
                root_cause='检索层问题',expected_improvement='减少错题或耗时',risk='完整回归验证',
                intervention_direction='stage_performance' if label=='C' else 'grounded_generation',evidence_assertions=[]))
        from agent_response_fixture import with_review
        return json.dumps(with_review({'candidates':rows},data))

class Service(LifecycleService):
    fail_d=False
    no_improvement=False
    round_one_no_improvement=False
    calls=0
    def answer(self,question,config):
        self.calls+=1
        used={**config}
        if self.no_improvement and config.get('candidate_id') or self.round_one_no_improvement and '-R1-' in config.get('candidate_id',''):
            used.update(top_k=4,prompt_strategy='Grounded')
        result=super().answer(question,used)
        row=next(r for r in self.store.questions() if r['question']==question)
        clarifiers=sorted(r['id'] for r in self.store.questions() if r.get('negative_subtype')=='insufficient_evidence')
        if clarifiers and row['id']==clarifiers[0]:result['answer']='错误答案'
        if self.fail_d and config.get('candidate_id','').endswith('-D') and row['raw'].get('coverage_slot')=='Q04':result['answer']='错误答案'
        return result


class RejectedRoundStub(Stub):
    def complete(self, system, prompt, **kwargs):
        raw=super().complete(system,prompt,**kwargs)
        if '唯一Optimization Agent' in system:
            value=json.loads(raw)
            data=json.loads(prompt)
            source=next(c for c in data['sources'] if c['config'].get('generation_thinking')=='low')
            value['source_candidates']=[data['winner']['id'],source['id']]
            value['proposed_config_diff']['generation_thinking']='low'
            return json.dumps(value)
        if 'RAG优化Agent' not in system:return raw
        data=json.loads(prompt)
        if not data['prior_sandbox_results']:return raw
        value=json.loads(raw)
        # The first second-round draft violates parameter disjointness.
        if 'validation_rejection' not in data:
            value['candidates'][0]['config_diff']={'multi_query':2}
            value['candidates'][1]['config_diff']={'multi_query':4}
        else:
            for row,diff in zip(value['candidates'],({'top_k':6,'prompt_strategy':'Tiered','min_score':.1},
                    {'multi_query':2},{'generation_thinking':'low','hyde':True})):
                row['config_diff']=diff
        return json.dumps(value)

class RehearsalTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from datetime import datetime, timezone
        clock=patch('app.paid_schedule.utc_now',return_value=datetime(2026,11,3,16,tzinfo=timezone.utc))
        clock.start();self.addCleanup(clock.stop)
        seed=tempfile.TemporaryDirectory(prefix='task015a-seed-');self.addCleanup(seed.cleanup)
        path=Path(seed.name)/'empty.json';path.write_text('{"cases":[]}')
        seed_patch=patch('app.governance.GOLDEN_DRAFT',path);seed_patch.start();self.addCleanup(seed_patch.stop)
        fixtures.ApiLifecycleTests.setUp(self)
        self.corpus.index_dir=Path(self.temp.name)/"corpus-index"
        self.corpus.index_dir.mkdir()
    post=fixtures.ApiLifecycleTests.post
    wait=fixtures.ApiLifecycleTests.wait
    join_workers=fixtures.ApiLifecycleTests.join_workers
    def bootstrap(self):
        self.provider=Stub();self.service.__class__=Service;self.service.provider=self.provider
        # Also reject accidental calls through configured production adapters.
        for name in ('app.providers.DeepSeekProvider.complete','app.knowledge_pipeline.AlibabaProvider._post_request'):
            blocker=patch(name,side_effect=AssertionError('Real Provider forbidden'));blocker.start();self.addCleanup(blocker.stop)
        plan=self.post('governance/coverage-preview',{'profile':'medium'})
        started=self.post('governance/generate',{'profile':'medium','plan_id':plan['plan_id']})
        run=self.wait('governance/generation-runs/'+started['run_id'],('completed','failed','needs_regeneration'))
        self.assertEqual(run['status'],'completed',run)
        for key in run['question_ids']:
            self.assertTrue(self.post(f'governance/questions/{key}/probe')['passed'])
            self.assertEqual(self.post(f'governance/questions/{key}/qc')['status'],'qc_passed')
        self.post('governance/review-batch',{'question_ids':run['question_ids'],'confirmed_manual_review':True})
        self.post('governance/generation-runs/'+started['run_id']+'/snapshot',{})
        baseline=self.post('evaluations/run',{'fresh':True})
        self.baseline=self.wait('evaluations/'+baseline['id'],('completed','failed'))
        self.assertEqual(self.baseline['status'],'completed',self.baseline)
        self.assertEqual(len(self.baseline['cases']),50)
        causes={c['result'].get('primary_root_cause') for c in self.store.bad_case_rows(self.baseline['id'])}
        self.assertIn('Safety',causes);self.assertTrue(causes & {'Ranking','Retrieval'})
        self.exp=self.post('experiments/run')['id']
        self.before=self.store.active_production()

    def snapshot(self,label):
        folder=os.getenv('RAG_015A_EVIDENCE_DIR')
        if not folder:return
        paths=['workspace','overview','documents','dataset?light=true','evaluation','bad-cases','optimization','versions','readiness','monitoring','pipeline']
        values={('/api/'+key.split('?')[0]):self.client.get('/api/'+key).json() for key in paths}
        Path(folder).mkdir(parents=True,exist_ok=True)
        Path(folder,label+'.json').write_text(json.dumps(values,ensure_ascii=False))

    def lifecycle(self,fail_d):
        self.bootstrap();self.service.fail_d=fail_d
        # This legacy D exercise explicitly runs all sources before the cycle checks Gate 2.
        from app.evaluation import EvaluationRunner
        for candidate in self.store.candidates(self.exp):
            EvaluationRunner(self.store,self.service).run_candidate(candidate['id'])
        cycle=run_until_qualified(self.store,self.service,self.exp)
        self.assertEqual(cycle['status'],'qualified',cycle)
        self.assertEqual(cycle['used'],3)
        rec=self.store.recommendation(self.exp)['result']
        self.assertEqual(rec['status'],'Needs Report Confirmation')
        self.snapshot('gate2')
        candidates=self.store.candidates(self.exp);winner=self.exp+'-R1-A'
        c=next(c for c in candidates if c['id'].endswith('-C'))
        self.assertTrue(c['result']['gates']['passed'],c['result']['gates'])
        self.assertEqual(c['result']['all_fixed_question_ids'],[])
        self.assertFalse(c['result']['qualification']['qualified'])
        self.post('experiments/'+self.exp+'/recommendation',{'candidate_id':winner,'actor':'offline'})
        d=self.post('experiments/'+self.exp+'/composite',{})
        self.assertEqual(d['status'],'generated',d)
        sources=[self.store.candidate(s['candidate_id']) for s in d['reasoning']['sources']]
        self.assertIn(c['id'],[s['id'] for s in sources])
        self.assertTrue(all(any(s['config'].get(k)==v for s in sources) for k,v in d['config'].items()))
        self.assertEqual(d['config']['generation_thinking'],'off')
        if not fail_d:
            # Seed synthetic prior attempt history to exercise the 11 -> 12 boundary.
            with self.store.connection() as db:
                for source,count in zip(candidates,[3,4,4]):
                    reasoning={**source['reasoning'],'sandbox_attempts':[{'attempt':n+1} for n in range(count)]}
                    db.execute('UPDATE candidate_configs SET reasoning_json=? WHERE id=?',(json.dumps(reasoning),source['id']))
            self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],11)
        # This real API preflight reproduces the efficiency-source mismatch.
        preflight=self.client.get('/api/candidates/'+d['id']+'/preflight')
        self.assertEqual(preflight.status_code,200,preflight.text)
        run=self.post('candidates/'+d['id']+'/run')
        result=self.wait('evaluations/'+run['id'],('completed','failed','partial'))
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(len(result['cases']),50)
        self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],4 if fail_d else 12)
        if not fail_d:
            with self.store.connection() as db:
                db.execute("INSERT INTO candidate_configs SELECT ?,experiment_id,'generated',config_json,reasoning_json,'{}',created_at FROM candidate_configs WHERE id=?",(d['id']+'-extra',d['id']))
            extra=self.client.post('/api/candidates/'+d['id']+'-extra/run',json={})
            self.assertEqual(extra.status_code,409,extra.text)
            self.assertIn('budget',extra.json()['detail'])
            with self.store.connection() as db:db.execute('DELETE FROM candidate_configs WHERE id=?',(d['id']+'-extra',))
        current=self.store.candidate(d['id']);self.assertEqual(current['result']['release_qualification']['qualified'],not fail_d)
        rec=self.store.refresh_recommendation(self.exp)
        selected=winner if fail_d else d['id'];self.assertEqual(rec['recommended_candidate'],selected)
        self.snapshot('d-failed' if fail_d else 'd-passed')
        version=self.post('candidates/'+selected+'/publish',{'decision':'approved','actor':'offline'})
        self.assertEqual(self.store.active_production()['config'],self.store.candidate(selected)['config'])
        versions=self.client.get('/api/versions').json();overview=self.client.get('/api/overview').json();workspace=self.client.get('/api/workspace').json()
        self.assertEqual(next(v for v in versions if v['status']=='active')['id'],version['id'])
        self.assertEqual(overview['production']['config'],version['config']);self.assertEqual(workspace['active_version'],version['id'])
        self.snapshot('published')
        question=next(r['question'] for r in self.store.questions() if r['raw'].get('coverage_slot')=='Q02')
        count=self.service.calls
        left=self.post('preview/scheme',{'question':question,'scheme_id':self.before['id']})
        right=self.post('preview/scheme',{'question':question,'scheme_id':version['id']})
        self.assertEqual(left['question'],right['question']);self.assertNotEqual(left['answer'],right['answer'])
        self.assertEqual(self.service.calls-count,2)
        folder=os.getenv('RAG_015A_EVIDENCE_DIR')
        if folder:Path(folder,'answers.json').write_text(json.dumps({'left':left,'right':right},ensure_ascii=False))
        from test_v14_probe_cost import bundle
        index=Path(self.temp.name)/'index';bundle(index)
        with patch('app.knowledge_pipeline.index_for_config',return_value=index):
            rolled=self.post('versions/'+self.before['id']+'/rollback',{'decision':'approved','actor':'offline'})
        self.assertEqual(rolled['config'],self.before['config']);self.snapshot('rolled-back')
        print('EVIDENCE',json.dumps({'baseline_bad':self.baseline['result']['bad_case_count'],'baseline_gates':self.baseline['result']['gates']['passed_count'],
            'baseline_causes':[c['result'].get('primary_root_cause') for c in self.store.bad_case_rows(self.baseline['id'])],
            'abc':[(c['reasoning']['candidate_label'],c['result']['qualification']['qualified'],c['result']['gates']['passed_count'],c['result']['all_fixed_question_ids']) for c in candidates],
            'D_release':not fail_d,'used':self.store.experiment(self.exp)['evaluation_budget']['used']},ensure_ascii=False))

    def test_source_guards_and_reserved_boundary(self):
        from copy import deepcopy
        from app.policy import composite_source_eligible
        source={'config':{'generation_thinking':'off'},'status':'evaluated','reasoning':{'direction':'效率（降档 + 检索补偿）'},
                'result':{'evaluation_identity':'same','regression':{'passed':True},'gates':{'passed':True},'all_fixed_question_ids':[]}}
        self.assertTrue(composite_source_eligible(source,'same'))
        for field,value in [('status','running'),('identity','other'),('regression',False),('gates',False),('direction','回答策略')]:
            c=deepcopy(source)
            if field=='status':c['status']=value
            elif field=='identity':c['result']['evaluation_identity']=value
            elif field=='direction':c['reasoning']['direction']=value
            else:c['result'][field]['passed']=value
            self.assertFalse(composite_source_eligible(c,'same'),field)
        from test_task009_optimization_cycle import CycleTests
        state,exp,calls,_=CycleTests().run_cycle(used=11)
        self.assertEqual(state['status'],'budget_exhausted');self.assertEqual(state['remaining'],1)
        self.assertEqual(calls,[])

    def test_d_pass_publish_compare_rollback(self):self.lifecycle(False)
    def test_confirmed_winner_survives_d_decline(self):
        import tempfile
        from app.governance import GovernanceStore
        from identity_fixture import completed_baseline, comparison_identity
        from app.policy import DEFAULT_PIPELINE_CONFIG
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'winner.db')
            with patch('identity_fixture.current_manifest',return_value={'sources':fixtures.FINGERPRINT}):base=completed_baseline(store)
            exp=store.create_experiment(base)
            for label,bad in [('A',0),('B',1)]:
                store.save_candidate(exp,label,{**DEFAULT_PIPELINE_CONFIG,'top_k':6 if label=='A' else 4,'min_score':0.1 if label=='B' else 0},
                    {'candidate_label':label,'round':1})
                store.finish_candidate(exp+'-'+label,'evaluated',{**comparison_identity(store,base),'bad_case_count':bad,'qualification':{'qualified':True},'release_qualification':{'qualified':True}})
            store.confirm_experiment_report(exp,exp+'-B','offline')
            with store.connection() as db:
                row=store.experiment(exp)['result'];row['composite']={'status':'no_effective_composite'}
                db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(row),exp))
            self.assertEqual(store.refresh_recommendation(exp)['recommended_candidate'],exp+'-B')
    def test_d_fail_keeps_winner_publish_compare_rollback(self):self.lifecycle(True)
    def test_real_agent_round_two_input_and_budget_stop(self):
        self.bootstrap();self.service.no_improvement=True
        cycle=run_until_qualified(self.store,self.service,self.exp)
        prompts=[p for p in self.provider.calls if 'prior_sandbox_results' in p]
        self.assertGreaterEqual(len(prompts),2)
        self.assertEqual(len(prompts[1]['prior_sandbox_results']),3)
        self.assertTrue(all(c['status']=='evaluated' and c['result']['qualification']['qualified'] is False for c in prompts[1]['prior_sandbox_results']))
        self.snapshot('budget')
        self.assertEqual(cycle['status'],'budget_exhausted',cycle)
        self.assertEqual(cycle['used'],9)
        self.assertEqual(cycle['remaining'],3)
        self.assertIn('完整',cycle['last_error'])
        print('BUDGET',json.dumps(cycle,ensure_ascii=False))

    def test_rejected_round_regenerates_then_qualified_gate2_d_recommendation(self):
        self.bootstrap()
        initial_calls=self.provider.calls
        self.provider=RejectedRoundStub();self.provider.calls=initial_calls;self.service.provider=self.provider
        self.service.round_one_no_improvement=True
        cycle=run_until_qualified(self.store,self.service,self.exp)
        self.assertEqual(cycle['status'],'qualified',cycle)
        self.assertEqual(cycle['used'],6)
        prompts=[p for p in self.provider.calls if 'prior_sandbox_results' in p]
        self.assertEqual(len(prompts),3)
        self.assertIn('共用参数',prompts[2]['validation_rejection']['reason'])
        self.assertEqual(prompts[1]['evaluation_budget']['used'],prompts[2]['evaluation_budget']['used'])
        self.assertEqual(len(prompts[2]['baseline_performance']['slowest_questions']),5)
        self.assertTrue(all(len(c['performance']['slowest_questions'])==5 for c in prompts[2]['prior_sandbox_results']))
        self.assertTrue(all(c['status']=='evaluated' for c in prompts[2]['prior_sandbox_results']))
        candidates=self.store.candidates(self.exp)
        self.assertTrue(all(c['result']['qualification']['qualified'] is False for c in candidates if c['reasoning']['round']==1))
        winner=self.exp+'-R2-A'
        self.assertTrue(self.store.candidate(winner)['result']['qualification']['qualified'])
        self.post('experiments/'+self.exp+'/recommendation',{'candidate_id':winner,'actor':'offline'})
        d=self.post('experiments/'+self.exp+'/composite',{})
        self.assertEqual(d['status'],'generated',d)
        run=self.post('candidates/'+d['id']+'/run')
        result=self.wait('evaluations/'+run['id'],('completed','failed','partial'))
        self.assertEqual(result['status'],'completed',result)
        self.join_workers()
        self.assertTrue(self.store.candidate(d['id'])['result']['release_qualification']['qualified'])
        rec=self.store.refresh_recommendation(self.exp)
        self.assertEqual(rec['recommended_candidate'],d['id'])
        self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],7)
        print('TASK016A_REHEARSAL',json.dumps({'rounds':2,'rejected_regenerations':1,'sandbox_used':7,
            'cycle':cycle['status'],'gate2':winner,'d_release_qualified':True,'recommended':d['id']},ensure_ascii=False))
