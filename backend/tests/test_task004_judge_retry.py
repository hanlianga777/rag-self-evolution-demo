"""Offline Judge format recovery; all responses and usage are local fixtures."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from app.ai_service import AiService
from app.providers import ProviderInvalidResponse, ProviderNetworkError
from app.telemetry import record_usage
from app.evaluation_stage import perform_stage


class JudgeRetryTests(unittest.TestCase):
    def service(self, replies):
        def judge(*args, **kwargs):
            value = next(replies)
            record_usage({'provider':'DeepSeek','requested_model':'fixture','status':'ok','prompt_tokens':10,'completion_tokens':2})
            if isinstance(value, Exception): raise value
            return value
        return AiService(None, None, SimpleNamespace(judge=judge, settings=SimpleNamespace(model='fixture')), False)

    def test_recovers_once_and_accounts_both_replies(self):
        service = self.service(iter([ProviderInvalidResponse('missing field',raw_provider_response='{}'), {'correctness':5}]))
        result = service.judge('q','e','a','positive')
        self.assertEqual(result['correctness'],5)
        self.assertEqual(result['response_retries'],1)
        self.assertEqual(len(result['token_usage']),2)
        self.assertEqual(result['response_recovery'][0]['error'],'missing field')

    def test_two_bad_replies_save_both_reasons_without_outer_third_attempt(self):
        service = self.service(iter([ProviderInvalidResponse('first'),ProviderInvalidResponse('second')]))
        cp={'attempts':[]}
        with self.assertRaises(ProviderInvalidResponse) as caught:
            perform_stage(cp,'judge',lambda:service.judge('q','e','a','positive'),'run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**k:None)
        reasons=caught.exception.response_metadata['response_recovery']
        self.assertEqual([row['error'] for row in reasons],['first','second'])
        self.assertEqual(len(cp['attempts']),1)
        self.assertEqual(len(cp['attempts'][0]['usage']),2)

    def test_unknown_billing_does_not_cancel_format_retry(self):
        error=ProviderInvalidResponse('transport response incomplete');error.request_execution_unknown=True
        provider=SimpleNamespace(judge=Mock(side_effect=error),settings=SimpleNamespace(model='fixture'))
        with self.assertRaises(ProviderInvalidResponse):AiService(None,None,provider,False).judge('q','e','a','positive')
        self.assertEqual(provider.judge.call_count,2)

    def test_network_error_is_not_format_recovery(self):
        provider=SimpleNamespace(judge=Mock(side_effect=ProviderNetworkError('offline')),settings=SimpleNamespace(model='fixture'))
        with self.assertRaises(ProviderNetworkError):AiService(None,None,provider,False).judge('q','e','a','positive')
        self.assertEqual(provider.judge.call_count,1)


    def test_actual_parser_records_two_paid_calls_and_saved_ledger(self):
        import io, json, tempfile
        from pathlib import Path
        from app.providers import DeepSeekProvider
        from app.config import Settings
        from app.paid_run import PaidRun, controlled_run
        good={'correctness':4,'completeness':1,'faithfulness':1,'behavior_pass':True,'reason':'fixture','missing_points':[],'unsupported_claims':[]}
        replies=[{'choices':[{'message':{'content':content},'finish_reason':'stop'}],
                  'usage':{'prompt_tokens':10,'completion_tokens':2}} for content in ['{}',json.dumps(good)]]
        with tempfile.TemporaryDirectory() as directory:
            ledger=PaidRun(Path(directory)/'ledger.json',prices={'fixture':{'provider':'DeepSeek','input':1.,'output':2.,'max_output':65536}},identity={},identity_check=lambda:{})
            service=AiService(None,None,DeepSeekProvider(Settings('fixture','https://fixture.invalid','fixture')),False)
            with controlled_run(ledger),patch('urllib.request.urlopen',side_effect=[io.BytesIO(json.dumps(r).encode()) for r in replies]) as request:
                result=service.judge('q','e','a','positive')
            saved=json.loads(ledger.path.read_text())
            self.assertEqual(result['response_retries'],1)
            self.assertEqual(request.call_count,2)
            self.assertEqual([call['status'] for call in saved['calls']],['ok','ok'])
            self.assertAlmostEqual(saved['spent_yuan'],.000028)
            self.assertEqual(len(result['token_usage']),2)

    def test_outer_quality_error_and_inner_format_error_share_two_requests(self):
        from app.evaluation import EvaluationRunner
        good={'verdict':'PASS','checks':[],'issues':[],'reason':'fixture',
              'quality':{'correctness':4,'faithfulness':1,'completeness':1}}
        provider=Mock(settings=SimpleNamespace(model='fixture'))
        responses=iter([{**good,'quality':{}},ProviderInvalidResponse('第二次格式错'),good])
        def judge(*args,**kwargs):
            record_usage({'provider':'DeepSeek','requested_model':'fixture','status':'ok','prompt_tokens':10,'completion_tokens':2})
            response=next(responses)
            if isinstance(response,Exception):raise response
            return response
        provider.judge.side_effect=judge
        runner=EvaluationRunner(None,AiService(None,None,provider,False))
        item={'id':'q','question':'q','reference_answer':'e','test_category':'positive','raw':{},'evidence':[]}
        execution={'answer':'a','retrieval_trace':{'final':[]},'retrieval':[],'timings':{}}
        checkpoint={'attempts':[]}
        context={'programmatic_evidence_observation':{},'_canonical_chunks':[]}
        with patch.object(runner,'judge_context',return_value=context),patch('app.evaluation.validate_business_judgment'),patch('app.evaluation_stage.time.sleep'):
            with self.assertRaises(ProviderInvalidResponse):
                perform_stage(checkpoint,'judge',lambda:runner.score_execution(item,execution),'run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**k:None)
        self.assertEqual(provider.judge.call_count,2)
        self.assertEqual(len(checkpoint['attempts']),2)
        self.assertEqual(sum(len(attempt['usage']) for attempt in checkpoint['attempts']),2)
        self.assertIn('quality metrics',checkpoint['attempts'][0]['error'])
        self.assertIn('第二次格式错',checkpoint['attempts'][1]['error'])

    def test_outer_retry_does_not_consume_next_question_allowance(self):
        provider=Mock(settings=SimpleNamespace(model='fixture'))
        def judge(*args,**kwargs):
            record_usage({'provider':'DeepSeek','requested_model':'fixture','status':'ok','prompt_tokens':10,'completion_tokens':2})
            return {'correctness':4}
        provider.judge.side_effect=judge
        service=AiService(None,None,provider,False)
        for question in ('one','two'):
            checkpoint={'attempts':[]}
            validations=[]
            def score():
                result=service.judge(question,'e','a','positive')
                validations.append(result)
                if len(validations)==1:raise ProviderInvalidResponse('outer quality invalid')
                return result
            with patch('app.evaluation_stage.time.sleep'):
                result=perform_stage(checkpoint,'judge',score,'run',automatic=False,check_stop=lambda:None,on_state=lambda *a,**k:None)
            self.assertEqual(result['response_retries'],1)
            self.assertEqual(len(checkpoint['attempts']),2)
            self.assertEqual(sum(len(attempt['usage']) for attempt in checkpoint['attempts']),2)
        self.assertEqual(provider.judge.call_count,4)

    def test_nonformat_stage_failure_is_not_resent(self):
        from app.providers import ProviderAPIError
        action=Mock(side_effect=ProviderAPIError('rate limited',status_code=429))
        cp={'attempts':[]}
        with self.assertRaises(ProviderAPIError):
            perform_stage(cp,'generation',action,'run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**k:None)
        self.assertEqual(action.call_count,1)
        self.assertFalse(cp['attempts'][0]['retryable'])


class RemovedAuthorizationTests(unittest.TestCase):
    def test_delegated_quality_review_does_not_require_owner_file(self):
        from test_delegated_review import DelegatedReviewTests
        fixture=DelegatedReviewTests();fixture.setUp()
        try:
            fixture.path.unlink()
            self.assertEqual(len(fixture.check()['reviews']),50)
        finally:fixture.doCleanups()

    def test_owner_request_accepts_no_named_authorization(self):
        with patch('app.corpus_management.require_consistent_switch'):
            from api_fixture import main
        request=main.OwnerDelegatedReviewRequest(generation_run_id='fixture',reviews=[{}]*50)
        self.assertEqual(request.generation_run_id,'fixture')

    def test_reopen_no_longer_requires_revision_authorization(self):
        import inspect
        from app.governance import GovernanceStore
        self.assertIsNot(inspect.signature(GovernanceStore.reopen_snapshot_question).parameters['authorization'].default,inspect.Parameter.empty)
