"""Isolated HTTP error audit. Stub HTTP only; no external Provider."""
import io,json,urllib.error,unittest
from unittest.mock import patch
from pathlib import Path
import test_optimization_contract as fixture
from app.providers import DeepSeekProvider,ProviderAPIError
from app.config import Settings
from app.optimization import OptimizationAgent

class AgentHttpErrorTests(unittest.TestCase):
    setUp=fixture.OptimizationContractTests.setUp
    def test_agent_records_sanitized_body_and_detailed_error(self):
        secret='fixture-secret-do-not-log'
        provider=DeepSeekProvider(Settings(secret,'https://invalid','deepseek-v4-flash'))
        body=json.dumps({'error':{'code':'context_length_exceeded','message':f'too long; api_key={secret}; Authorization: Bearer unknown-secret'}})
        error=urllib.error.HTTPError('https://invalid',400,'bad request',{},io.BytesIO(body.encode()))
        with patch('app.providers.urllib.request.urlopen',side_effect=error) as http:
            with self.assertRaisesRegex(ValueError,'context_length_exceeded') as caught:
                OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual(http.call_count,1)
        self.assertIn('失败阶段：provider',str(caught.exception));self.assertIn('可重试：否',str(caught.exception))
        with self.store.connection() as c:audit=json.loads(c.execute('select result_json from agent_traces order by id desc limit 1').fetchone()[0])
        detail=audit['provider_error'];self.assertEqual(detail['http_status'],400);self.assertFalse(detail['retryable'])
        self.assertEqual(detail['provider_code'],'context_length_exceeded');self.assertEqual(detail['stage'],'provider')
        self.assertNotIn(secret,json.dumps(audit));self.assertNotIn('unknown-secret',json.dumps(audit))
        self.assertIn('too long',detail['detail']);self.assertIn('error',detail['raw_response'])
        summary=audit['request_summary'];self.assertEqual(summary['model'],'deepseek-v4-flash');self.assertEqual(summary['roles'],['system','user']);self.assertEqual(summary['response_format'],{'type':'json_object'})
        self.assertNotIn('messages',summary);self.assertNotIn('Authorization',json.dumps(summary))

    def test_invalid_request_stops_before_http_with_local_stage(self):
        provider=DeepSeekProvider(Settings('fixture','https://invalid','fixture'))
        with patch('app.providers.urllib.request.urlopen') as http:
            with self.assertRaisesRegex(ValueError,'temperature'):
                class BadTemperature(DeepSeekProvider):
                    def request_summary(self,*args,**kwargs):return super().request_summary(*args,**kwargs,temperature=float('nan'))
                OptimizationAgent(self.store,BadTemperature(provider.settings)).generate('EVAL-test')
        http.assert_not_called()
        with self.store.connection() as c:audit=json.loads(c.execute('select result_json from agent_traces order by id desc limit 1').fetchone()[0])
        self.assertEqual(audit['validation_stage'],'request_validation');self.assertFalse(audit['provider_error']['retryable'])

    def test_shared_request_preflight_preserves_valid_payload(self):
        from app.paid_run import execution_limits,provider_task
        provider=DeepSeekProvider(Settings('fixture','https://invalid','fixture'))
        summary=provider.request_summary('return JSON','{}',json_mode=True)
        self.assertIsNone(summary['max_tokens']);self.assertEqual(summary['temperature'],.2)
        with execution_limits({'agent':16384}),provider_task('agent'):
            self.assertEqual(provider.request_summary('return JSON','{}',json_mode=True)['max_tokens'],16384)
        with patch('app.providers.urllib.request.urlopen') as http:
            for system,user,kwargs in [(None,'q',{}),('s',[],{}),('s','q',{'temperature':-1}),('s','q',{'json_mode':'true'})]:
                with self.assertRaisesRegex(Exception,'请求本地校验'):provider.complete(system,user,**kwargs)
            for limit in (0,False,393217):
                with execution_limits({'agent':limit}),provider_task('agent'):
                    with self.assertRaisesRegex(Exception,'max_tokens'):provider.complete('return JSON','{}',json_mode=True)
        http.assert_not_called()

    def test_api_exposes_detail_stage_and_retryability(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        from unittest.mock import Mock
        provider=DeepSeekProvider(Settings('fixture-secret','https://invalid','fixture'))
        body=b'{"error":{"code":"invalid_request","message":"parameter rejected"}}'
        error=urllib.error.HTTPError('https://invalid',400,'bad',{},io.BytesIO(body))
        with patch.object(main,'store',self.store),patch.object(main,'ai_service',Mock(provider=provider)),patch('app.providers.urllib.request.urlopen',side_effect=error):
            response=TestClient(main.app).post('/api/experiments/run',headers={'Origin':'http://127.0.0.1:5174'})
        self.assertEqual(response.status_code,409)
        for text in ('HTTP 400','invalid_request','parameter rejected','失败阶段：provider','可重试：否'):
            self.assertIn(text,response.json()['detail'])

    def test_non_json_error_is_redacted_and_server_error_retryable(self):
        from app.providers import redact_provider_error,provider_error_details
        body=redact_provider_error('<h1>busy</h1> Authorization: Bearer unknown-secret api_key=fixture-secret','fixture-secret')
        error=ProviderAPIError('HTTP 503',status_code=503,raw_provider_response=body)
        detail=provider_error_details(error,'provider')
        self.assertTrue(detail['retryable']);self.assertIsNone(detail['provider_code'])
        self.assertNotIn('unknown-secret',detail['raw_response']);self.assertNotIn('fixture-secret',str(error))
