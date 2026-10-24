"""Offline RPC persistence and failure classification; never contacts a Provider."""
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from app.config import Settings
from app.evaluation_stage import perform_stage
from app.knowledge_pipeline import AlibabaProvider
from app.providers import DeepSeekProvider, ProviderAPIError, ProviderTimeout


class RequestCheckpointTests(unittest.TestCase):
    def stage(self, cp, action, run='one'):
        return perform_stage(cp, 'generation', action, run, automatic=True,
                             check_stop=lambda: None, on_state=lambda *a, **kw: None)

    def provider(self):
        return AlibabaProvider({'DASHSCOPE_API_KEY': 'fixture', 'DASHSCOPE_BASE_URL': 'https://fixture.invalid'})

    def test_completed_embedding_survives_failed_rerank_and_explicit_resume(self):
        calls = []
        def network(request, **kwargs):
            calls.append(request.full_url)
            if request.full_url.endswith('/embeddings'):
                return io.BytesIO(b'{"data":[{"index":0,"embedding":[1,2]}],"usage":{"total_tokens":2}}')
            if calls.count(request.full_url) <= 3:
                raise urllib.error.HTTPError(request.full_url, 429, 'limited', {}, io.BytesIO(b'{}'))
            return io.BytesIO(b'{"results":[{"index":0,"relevance_score":0.9}],"usage":{"total_tokens":2}}')
        cp = {'attempts': []}; provider = self.provider()
        def answer():
            provider.embed(['query'], 2)
            return provider.rerank('query', [{'content': 'fixture'}])
        with patch('urllib.request.urlopen', side_effect=network), patch('app.evaluation_stage.time.sleep'):
            with self.assertRaises(ProviderAPIError): self.stage(cp, answer)
            restored = json.loads(json.dumps(cp))
            self.stage(restored, answer, 'explicit-resume')
        self.assertEqual(sum(url.endswith('/embeddings') for url in calls), 1)

    def test_successful_rpc_is_durable_before_next_request_and_survives_worker_loss(self):
        cp = {'attempts': []}; saved = []
        def state(*a, **kw): saved.append(json.loads(json.dumps(cp)))
        def answer():
            self.provider().embed(['query'], 2)
            raise SystemExit('fixture worker loss after settled request')
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"data":[{"index":0,"embedding":[1,2]}],"usage":{"total_tokens":2}}')):
            with self.assertRaises(SystemExit):
                perform_stage(cp, 'generation', answer, 'one', automatic=True, check_stop=lambda: None, on_state=state)
        self.assertTrue(any(any(r.get('status') == 'completed' for r in s.get('provider_requests', {}).values()) for s in saved))
        from app.evaluation_stage import checkpoint_usage
        from app.paid_run import require_reconciled_execution
        self.assertEqual(len(checkpoint_usage(saved[-1])),1)
        with self.assertRaisesRegex(ValueError,'对账'):
            require_reconciled_execution({'checkpoints':{'Q1':saved[-1]}})

    def test_answer_rpc_reuses_full_response_without_recharging_usage(self):
        from app.evaluation_stage import checkpoint_usage
        provider = DeepSeekProvider(Settings('fixture','https://fixture.invalid','fixture'))
        cp = {'attempts': []}
        def fail_after_response():
            provider.complete('system','query')
            raise ValueError('fixture post-response local interruption')
        body = b'{"choices":[{"message":{"content":"answer"},"finish_reason":"stop"}],"usage":{"prompt_tokens":2,"completion_tokens":1}}'
        with patch('urllib.request.urlopen',return_value=io.BytesIO(body)) as request:
            with self.assertRaises(ValueError):self.stage(cp,fail_after_response)
            self.assertEqual(self.stage(json.loads(json.dumps(cp)),lambda:provider.complete('system','query'),'two'),'answer')
            self.assertEqual(request.call_count,1)
        self.assertEqual(len(checkpoint_usage(cp)),1)

    def test_deepseek_rejection_is_known_and_retries_only_three_times(self):
        provider = DeepSeekProvider(Settings('fixture', 'https://fixture.invalid', 'fixture'))
        def network(request, **kwargs):
            raise urllib.error.HTTPError(request.full_url, 429, 'limited', {}, io.BytesIO(b'{"error":{"code":"rate_limit"}}'))
        cp = {'attempts': []}
        with patch('urllib.request.urlopen', side_effect=network) as request, patch('app.evaluation_stage.time.sleep'):
            with self.assertRaises(ProviderAPIError): self.stage(cp, lambda: provider.complete('system', 'user'))
        self.assertEqual(request.call_count, 3)
        self.assertFalse(cp.get('unknown_execution', {}).get('generation', False))
        self.assertFalse(cp.get('unsettled_usage', {}).get('generation', False))

    def test_5xx_or_timeout_is_unknown_never_retried(self):
        for provider in (self.provider(), DeepSeekProvider(Settings('fixture', 'https://fixture.invalid', 'fixture'))):
            for fault in (TimeoutError('fixture'), urllib.error.HTTPError('https://fixture.invalid', 503, 'service', {}, io.BytesIO(b'{}'))):
                with self.subTest(provider=type(provider).__name__, fault=type(fault).__name__):
                    cp = {'attempts': []}
                    action = (lambda: provider._post('/embeddings', {'model':'text-embedding-v4'})) if isinstance(provider, AlibabaProvider) else (lambda: provider.complete('system', 'user'))
                    with patch('urllib.request.urlopen', side_effect=fault) as request:
                        with self.assertRaises((ProviderAPIError, ProviderTimeout)): self.stage(cp, action)
                    self.assertEqual(request.call_count, 1)
                    self.assertTrue(cp['unknown_execution']['generation'])

    def test_body_timeout_preserves_received_http_headers_without_claiming_completion(self):
        class Response(io.BytesIO):
            status = 200
            headers = {'x-request-id':'fixture-response-id'}
            def read(self,*args):raise TimeoutError('fixture body timeout')
        for provider in (self.provider(),DeepSeekProvider(Settings('fixture','https://fixture.invalid','fixture'))):
            action = (lambda:provider._post('/embeddings',{'model':'text-embedding-v4'})) if isinstance(provider,AlibabaProvider) else (lambda:provider.complete('system','user'))
            with patch('urllib.request.urlopen',return_value=Response()),self.assertRaises(ProviderTimeout) as caught:
                self.stage({'attempts':[]},action)
            metadata = caught.exception.response_metadata
            self.assertIs(metadata.get('http_response_received'),True)
            self.assertEqual(metadata['http_status'],200)
            self.assertEqual(metadata['request_id'],'fixture-response-id')
            self.assertTrue(metadata['request_execution_unknown'])

    def test_missing_usage_saves_rpc_result_and_blocks_another_request(self):
        from app.paid_run import require_reconciled_execution
        cp = {'attempts': []}
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"data":[{"index":0,"embedding":[1,2]}]}')) as request:
            with self.assertRaisesRegex(RuntimeError, 'Usage'):
                self.stage(cp, lambda: self.provider().embed(['query'], 2))
            self.assertTrue(any('result' in r for r in cp['provider_requests'].values()))
            with self.assertRaisesRegex(ValueError, '对账'):
                require_reconciled_execution({'checkpoints': {'Q1': cp}})
            self.assertEqual(request.call_count, 1)

    def test_invalid_embedding_is_audited_but_never_reused_as_success(self):
        from app.providers import ProviderInvalidResponse
        cp = {'attempts': []}; calls = []
        def network(*args, **kwargs):
            calls.append(1)
            vector = [1] if len(calls)<=2 else [1,2]
            return io.BytesIO(json.dumps({'data':[{'index':0,'embedding':vector}],'usage':{'total_tokens':2}}).encode())
        with patch('urllib.request.urlopen',side_effect=network),patch('app.evaluation_stage.time.sleep'):
            with self.assertRaises(ProviderInvalidResponse):self.stage(cp,lambda:self.provider().embed(['q'],2))
            self.assertFalse(any(r.get('status')=='completed' for r in cp['provider_requests'].values()))
            self.stage(json.loads(json.dumps(cp)),lambda:self.provider().embed(['q'],2),'two')
        self.assertEqual(len(calls),3)


