"""Task 006 batch recovery: synthetic questions and disposable databases only."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_baseline_resume as baseline_fixture
import test_candidate_review_export as quality_fixture
from api_fixture import main
from app.evaluation import EvaluationRunner
from app.providers import ProviderAPIError, ProviderTimeout


class BaselineBatchRecoveryTests(unittest.TestCase):
    setUp = baseline_fixture.ResumeTests.setUp
    tearDown = baseline_fixture.ResumeTests.tearDown

    def execute(self):
        with patch('app.evaluation.time.sleep'):
            return self.runner.execute_baseline(*self.runner.start_baseline())

    def test_failed_question_gets_one_final_pass_after_other_questions(self):
        self.runtime.fail = None
        original = self.runtime.answer
        attempts = []
        def answer(question, config):
            attempts.append(question)
            if question == 'Q2' and attempts.count('Q2') == 1:
                error = ProviderTimeout('SSL fixture exhausted after three HTTP attempts')
                error.provider_retry_exhausted = True
                raise error
            return original(question, config)
        self.runtime.answer = answer
        result = self.execute()
        self.assertEqual(attempts, ['Q1', 'Q2', 'Q3', 'Q4', 'Q2'])
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(result['result']['evaluation_complete'])
        self.assertEqual(result['result']['technical_failed'], 0)

    def test_persisting_failure_finishes_without_business_fail_or_score(self):
        result = self.execute()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['result']['completed'], 3)
        self.assertEqual(result['result']['technical_failed'], 1)
        self.assertFalse(result['result']['evaluation_complete'])
        self.assertIsNone(result['result']['gates']['passed'])
        self.assertEqual(self.runtime.answers, ['Q1', 'Q2', 'Q3', 'Q4'])
        self.assertEqual(self.runtime.judges.count('Q2'), 2)
        self.assertFalse(self.store.bad_case_rows())
        self.runtime.fail = None
        child = self.runner.execute_baseline(*self.runner.start_baseline(result['id']))
        self.assertTrue(child['result']['evaluation_complete'])
        self.assertEqual(self.runtime.answers, ['Q1', 'Q2', 'Q3', 'Q4'])

    def test_401_stops_without_final_pass(self):
        original = self.runtime.answer
        def answer(question, config):
            if question == 'Q2':
                raise ProviderAPIError('HTTP 401 fixture original', status_code=401)
            return original(question, config)
        self.runtime.answer = answer
        result = self.execute()
        self.assertEqual(result['status'], 'partial')
        self.assertIn('HTTP 401 fixture original', result['error_message'])
        self.assertEqual(self.runtime.answers, ['Q1'])

    def test_answer_replay_continues_and_tail_retries_judge_without_generation(self):
        self.runtime.fail = None
        completed = self.execute()
        run_id, items, executions = self.runner.start_replay(completed['id'])
        original = self.runner.score_execution
        calls=[]
        def score(item, execution, **kwargs):
            calls.append(item['id'])
            if item['id']=='Q2' and calls.count('Q2')==1:
                raise ProviderTimeout('fixture replay exhausted')
            return original(item, execution, **kwargs)
        before=list(self.runtime.answers)
        with patch.object(self.runner, 'score_execution', side_effect=score):
            replay=self.runner.execute_replay(run_id, items, executions)
        self.assertEqual(calls, ['Q1','Q2','Q3','Q4','Q2'])
        self.assertEqual(replay['status'], 'completed')
        self.assertEqual(replay['result']['technical_failed'], 0)
        self.assertEqual(self.runtime.answers, before)
        self.assertTrue(replay['result']['checkpoints']['Q2']['attempts'])


class QualityBatchRecoveryTests(unittest.TestCase):
    setUp = quality_fixture.CandidateReviewExportTests.setUp
    join_workers = quality_fixture.CandidateReviewExportTests.join_workers
    quality_result = quality_fixture.CandidateReviewExportTests.quality_result

    def run_batch(self, quality):
        ids = [row['id'] for row in self.rows]
        service = SimpleNamespace(retriever=None, answerability_check=None,
                                  negative_subtype_check=None, quality_check=quality)
        def probe(key, *_args, **_kwargs):
            _, identity = self.store.capture_quality(key)
            return self.store.record_probe_result(key, {'question_quality':30,
                'golden_answer_quality':30, 'evidence_support':40, 'reason':'synthetic fixture',
                'probe_details':{'probe_execution_status':'completed'}}, execution=identity)
        self.store.update_quality_rerun(self.run_id, {'status':'running'}, start=True)
        with patch.object(self.store, 'run_probe', side_effect=probe):
            main._run_quality_rerun(self.run_id, ids, self.store, service, main.corpus)
        return ids, self.store.generation_run(self.run_id, qualification=False)['artifacts']['hard_validation']['quality_rerun']

    def reply(self):
        return {'score':90, 'priority':'P2', 'reason':'synthetic fixture', 'ablation_valid':True}

    def test_tail_retry_reuses_probe_and_other_completed_questions(self):
        calls = []
        target = self.rows[1]['id']
        def qc(item):
            calls.append(item['id'])
            if item['id'] == target and calls.count(target) == 1:
                raise ProviderTimeout('fixture transient exhausted')
            return self.reply()
        ids, state = self.run_batch(qc)
        self.assertEqual(calls, ids + [target])
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['technical_failed'], 0)
        self.assertEqual(state['completed'], 20)
        self.assertEqual(state['qc_passed'], 20)
        self.assertEqual(len(self.store.probe_history(target)), 1)

    def test_exhausted_question_kept_technical_and_next_question_runs(self):
        target = self.rows[0]['id']; calls=[]
        def qc(item):
            calls.append(item['id'])
            if item['id'] == target:
                raise ProviderTimeout('fixture original exhausted')
            return self.reply()
        ids, state = self.run_batch(qc)
        self.assertEqual(calls, ids + [target])
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['completed'], 20)
        self.assertEqual(state['technical_failed'], 1)
        self.assertEqual(state['qc_passed'], 19)
        self.assertIn('fixture original exhausted', state['slots']['Q01']['error'])
        self.assertEqual(self.store.qc_history(target), [])

    def test_permanent_error_stops_whole_batch(self):
        calls=[]
        def qc(item):
            calls.append(item['id'])
            raise ProviderAPIError('HTTP 401 original fixture', status_code=401)
        _, state = self.run_batch(qc)
        self.assertEqual(len(calls), 1)
        self.assertEqual(state['status'], 'failed')
        self.assertIn('HTTP 401 original fixture', state['error'])

    def test_same_run_anomalies_resume_preserves_four_done_and_q05_embedding(self):
        from app.evaluation_stage import perform_stage, checkpoint_request
        from app.providers import ProviderUnavailable
        ids=[row['id'] for row in self.rows]; target=ids[4]
        for key in ids[:4]:
            quality_fixture.CandidateReviewExportTests.quality_history(self,key)
        _,identity=self.store.capture_quality(target)
        cp={'identity':{k:v for k,v in identity.items() if k!='probe_id'}, 'attempts':[]}
        embeddings=[];reranks=[];probes=[];qcs=[]
        def embedding(key):
            embeddings.append(key); return [[1.0]]
        def interrupted_probe():
            checkpoint_request('fixture','embedding','embed',{'key':target},lambda:embedding(target))
            error=ProviderUnavailable('fixture old SSL error')
            error.request_execution_unknown=True
            raise error
        with self.assertRaises(ProviderUnavailable):
            perform_stage(cp,'probe',interrupted_probe,'old-worker',automatic=False,
                          check_stop=lambda:None,on_state=lambda *_args,**_kwargs:None)
        self.store.update_quality_rerun(self.run_id,{'status':'failed','checkpoints':{target:cp}})
        selected=self.store.update_quality_rerun(self.run_id,{'status':'running'},start=True,anomalies_only=True)
        self.assertEqual(selected,ids[4:])
        def probe(key,*_args,**_kwargs):
            probes.append(key)
            checkpoint_request('fixture','embedding','embed',{'key':key},lambda:embedding(key))
            checkpoint_request('fixture','rerank','rank',{'key':key},lambda:reranks.append(key))
            _,binding=self.store.capture_quality(key)
            return self.store.record_probe_result(key,{'question_quality':30,'golden_answer_quality':30,
                'evidence_support':40,'reason':'synthetic fixture','probe_details':{'probe_execution_status':'completed'}},execution=binding)
        def qc(item):
            qcs.append(item['id']);return self.reply()
        service=SimpleNamespace(retriever=None,answerability_check=None,negative_subtype_check=None,quality_check=qc)
        with patch.object(self.store,'run_probe',side_effect=probe):
            main._run_quality_rerun(self.run_id,selected,self.store,service,main.corpus)
        self.assertEqual(probes,ids[4:]);self.assertEqual(qcs,ids[4:])
        self.assertEqual(embeddings.count(target),1)
        self.assertEqual(reranks.count(target),1)
        self.assertTrue(all(len(self.store.qc_history(key))==1 for key in ids))
        state=self.store.generation_run(self.run_id,qualification=False)['artifacts']['hard_validation']['quality_rerun']
        self.assertEqual(state['status'],'completed');self.assertEqual(state['technical_failed'],0)

    def test_original_generation_quality_uses_batch_recovery(self):
        self.store.update_generation_run(self.run_id,status='probing')
        calls=[];target=self.rows[1]['id']
        def qc(item):
            calls.append(item['id'])
            if item['id']==target and calls.count(target)==1:raise ProviderTimeout('fixture original quality')
            return self.reply()
        def probe(key,*_args,**_kwargs):
            _,binding=self.store.capture_quality(key)
            return self.store.record_probe_result(key,{'question_quality':30,'golden_answer_quality':30,
                'evidence_support':40,'reason':'synthetic fixture','probe_details':{'probe_execution_status':'completed'}},execution=binding)
        service=SimpleNamespace(retriever=None,answerability_check=None,negative_subtype_check=None,quality_check=qc)
        with patch.object(self.store,'run_probe',side_effect=probe):
            main._run_mini_generation_work(self.run_id,self.store,service,main.corpus,resume_quality=True)
        self.assertEqual(calls,[row['id'] for row in self.rows]+[target])
        run=self.store.generation_run(self.run_id,qualification=False)
        self.assertEqual(run['status'],'completed')
        self.assertEqual(run['artifacts']['hard_validation']['quality_rerun']['technical_failed'],0)
        self.assertEqual(run['artifacts']['hard_validation']['progress']['qc_completed'],20)

    def test_wrapped_invalid_probe_reply_tail_retry_retires_deepseek_only(self):
        from app.evaluation_stage import checkpoint_request
        from app.providers import ProviderUnavailable
        target=self.rows[0]['id'];embedding=[];judge=[]
        def probe(key,*_args,**_kwargs):
            checkpoint_request('Alibaba','embed','embedding',{'key':key},lambda:embedding.append(key))
            def response():
                judge.append(key);return '{}' if key==target and judge.count(key)==1 else 'valid'
            text=checkpoint_request('DeepSeek','fixture','judge',{'key':key},response)
            if text=='{}':
                try:raise ValueError('fixture missing answerable field')
                except ValueError as error:
                    raise ProviderUnavailable('DeepSeek Answerability 未返回有效 JSON') from error
            _,binding=self.store.capture_quality(key)
            return self.store.record_probe_result(key,{'question_quality':30,'golden_answer_quality':30,
                'evidence_support':40,'reason':'synthetic fixture','probe_details':{'probe_execution_status':'completed'}},execution=binding)
        ids=[row['id'] for row in self.rows]
        service=SimpleNamespace(retriever=None,answerability_check=None,negative_subtype_check=None,quality_check=lambda _item:self.reply())
        self.store.update_quality_rerun(self.run_id,{'status':'running'},start=True)
        with patch.object(self.store,'run_probe',side_effect=probe):
            main._run_quality_rerun(self.run_id,ids,self.store,service,main.corpus)
        state=self.store.generation_run(self.run_id,qualification=False)['artifacts']['hard_validation']['quality_rerun']
        self.assertEqual(state['technical_failed'],0)
        self.assertEqual(embedding.count(target),1)
        self.assertEqual(judge.count(target),2)
        self.assertTrue(state['checkpoints'][target]['manual_resume_history'][0]['provider_requests'])

    def test_revision_does_not_multiply_http_retries(self):
        run={'runtime_attempts':[]}
        store=SimpleNamespace(revision_run=lambda _key:run,update_revision=lambda _key,**values:run.update(values))
        def work():raise ProviderTimeout('fixture three HTTP tries already exhausted')
        with patch.object(main,'ProviderTimeout',ProviderTimeout):
            with self.assertRaises(ProviderTimeout):
                main._revision_attempt(store,'fixture','qc',SimpleNamespace(model='fixture'),work)
        self.assertEqual(len(run['runtime_attempts']),1)

    def test_recovery_mid_final_pass_does_not_repeat_already_failed_final_retry(self):
        ids=[row['id'] for row in self.rows];calls=[]
        def qc(item):
            key=item['id'];calls.append(key)
            if key==ids[0]:raise ProviderTimeout('fixture remains exhausted')
            if key==ids[1] and calls.count(key)==1:raise ProviderTimeout('fixture first pass')
            if key==ids[1] and calls.count(key)==2:raise KeyboardInterrupt('fixture worker crash')
            return self.reply()
        def probe(key,*_args,**_kwargs):
            _,identity=self.store.capture_quality(key)
            return self.store.record_probe_result(key,{'question_quality':30,'golden_answer_quality':30,
                'evidence_support':40,'reason':'synthetic fixture','probe_details':{'probe_execution_status':'completed'}},execution=identity)
        service=SimpleNamespace(retriever=None,answerability_check=None,negative_subtype_check=None,quality_check=qc)
        self.store.update_quality_rerun(self.run_id,{'status':'running'},start=True)
        with patch.object(self.store,'run_probe',side_effect=probe):
            with self.assertRaises(KeyboardInterrupt):
                main._run_quality_rerun(self.run_id,ids,self.store,service,main.corpus)
            state=self.store.generation_run(self.run_id,qualification=False)['artifacts']['hard_validation']['quality_rerun']
            self.assertTrue(state['final_retry_started'])
            self.assertTrue(state['slots']['Q01']['final_retry_done'])
            main._run_quality_rerun(self.run_id,ids,self.store,service,main.corpus)
        state=self.store.generation_run(self.run_id,qualification=False)['artifacts']['hard_validation']['quality_rerun']
        self.assertEqual(state['status'],'completed');self.assertEqual(state['technical_failed'],1)
        self.assertEqual(calls.count(ids[0]),2)
        self.assertEqual(calls.count(ids[1]),3)
        self.assertTrue(all(calls.count(key)==1 for key in ids[2:]))

    def test_qc_network_failure_keeps_completed_subrequest_checkpoint(self):
        from app.evaluation_stage import checkpoint_request
        target=self.rows[0]['id'];first=[];second=[]
        def qc(item):
            if item['id']==target:
                checkpoint_request('DeepSeek','fixture','first',{'key':target},lambda:first.append(target))
                def next_request():
                    second.append(target)
                    if len(second)==1:raise ProviderTimeout('fixture second RPC exhausted')
                    return self.reply()
                return checkpoint_request('DeepSeek','fixture','second',{'key':target},next_request)
            return self.reply()
        _,state=self.run_batch(qc)
        self.assertEqual(state['status'],'completed');self.assertEqual(state['technical_failed'],0)
        self.assertEqual(len(first),1);self.assertEqual(len(second),2)

    def test_paired_revision_quality_continues_then_retries_only_technical_failure(self):
        run={'question_ids':['one','two'],'generation_run_id':'fixture','quality_results':{},'runtime_attempts':[]}
        finished={};calls=[]
        def update(_key,**values):run.update(values)
        def finish(_key,results,**kwargs):finished.update(results=results,**kwargs)
        store=SimpleNamespace(revision_run=lambda _key:run,update_revision=update,
            question=lambda key:{'id':key,'raw':{},'qc_status':'qc_passed' if key in finished else 'qc_pending'},
            revision_quality_step=lambda _run,key:'qc',finish_revision_quality=finish)
        def qc(_store,_service,key):
            calls.append(key)
            if key=='one' and calls.count(key)==1:raise ProviderTimeout('fixture paired QC exhausted')
            return {'reason':'synthetic fixture'},{'status':'qc_passed'}
        with patch.object(main,'_quality_check',side_effect=qc):
            main._run_revision_quality('fixture',store,SimpleNamespace(model='fixture'),SimpleNamespace(chunks=lambda:[]))
        self.assertEqual(calls,['one','two','one'])
        self.assertNotIn('error',finished)
        self.assertTrue(all(v['qc']=='qc_passed' for v in finished['results'].values()))
        self.assertEqual(len(run['runtime_attempts']),3)
