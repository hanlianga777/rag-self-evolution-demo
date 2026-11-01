"""Network-mocked Round 0 request tests; no real provider acceptance."""
from contextlib import nullcontext
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_isolation = tempfile.TemporaryDirectory(prefix='round0-thinking-')
_env = {name: str(Path(_isolation.name) / suffix) for name, suffix in {
    'RAG_DEMO_DB_PATH':'fixture.sqlite','RAG_DEMO_ENV_PATH':'empty.env',
    'RAG_DEMO_INDEX_DIR':'index','RAG_DEMO_DOCUMENTS_DIR':'documents',
    'RAG_DEMO_UPLOADS_DIR':'uploads'}.items()}
with patch.dict(os.environ, _env):
    from app import providers
    from app.config import Settings, load_settings
    from app.ai_service import AiService, generation_contract
    from app.paid_run import provider_task



class Response(io.BytesIO):
    status = 200
    headers = {}


class ThinkingTests(unittest.TestCase):
    def setUp(self):
        self.network = patch('socket.create_connection', side_effect=AssertionError('offline only'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.provider = providers.DeepSeekProvider(Settings('fixture', 'https://invalid', 'deepseek-flash'))

    def payload(self):
        return json.loads(self.provider._request('system', 'user', True, False).data)

    def test_model_alias_only_normalizes_new_settings(self):
        empty = Path(_isolation.name) / 'empty.env'
        self.assertEqual(load_settings({}, empty).model, 'deepseek-flash')
        self.assertEqual(load_settings({'DEEPSEEK_MODEL':'deepseek-v4-flash'}, empty).model, 'deepseek-flash')

    def test_tasks_independent_and_off_has_no_effort(self):
        for task, effort in {'baseline':'max','judge':'max','agent':'high','query_rewrite':'low','multi_query':'low','hyde':'high','query_decompose':'high'}.items():
            with providers.thinking_task(task):
                payload = self.payload()
                self.assertEqual(payload['thinking'], {'type':'enabled'})
                self.assertEqual(payload['reasoning_effort'], effort)
                self.assertNotIn('temperature', payload)
        with providers.thinking_task('candidate', 'off'):
            self.assertEqual(self.payload()['thinking'], {'type':'disabled'})
            self.assertNotIn('reasoning_effort', self.payload())
            with provider_task('judge'):
                self.assertEqual(self.payload()['reasoning_effort'], 'max')
            with provider_task('agent'):
                self.assertEqual(self.payload()['reasoning_effort'], 'high')
        with providers.thinking_task('candidate', 'typo'):
            with self.assertRaises(providers.ProviderRequestError): self.payload()

    def test_json_and_stream_use_content_only_keep_usage_model_and_redact_raw(self):
        usage = {'prompt_tokens':10,'completion_tokens':30,'completion_tokens_details':{'reasoning_tokens':20}}
        bodies = [json.dumps({'id':'r1','model':'actual-version','choices':[{'message':{'content':'{"ok":true}','reasoning_content':'PRIVATE THINKING'},'finish_reason':'stop'}],'usage':usage}).encode(),
                  b'data: {"id":"r1","model":"actual-version","choices":[{"delta":{"reasoning_content":"PRIVATE THINKING"}}]}\n\n' + b'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}"},"finish_reason":"stop"}]}\n\n' + ('data: '+json.dumps({'choices':[],'usage':usage})+'\n\ndata: [DONE]\n\n').encode()]
        for stream, body in enumerate(bodies):
            run = SimpleNamespace(output_limits=None, response=lambda saved: self.assertNotIn('PRIVATE THINKING', json.dumps(saved)))
            with patch('urllib.request.urlopen', return_value=Response(body)), patch('app.paid_run.current_paid_run', return_value=run), patch('app.paid_run.paid_request', return_value=nullcontext()), patch('app.telemetry.record_usage'), patch('app.paid_run.payment_usage'):
                result = self.provider.complete_with_metrics('system', 'user', json_mode=True, stream=bool(stream))
            self.assertEqual(result['content'], '{"ok":true}')
            self.assertEqual(result['usage']['response_model'], 'actual-version')
            self.assertEqual(result['usage']['request_parameters']['thinking'], {'type':'enabled'})
            self.assertEqual(result['usage']['request_parameters']['response_format'], {'type':'json_object'})
            self.assertNotIn('messages', result['usage']['request_parameters'])
            self.assertEqual(result['reasoning_tokens'], 20)
            self.assertEqual(result['output_tokens'], 30)

    def test_length_and_timeout_remain_explicit(self):
        body = json.dumps({'choices':[{'message':{'content':'partial','reasoning_content':'PRIVATE THINKING'},'finish_reason':'length'}],'usage':{'completion_tokens':30}}).encode()
        with patch('urllib.request.urlopen', return_value=Response(body)), patch('app.paid_run.payment_usage'):
            with self.assertRaises(providers.ProviderInvalidResponse) as error:self.provider.complete('system','user')
        self.assertEqual(error.exception.response_metadata['finish_reason'], 'length')
        self.assertNotIn('PRIVATE THINKING', error.exception.raw_provider_response)
        with patch('urllib.request.urlopen', side_effect=socket.timeout()), patch('app.paid_run.payment_usage'):
            with self.assertRaises(providers.ProviderTimeout):self.provider.complete('system','user')

    def test_v2_default_candidate_off_auxiliary_tasks_and_no_golden_leakage(self):
        calls = []
        class Provider:
            settings = SimpleNamespace(configured=True, model='fixture')
            def complete(inner, system, user, **kwargs):
                calls.append((system,user,providers.thinking_config()))
                return 'retrieval query'
            def complete_with_metrics(inner, system, user, **kwargs):
                calls.append((system,user,providers.thinking_config()))
                return {'content':'answer','ttft_ms':0,'input_tokens':10,'output_tokens':5}
        service = AiService(object(),object(),Provider(),False)
        service.retriever = SimpleNamespace(retrieve=lambda *a,**kw:[{'chunk_id':'C1','content':'source'}])
        result = service.answer('question', {'run_target':'sandbox_candidate','generation_thinking':'off','query_rewrite':True,'multi_query':1,'hyde':True,'reference_answer':'GOLDEN SECRET','required_checks':['GOLDEN SECRET']})
        self.assertEqual(result['generation_prompt_version'], 'generation-vnext-2')
        self.assertEqual([c[2]['reasoning_effort'] for c in calls[:-1]], ['low','low','high'])
        self.assertEqual(calls[-1][2]['thinking'], {'type':'disabled'})
        self.assertNotIn('GOLDEN SECRET', repr(calls))
        self.assertIn('安全条件', calls[-1][0])
        self.assertNotEqual(generation_contract(), generation_contract('generation-vnext-1'))

    def test_checkpoint_identity_includes_effort_and_reuses_only_matching_request(self):
        from app.evaluation_stage import _request_checkpoint
        checkpoint = {}
        token = _request_checkpoint.set((checkpoint, 'generation', 'offline', lambda *a, **k: None, lambda: None))
        self.addCleanup(_request_checkpoint.reset, token)
        body = json.dumps({'choices':[{'message':{'content':'answer'}, 'finish_reason':'stop'}], 'usage':{'prompt_tokens':1,'completion_tokens':2}}).encode()
        with patch('urllib.request.urlopen', side_effect=lambda *a, **k: Response(body)) as http, patch('app.paid_run.payment_usage'):
            for effort in ('max', 'max', 'off', 'off'):
                with provider_task('answer'), providers.thinking_task('candidate', effort):
                    self.assertEqual(self.provider.complete('system','user'), 'answer')
        self.assertEqual(http.call_count, 2)
        self.assertEqual(len(checkpoint['provider_requests']), 2)

    def test_invalid_and_http_error_responses_do_not_save_reasoning_or_fallback(self):
        import urllib.error
        for raw in ('{"choices":[{"message":{"reasoning_content":"PRIVATE THINKING"',
                    '{"error":{"code":"unsupported_thinking","message":"unsupported max"},"reasoning_content":"PRIVATE THINKING"}'):
            error = urllib.error.HTTPError('https://invalid', 400, 'rejected', {}, io.BytesIO(raw.encode()))
            with patch('urllib.request.urlopen', side_effect=error) as http, patch('app.paid_run.payment_usage'):
                with self.assertRaises(providers.ProviderAPIError) as failure:
                    with providers.thinking_task('candidate','max'): self.provider.complete('system','user')
            self.assertEqual(http.call_count, 1)
            self.assertNotIn('PRIVATE THINKING', failure.exception.raw_provider_response)
            self.assertNotIn('PRIVATE THINKING', str(failure.exception))

    def test_baseline_max_and_judge_max_cannot_inherit_candidate_off(self):
        calls = []
        class Provider:
            settings = SimpleNamespace(configured=True, model='fixture')
            def complete_with_metrics(inner, *a, **k):
                calls.append(providers.thinking_config())
                return {'content':'answer','ttft_ms':0,'input_tokens':1,'output_tokens':2}
            def judge(inner, *a, **k):
                calls.append(providers.thinking_config())
                return {}
        service = AiService(object(),object(),Provider(),False)
        service.retriever = SimpleNamespace(retrieve=lambda *a,**kw:[{'chunk_id':'C1','content':'source'}])
        with providers.thinking_task('candidate','off'):
            service.answer('question', {'run_target':'baseline','generation_thinking':'off'})
            service.judge('question','golden','answer','positive')
        self.assertEqual([c['reasoning_effort'] for c in calls], ['max','max'])

    def test_decompose_strict_bounded_json_and_high_effort(self):
        class Provider:
            settings = SimpleNamespace(configured=True, model='fixture')
            def complete(inner, *a, **k):
                self.assertEqual(providers.thinking_config()['reasoning_effort'], 'high')
                return inner.response
        provider = Provider()
        service = AiService(object(),object(),provider,False)
        provider.response = '{"subquestions":["how to operate?", "how to store?"]}'
        self.assertEqual(len(service.decompose_query('operate and store?')), 2)
        for response in ('{}','{"subquestions":["a","b","c","d"]}','{"subquestions":"bad"}', 'not JSON'):
            provider.response = response
            with self.assertRaises(providers.ProviderInvalidResponse): service.decompose_query('question')

    def test_agent_rejects_legacy_generation_contract_before_claim_or_provider(self):
        from app.optimization import OptimizationAgent
        from unittest.mock import Mock
        store = Mock()
        for version in ('generation-vnext-1','generation-vnext-2'):
            store.evaluation_run.return_value = {'judge':generation_contract(version)}
            with self.assertRaisesRegex(ValueError, 'Generation'):
                OptimizationAgent(store,self.provider).generate('old-baseline')
        store.claim_agent_generation.assert_not_called()

    def test_agent_new_parameters_keep_evidence_and_direction_contract(self):
        from app.optimization import validate_intervention
        from app.policy import DEFAULT_PIPELINE_CONFIG
        case = {'programmatic_metrics':{'retrieval_trace':{'candidates':[],'final':[]}}}
        for direction, observation, diff in [('grounded_generation','final_sufficient',{'generation_thinking':'off'}),
                                             ('query_expansion','recall_missing',{'query_decompose':True}),
                                             ('context_selection','retrieval_noise',{'retrieval_max_tokens':16384})]:
            view = {'target_eligible':True,'primary_root_cause':'Generation','trace_observations':[observation], 'context_selection_options':[]}
            proposal = {'target_bad_cases':['Q1'],'root_cause':'Generation','intervention_direction':direction,
                        'config_diff':diff,'evidence_assertions':[{'target_id':'Q1','observation':observation}],
                        'hypothesis':'test one intervention','why':'saved trace','expected_improvement':'regression check','risk':'latency and evidence completeness'}
            with patch('app.optimization.diagnostic_view', return_value=view):
                validate_intervention(proposal, {'Q1':case}, DEFAULT_PIPELINE_CONFIG)
                proposal['evidence_assertions']=[]
                with self.assertRaises(ValueError): validate_intervention(proposal, {'Q1':case}, DEFAULT_PIPELINE_CONFIG)

    def test_agent_new_stage_parameters_require_measured_bottleneck(self):
        from app.optimization import validate_intervention
        from app.policy import DEFAULT_PIPELINE_CONFIG
        for stage, diff in [('query_decompose', {'query_decompose':True}), ('context_budget', {'retrieval_max_tokens':16384})]:
            case = {'programmatic_metrics':{'retrieval_trace':{'candidates':[],'final':[]}, 'stages':[{'stage_name':stage,'duration_ms':100}]}}
            view = {'target_eligible':True,'primary_root_cause':'Performance','trace_observations':['measured_latency'], 'latency':{'bottleneck':{'stage_name':stage}}}
            proposal = {'target_bad_cases':['Q1'],'root_cause':'Performance','intervention_direction':'stage_performance',
                        'performance_stage':stage, 'config_diff':diff,'evidence_assertions':[{'target_id':'Q1','observation':'measured_latency'}],
                        'hypothesis':'test one intervention','why':'measured stage','expected_improvement':'regression check','risk':'evidence completeness'}
            with patch('app.optimization.diagnostic_view', return_value=view):
                validate_intervention(proposal, {'Q1':case}, DEFAULT_PIPELINE_CONFIG)
                proposal['performance_stage']='unknown'
                with self.assertRaises(ValueError): validate_intervention(proposal, {'Q1':case}, DEFAULT_PIPELINE_CONFIG)

    def test_incomplete_sse_drops_unframed_transport_fragment(self):
        import http.client
        class BrokenResponse(Response):
            def __iter__(inner):
                yield b'data: {"choices":[{"delta":{"reasoning_content":"PRIVATE START"}}],"usage":{"prompt_tokens":7}}\n\n'
                raise http.client.IncompleteRead(b'PRIVATE REASONING CONTINUATION')
        with patch('urllib.request.urlopen',side_effect=lambda *a,**kw:BrokenResponse()) as request, patch('app.paid_run.payment_usage'), patch('app.providers.time.sleep'):
            with self.assertRaises(providers.ProviderNetworkError) as failure:
                self.provider.complete_with_metrics('system','user',stream=True)
        self.assertEqual(request.call_count,3)
        self.assertNotIn('PRIVATE', failure.exception.raw_provider_response)
        self.assertIn('prompt_tokens', failure.exception.raw_provider_response)
        self.assertEqual(failure.exception.response_metadata['partial_usage'], {'prompt_tokens':7})