class FiftyQuestionMatrixTests(unittest.TestCase):
    def test_abc_fifty_question_fault_matrix_and_second_round_isolation(self):
        from copy import deepcopy
        import test_baseline_resume as fixture
        from app.corpus import current_manifest, manifest_identity
        from app.paid_run import provider_task
        from app.providers import ProviderInvalidResponse
        from app.telemetry import record_usage
        variants = {'A': {'top_k': 6}, 'B': {'candidate_k': 24}, 'C': {'rerank': 'query_only'}}
        faults = [('none', 0), *[('embedding', n) for n in (1, 25, 49)],
                  ('rerank',49), ('answer',49), ('429',49), ('503',49), ('auth',49),
                  ('judge_structure',49), ('judge_quote',49), ('stop',25), ('usage',49)]
        for label, changes in variants.items():
            for fault, position in faults:
                if label == 'C' and fault == 'rerank': continue
                with self.subTest(candidate=label, fault=fault, position=position):
                    fixture.ResumeTests.setUp(self)
                    try:
                        items = [{'id':f'Q{i}', 'question':f'Q{i}', 'reference_answer':'事实',
                                  'test_category':'positive' if i<=20 else 'ablation' if i<=30 else 'negative',
                                  'negative_subtype':None if i<=30 else 'safety_critical' if i<=40 else 'prompt_injection', 'evidence':[]} for i in range(1,51)]
                        snapshot = {'questions':items,'question_ids':[i['id'] for i in items], 'corpus_fingerprint':manifest_identity(current_manifest())}
                        with self.store.connection() as db: db.execute('UPDATE dataset_versions SET snapshot_json=?', (json.dumps(snapshot),))
                        self.runtime.fail = None
                        baseline = self.runner.execute_baseline(*self.runner.start_baseline())
                        exp = self.store.create_experiment(baseline['id'], 'completed')
                        config = {**baseline['config'], **changes};config.pop('run_target', None)
                        self.store.save_candidate(exp, 'R1-'+label, config, {'round':1,'candidate_label':label})
                        cid = exp+'-R1-'+label
                        original_answer, original_judge = self.runtime.answer, self.runtime.judge
                        current = {}; calls = []; enabled = [True]
                        def network(request, **kwargs):
                            payload = json.loads(request.data)
                            phase = 'embedding' if 'embeddings' in request.full_url else 'rerank' if 'reranks' in request.full_url else 'answer'
                            calls.append((current['q'], phase))
                            active = enabled[0] and current['q'] == f'Q{position}'
                            if active and fault in {phase, '503'}: raise TimeoutError('fixture timeout') if fault == phase else urllib.error.HTTPError(request.full_url,503,'fixture',{},io.BytesIO(b'{}'))
                            if active and phase == 'embedding' and fault in {'429','auth'}:
                                raise urllib.error.HTTPError(request.full_url,429 if fault=='429' else 401,'fixture',{},io.BytesIO(b'{}'))
                            body = {'data':[{'index':0,'embedding':[1,2]}]} if phase=='embedding' else {'results':[{'index':i,'relevance_score':.9} for i in range(len(payload['documents']))]} if phase=='rerank' else {'choices':[{'message':{'content':'事实'},'finish_reason':'stop'}]}
                            if not (active and fault=='usage'): body['usage'] = {'prompt_tokens':2,'completion_tokens':1,'total_tokens':3}
                            return io.BytesIO(json.dumps(body).encode())
                        def answer(q, cfg):
                            current['q'] = q
                            if enabled[0] and fault=='stop' and q==f'Q{position}':
                                rid = self.store.candidate(cid)['result']['evaluation_run_id']
                                self.store.request_evaluation_stop(rid)
                            self.provider().embed([q],2)
                            if cfg.get('rerank') is True:self.provider().rerank(q,[{'content':f'fixture-{i}'} for i in range(cfg['candidate_k'])])
                            with provider_task('answer'):
                                DeepSeekProvider(Settings('fixture','https://fixture.invalid','fixture')).complete('system',q)
                            return original_answer(q,cfg)
                        def judge(q, *args, **kwargs):
                            if enabled[0] and q==f'Q{position}' and fault.startswith('judge_'):
                                record_usage({'provider':'DeepSeek','requested_model':'fixture','status':'ok','prompt_tokens':2,'completion_tokens':1})
                                raise ProviderInvalidResponse('fixture invalid JSON' if fault=='judge_structure' else 'answer quote is missing or not located', raw_provider_response='fixture invalid response')
                            return original_judge(q,*args,**kwargs)
                        with patch.object(self.runtime,'answer',side_effect=answer), patch.object(self.runtime,'judge',side_effect=judge), patch('urllib.request.urlopen',side_effect=network), patch('app.evaluation_stage.time.sleep'):
                            outcome = self.runner.run_candidate(cid,automatic=True)
                            source = self.store.evaluation_run(outcome['result']['evaluation_run_id'])
                            rows = self.store.evaluation_case_results(source['id']); before = deepcopy(source)
                            if fault=='none': self.assertEqual(len(rows),50,source.get('error_message'))
                            else:
                                self.assertGreaterEqual(len(rows),position-1,source.get("error_message"))
                                self.assertNotEqual(source['status'],'completed')
                                self.assertIsNone(outcome['result']['qualification']['qualified'])
                                plan = self.runner.candidate_resume_plan(cid)
                                safe = fault in {'429','auth','judge_structure','judge_quote','stop'}
                                self.assertEqual(plan['can_resume'],safe)
                                if safe:
                                    enabled[0] = False
                                    finished = self.runner.run_candidate(cid,automatic=True)
                                    self.assertEqual(finished['result']['completed'],50)
                                    self.assertEqual(self.store.evaluation_run(source['id']),before)
                                    child = self.store.evaluation_case_results(finished['result']['evaluation_run_id'])
                                    for old in rows:
                                        saved = next(r for r in child if r['question_id']==old['question_id'])
                                        self.assertEqual({k:v for k,v in saved.items() if k!='run_id'},{k:v for k,v in old.items() if k!='run_id'})
                                    if fault.startswith('judge_'):self.assertEqual(calls.count((f'Q{position}','answer')),1)
                            if fault=='none':
                                old_calls = len(calls)
                                self.store.save_candidate(exp,'R2-'+label,{**config,'min_score':.1},{'round':2,'candidate_label':label})
                                second = self.runner.run_candidate(exp+'-R2-'+label,automatic=True)
                                self.assertEqual(second['result']['completed'],50)
                                self.assertNotEqual(second['result']['evaluation_run_id'],source['id'])
                                self.assertEqual(len(calls)-old_calls,150 if label!='C' else 100)
                    finally: fixture.ResumeTests.tearDown(self)

    provider = RequestCheckpointTests.provider
