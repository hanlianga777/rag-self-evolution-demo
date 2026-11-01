"""HTTP fixtures only: retry each RPC, never a whole retrieval/answer stage."""
import io
import json
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.evaluation_stage import checkpoint_usage, perform_stage
from app.knowledge_pipeline import AlibabaProvider
from app.paid_run import PaidRun, accounting_only, controlled_run
from app.providers import DeepSeekProvider, ProviderAPIError
from app.telemetry import collect_usage


class TransportRetryTests(unittest.TestCase):
    def providers(self):
        deepseek = DeepSeekProvider(Settings('fixture', 'https://fixture.invalid', 'fixture'))
        alibaba = AlibabaProvider({'DASHSCOPE_API_KEY':'fixture', 'DASHSCOPE_BASE_URL':'https://fixture.invalid'})
        return [
            ('deepseek', lambda: deepseek.complete('system', 'question'),
             {'choices':[{'message':{'content':'answer'}, 'finish_reason':'stop'}],
              'usage':{'prompt_tokens':2, 'completion_tokens':1}}, 'answer'),
            ('embedding', lambda: alibaba.embed(['query'], 2).tolist(),
             {'data':[{'index':0, 'embedding':[3.,4.]}], 'usage':{'total_tokens':2}}, [[.6000000238418579,.800000011920929]]),
            ('rerank', lambda: alibaba.rerank('query', [{'content':'evidence'}])[0]['score'],
             {'results':[{'index':0, 'relevance_score':.9}], 'usage':{'total_tokens':2}}, .9),
        ]

    def stage(self, checkpoint, action):
        return perform_stage(checkpoint, 'generation', action, 'fixture-run', automatic=True,
                             check_stop=lambda:None, on_state=lambda *a, **kw:None)

    def test_ssl_then_success_records_each_attempt_in_plain_provider_calls(self):
        for name, action, body, expected in self.providers():
            with self.subTest(provider=name), collect_usage() as usage:
                replies=[urllib.error.URLError(ssl.SSLEOFError('UNEXPECTED_EOF_WHILE_READING')),
                         io.BytesIO(json.dumps(body).encode())]
                with patch('urllib.request.urlopen', side_effect=replies), patch('app.providers.time.sleep') as sleep:
                    self.assertEqual(action(), expected)
                self.assertEqual(len(usage), 2)
                self.assertEqual([u['status'] for u in usage], ['unknown', 'ok'])
                self.assertEqual([c.args[0] for c in sleep.call_args_list], [5])

    def test_three_failures_have_three_usage_rows_and_no_nested_stage_retry(self):
        for name, action, _, _ in self.providers():
            checkpoint={'attempts':[]}
            with self.subTest(provider=name), patch('urllib.request.urlopen', side_effect=TimeoutError('read timed out')) as http, patch('app.providers.time.sleep') as sleep:
                with self.assertRaises(Exception) as caught:
                    self.stage(checkpoint, action)
                self.assertTrue(caught.exception.provider_retry_exhausted)
                self.assertEqual(http.call_count, 3)
                self.assertEqual([c.args[0] for c in sleep.call_args_list], [5,15])
                self.assertEqual(len(checkpoint_usage(checkpoint)), 3)
                self.assertEqual(len(checkpoint['attempts']), 1)

    def test_401_is_permanent_and_sent_once(self):
        for name, action, _, _ in self.providers():
            with self.subTest(provider=name), collect_usage() as usage:
                error=urllib.error.HTTPError('https://fixture.invalid',401,'Unauthorized',{},io.BytesIO(b'{"error":{"message":"bad key"}}'))
                with patch('urllib.request.urlopen', side_effect=error) as http, patch('app.providers.time.sleep') as sleep:
                    with self.assertRaises(ProviderAPIError) as caught:action()
                from app.providers import permanent_provider_error
                self.assertTrue(permanent_provider_error(caught.exception))
                self.assertEqual(http.call_count, 1)
                self.assertEqual(len(usage), 1)
                sleep.assert_not_called()

    def test_429_and_5xx_retry_the_http_request_then_use_success(self):
        for name, action, body, expected in self.providers():
            for status in (429,503):
                with self.subTest(provider=name,status=status), collect_usage() as usage:
                    error=urllib.error.HTTPError('https://fixture.invalid',status,'busy',{},io.BytesIO(b'{"error":{"code":"Throttling"}}'))
                    replies=[error,io.BytesIO(json.dumps(body).encode())]
                    with patch('urllib.request.urlopen',side_effect=replies), patch('app.providers.time.sleep'):
                        self.assertEqual(action(),expected)
                    self.assertEqual(len(usage),2)
                    self.assertEqual(usage[0]['http_status'],status)
                    self.assertEqual(usage[1]['status'],'ok')

    def test_unknown_usage_keeps_valid_result_and_individual_ledger_rows(self):
        for name, action, body, expected in self.providers():
            with self.subTest(provider=name), tempfile.TemporaryDirectory() as directory:
                body={k:v for k,v in body.items() if k!='usage'}
                ledger=PaidRun(Path(directory)/'ledger.json', identity={}, identity_check=lambda:{})
                checkpoint={'attempts':[]}
                replies=[urllib.error.URLError(ssl.SSLEOFError('connection lost')), io.BytesIO(json.dumps(body).encode())]
                with accounting_only(), controlled_run(ledger), patch('urllib.request.urlopen',side_effect=replies), patch('app.providers.time.sleep'):
                    self.assertEqual(self.stage(checkpoint, action), expected)
                self.assertEqual(len(checkpoint_usage(checkpoint)), 2)
                self.assertEqual(len(ledger.calls), 2)
                self.assertTrue(all(c['status']=='unknown' for c in ledger.calls))
                self.assertIsNone(ledger.stopped)
                self.assertTrue(all(c.get('upper_estimate_yuan') is None for c in ledger.calls))

    def test_recovered_rpc_does_not_repeat_an_earlier_embedding(self):
        checkpoint={'attempts':[]}; urls=[]
        provider=AlibabaProvider({'DASHSCOPE_API_KEY':'fixture','DASHSCOPE_BASE_URL':'https://fixture.invalid'})
        def http(request, **kwargs):
            urls.append(request.full_url)
            if request.full_url.endswith('/embeddings'):
                return io.BytesIO(b'{"data":[{"index":0,"embedding":[3,4]}],"usage":{"total_tokens":2}}')
            if urls.count(request.full_url)==1:raise TimeoutError('read timeout')
            return io.BytesIO(b'{"results":[{"index":0,"relevance_score":0.9}],"usage":{"total_tokens":2}}')
        def action():
            provider.embed(['query'],2)
            return provider.rerank('query',[{'content':'evidence'}])
        with patch('urllib.request.urlopen',side_effect=http), patch('app.providers.time.sleep'):
            self.assertEqual(self.stage(checkpoint, action)[0]['score'],.9)
        self.assertEqual(sum(url.endswith('/embeddings') for url in urls),1)
        self.assertEqual(sum(url.endswith('/reranks') for url in urls),2)
        self.assertEqual(len(checkpoint_usage(checkpoint)),3)

    def test_all_5xx_are_transient_but_invalid_json_is_not_transport(self):
        from app.providers import transient_provider_error, permanent_provider_error, ProviderInvalidResponse
        for status in (429,500,501,502,503,504,507,599):
            error=ProviderAPIError('fixture',status_code=status)
            self.assertTrue(transient_provider_error(error))
            self.assertFalse(permanent_provider_error(error))
        self.assertFalse(transient_provider_error(ProviderInvalidResponse('invalid JSON')))
        for status in (400,401,403,404,413,422):
            error=ProviderAPIError('fixture',status_code=status)
            self.assertFalse(transient_provider_error(error))
            self.assertTrue(permanent_provider_error(error))

    def test_network_attempt_does_not_consume_judge_format_rejudgment(self):
        from app.ai_service import AiService
        from app.evaluation_stage import judge_request_count
        provider=DeepSeekProvider(Settings('fixture','https://fixture.invalid','fixture'))
        service=AiService(None,None,provider,False)
        good={'correctness':4,'completeness':1,'faithfulness':1,'behavior_pass':True,
              'reason':'fixture','missing_points':[],'unsupported_claims':[]}
        def response(content):
            return io.BytesIO(json.dumps({'choices':[{'message':{'content':content},'finish_reason':'stop'}],
                                         'usage':{'prompt_tokens':10,'completion_tokens':2}}).encode())
        replies=[TimeoutError('read timeout'),response('{}'),response(json.dumps(good))]
        checkpoint={'attempts':[]}
        with patch('urllib.request.urlopen',side_effect=replies) as http, patch('app.providers.time.sleep'):
            result=perform_stage(checkpoint,'judge',lambda:service.judge('q','e','a','positive'),
                                 'fixture-run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**kw:None)
        self.assertEqual(result['correctness'],4)
        self.assertEqual(result['response_retries'],1)
        self.assertEqual(http.call_count,3)
        self.assertEqual(len(checkpoint_usage(checkpoint)),3)
        self.assertEqual(judge_request_count(checkpoint,'fixture-run'),2)

    def test_local_response_save_error_never_repeats_successful_alibaba_request(self):
        provider=AlibabaProvider({'DASHSCOPE_API_KEY':'fixture','DASHSCOPE_BASE_URL':'https://fixture.invalid'})
        with tempfile.TemporaryDirectory() as directory:
            ledger=PaidRun(Path(directory)/'ledger.json',identity={},identity_check=lambda:{})
            failure=OSError(28,'No space left on device')
            with accounting_only(),controlled_run(ledger),collect_usage() as usage:
                with patch('urllib.request.urlopen',side_effect=lambda *a,**kw:io.BytesIO(b'{"results":[{"index":0,"relevance_score":0.9}],"usage":{"total_tokens":2}}')) as http, patch.object(ledger,'response',side_effect=failure), patch('app.providers.time.sleep') as sleep:
                    with self.assertRaises(OSError) as caught:
                        provider.rerank('query',[{'content':'evidence'}])
            self.assertIs(caught.exception,failure)
            self.assertEqual(http.call_count,1)
            sleep.assert_not_called()
            self.assertEqual(len(usage),1)
            self.assertEqual(usage[0]['status'],'ok')
            self.assertEqual(usage[0]['total_tokens'],2)
            saved=json.loads(ledger.path.read_text())
            self.assertEqual(len(saved['calls']),1)
            self.assertEqual(saved['calls'][0]['status'],'ok')
            self.assertEqual(saved['calls'][0]['usage']['total_tokens'],2)


if __name__=='__main__':unittest.main()
