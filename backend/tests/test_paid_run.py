"""Offline payment-boundary tests; never Provider acceptance."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from app.ai_service import AiService
from app.providers import ProviderNetworkError, ProviderUnavailable
from app.paid_run import PaidRun, paid_request, controlled_run
from app.telemetry import record_usage


class PaidRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'calls.json'
        self.prices = {'deepseek-v4-flash': {'provider':'DeepSeek', 'input':2., 'output':8., 'max_output':384000}}
        self.run = self.make_run(self.path)

    def make_run(self, path, budget=20.):
        return PaidRun(path,budget,self.prices,{'corpus':'new'},identity_check=lambda:{'corpus':'new'})

    def api(self):
        root = Path(self.temp.name)
        with patch.dict(os.environ,{'RAG_DEMO_DB_PATH':str(root/'fixture.db'),'RAG_DEMO_INDEX_DIR':str(root/'index'),
                                   'RAG_DEMO_ENV_PATH':str(root/'absent.env'),'RAG_DEMO_UPLOADS_DIR':str(root/'uploads'),
                                   'RAG_FORCE_MOCK':'1','DEEPSEEK_API_KEY':'','DASHSCOPE_API_KEY':''}):
            from api_fixture import main
        return main

    def test_frozen_limits_apply_without_paid_context(self):
        from app.paid_run import execution_limits, provider_task
        from app.providers import DeepSeekProvider
        from app.config import Settings
        provider=DeepSeekProvider(Settings('fixture','https://fixture.invalid','deepseek-v4-flash'))
        with execution_limits({'judge':32768}),provider_task('judge'):
            self.assertEqual(json.loads(provider._request('s','u',True,False,.2).data)['max_tokens'],32768)

    def test_one_explicit_unknown_retry_retains_original_call_and_reserve(self):
        from app.paid_run import provider_task
        payload={'messages':[],'max_tokens':10}
        with provider_task('judge'):old=self.run.begin('DeepSeek','deepseek-v4-flash',payload)
        self.run.stop('ProviderTimeout');original=json.loads(json.dumps(old))
        auth={'source':'direct_user_instruction','request_sha256':old['request_sha256'],'max_judge_retries':1}
        continued=PaidRun.next_stage(self.path,'resume',lambda:{'corpus':'new'},authorization=auth,budget_yuan=10.)
        self.assertEqual(continued.calls[0],original)
        with provider_task('judge'):new=continued.begin('DeepSeek','deepseek-v4-flash',payload)
        continued.settle(new,{'provider':'DeepSeek','requested_model':'deepseek-v4-flash','status':'ok','prompt_tokens':1,'completion_tokens':1})
        with self.assertRaises(RuntimeError):continued.begin('DeepSeek','deepseek-v4-flash',payload)
        self.assertEqual(continued.calls[0]['status'],'reserved')
        candidate=PaidRun.next_stage(self.path,'candidate-A1',lambda:{'corpus':'new'})
        with provider_task('judge'):candidate.begin('DeepSeek','deepseek-v4-flash',payload)


    def test_accounting_explicit_retry_keeps_unknown_and_allows_exactly_once(self):
        from app.paid_run import accounting_only
        payload = {'messages': [], 'max_tokens': 10}
        with accounting_only():
            old = self.run.begin('DeepSeek', 'deepseek-v4-flash', payload)
            old['status'] = 'unknown'
            original = json.loads(json.dumps(old))
            self.run.accounting_retry_authorization = {
                'source': 'direct_user_instruction', 'unknown_call_index': 0,
                'request_sha256': old['request_sha256'], 'max_request_retries': 1,
            }
            self.run.save()
            restored = PaidRun.load_accounting(self.path, lambda: {'corpus': 'new'})
            new = restored.begin('DeepSeek', 'deepseek-v4-flash', payload)
            self.assertEqual(new['retry_of_call_index'], 0)
            restored.settle(new, {'provider': 'DeepSeek', 'requested_model': 'deepseek-v4-flash',
                                 'status': 'ok', 'prompt_tokens': 1, 'completion_tokens': 1})
            with self.assertRaisesRegex(RuntimeError, 'unknown request'):
                restored.begin('DeepSeek', 'deepseek-v4-flash', payload)
            self.assertEqual(restored.calls[0], original)

    def test_accounting_retry_rejects_wrong_or_missing_authorization(self):
        from app.paid_run import accounting_only
        payload = {'messages': [], 'max_tokens': 10}
        with accounting_only():
            old = self.run.begin('DeepSeek', 'deepseek-v4-flash', payload)
            old['status'] = 'unknown'
            for auth in (None, {'source': 'direct_user_instruction', 'unknown_call_index': 1,
                                'request_sha256': old['request_sha256'], 'max_request_retries': 1},
                         {'source': 'direct_user_instruction', 'unknown_call_index': 0,
                          'request_sha256': 'wrong', 'max_request_retries': 1}):
                self.run.accounting_retry_authorization = auth
                with self.assertRaisesRegex(RuntimeError, 'unknown request'):
                    self.run.begin('DeepSeek', 'deepseek-v4-flash', payload)
            self.assertEqual(len(self.run.calls), 1)

    def test_first_stop_reason_survives_outer_stage_failure(self):
        self.run.stop('ProviderTimeout')
        self.run.stop('RuntimeError')
        self.assertEqual(json.loads(self.path.read_text())['stopped'],'ProviderTimeout')

    def test_checkpoint_authorization_keeps_all_unknown_reserves_and_requires_exact_scope(self):
        old=self.run.begin('DeepSeek','deepseek-v4-flash',{'max_tokens':10})
        self.run.stop('ProviderNetworkError')
        auth={'source':'direct_user_instruction','scope':'finite_checkpoint_resume',
              'max_missing_request_retries':1,'source_evaluation_id':'partial-fixture',
              'evaluation_identity':'frozen-fixture','held_request_sha256':[old['request_sha256']]}
        resumed=PaidRun.next_stage(self.path,'baseline-recovery-1',lambda:{'corpus':'new'},authorization=auth)
        self.assertEqual(resumed.calls,[old])
        self.assertEqual(resumed.spent,0)
        new=resumed.begin('DeepSeek','deepseek-v4-flash',{'max_tokens':11})
        resumed.stop('ProviderNetworkError')
        with self.assertRaises(RuntimeError):
            PaidRun.next_stage(self.path,'baseline-recovery-2',lambda:{'corpus':'new'},authorization=auth)
        auth['held_request_sha256'].append(new['request_sha256'])
        again=PaidRun.next_stage(self.path,'baseline-recovery-2',lambda:{'corpus':'new'},authorization=auth)
        self.assertEqual(again.calls,[old,new])
        self.assertEqual(len(again.continuation_authorizations),2)
        with self.assertRaisesRegex(RuntimeError,'budget'):
            again.budget=0.00001
            again.begin('DeepSeek','deepseek-v4-flash',{'max_tokens':12})

    def test_network_failure_and_missing_usage_stop_next_request(self):
        for missing in (False, True):
            path = Path(self.temp.name)/f'{missing}.json'
            run = self.make_run(path)
            with controlled_run(run):
                with self.assertRaises(Exception):
                    with paid_request('DeepSeek','deepseek-v4-flash',{'messages':[]}):
                        if not missing: raise ProviderNetworkError('offline failure')
                with self.assertRaisesRegex(RuntimeError,'stopped'):
                    with paid_request('DeepSeek','deepseek-v4-flash',{}): pass
            self.assertEqual(len(json.loads(path.read_text())['calls']),1)

    def test_usage_is_settled_and_budget_refuses_before_request(self):
        with controlled_run(self.run):
            with paid_request('DeepSeek','deepseek-v4-flash',{'messages':[]}):
                record_usage({'provider':'DeepSeek','requested_model':'deepseek-v4-flash','status':'ok','prompt_tokens':100,'completion_tokens':100})
        self.assertAlmostEqual(self.run.spent,0.001)
        low = self.make_run(Path(self.temp.name)/'low.json',.01)
        with controlled_run(low), self.assertRaisesRegex(RuntimeError,'budget'):
            with paid_request('DeepSeek','deepseek-v4-flash',{}): pass
        self.assertEqual(low.calls,[])

    def test_reopening_ledger_is_not_automatic_resume(self):
        with controlled_run(self.run):
            pass
        with self.assertRaisesRegex(RuntimeError,'exists'):
            PaidRun(self.path,20.,self.prices,{'corpus':'new'})

    def test_qc_and_answerability_fail_once_without_changing_normal_defaults(self):
        service = AiService(None,None,SimpleNamespace(settings=SimpleNamespace(model='deepseek-v4-flash')),False)
        for name,args in [('quality_check',({},)),('answerability_check',('q',[],{}))]:
            with patch.object(service,'_'+name,side_effect=ProviderNetworkError('offline')) as call:
                with controlled_run(self.run), self.assertRaises(ProviderNetworkError):
                    getattr(service,name)(*args)
                self.assertEqual(call.call_count,1)
            with patch.object(service,'_'+name,side_effect=ProviderNetworkError('offline')) as call:
                with self.assertRaises(ProviderNetworkError): getattr(service,name)(*args)
                self.assertEqual(call.call_count,2)

    def test_parser_failure_is_not_retried(self):
        service = AiService(None,None,SimpleNamespace(settings=SimpleNamespace(model='deepseek-v4-flash')),False)
        with patch.object(service,'_quality_check',side_effect=ProviderUnavailable('DeepSeek QC 未返回有效 JSON')) as call:
            with controlled_run(self.run), self.assertRaises(ProviderUnavailable): service.quality_check({})
            self.assertEqual(call.call_count,1)

    def test_task_limits_are_explicit_and_unknown_task_never_calls_provider(self):
        from app.paid_run import provider_task
        from app.providers import DeepSeekProvider
        from app.config import Settings
        run = PaidRun(Path(self.temp.name)/'limited.json',50.,self.prices,{},identity_check=lambda:{},output_limits={'qc':16384,'answer':8192,'judge':32768})
        provider = DeepSeekProvider(Settings('fixture','https://fixture.invalid','deepseek-v4-flash'))
        with controlled_run(run), provider_task('qc'):
            payload = json.loads(provider._request('s','u',True,False).data)
        self.assertEqual(payload['max_tokens'],16384)
        with controlled_run(run), patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(RuntimeError,'task'): provider.complete('s','u')
        network.assert_not_called()

    def test_request_limits_change_evaluation_identity_only_when_present(self):
        from app.evaluation_contract import evaluation_identity
        snapshot = {'id':'fixture','corpus_fingerprint':{}}
        judge = {'model':'fixture','temperature':0}
        original = evaluation_identity(snapshot,judge)
        limited = {**judge,'execution_snapshot':{'request_limits':{'answer':8192,'judge':32768,'query':4096}}}
        self.assertNotEqual(original,evaluation_identity(snapshot,limited))
        changed = {**limited,'execution_snapshot':{'request_limits':{'answer':16384,'judge':32768,'query':4096}}}
        self.assertNotEqual(evaluation_identity(snapshot,limited),evaluation_identity(snapshot,changed))

    def test_explicit_next_stage_preserves_budget_and_rejects_duplicate_or_unknown_usage(self):
        with controlled_run(self.run):
            with paid_request('DeepSeek','deepseek-v4-flash',{}):
                record_usage({'provider':'DeepSeek','requested_model':'deepseek-v4-flash','status':'ok','prompt_tokens':100,'completion_tokens':100})
        continued=PaidRun.next_stage(self.path,'baseline',lambda:{'corpus':'new'})
        self.assertEqual(continued.spent,self.run.spent)
        self.assertEqual(len(continued.calls),1)
        with self.assertRaisesRegex(RuntimeError,'duplicate'):
            PaidRun.next_stage(self.path,'baseline',lambda:{'corpus':'new'})
        continued.stop('uncertain')
        with self.assertRaisesRegex(RuntimeError,'uncertain'):
            PaidRun.next_stage(self.path,'agent',lambda:{'corpus':'new'})

    def test_truncated_response_keeps_known_usage_and_does_not_retry(self):
        import io
        from app.providers import DeepSeekProvider
        from app.config import Settings
        provider=DeepSeekProvider(Settings('fixture','https://fixture.invalid','deepseek-v4-flash'))
        body={'choices':[{'message':{'content':''},'finish_reason':'length'}],'usage':{'prompt_tokens':100,'completion_tokens':100}}
        with controlled_run(self.run),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())) as network:
            with self.assertRaises(ProviderUnavailable):provider.complete('s','u')
        self.assertEqual(network.call_count,1)
        self.assertEqual(self.run.calls[0]['status'],'ok')
        self.assertGreater(self.run.spent,0)
        self.assertIsNotNone(self.run.stopped)

    def test_invalid_usage_is_saved_and_aborts_following_call(self):
        with controlled_run(self.run):
            with self.assertRaisesRegex(RuntimeError,'Usage'):
                with paid_request('DeepSeek','deepseek-v4-flash',{}):
                    record_usage({'status':'ok','provider':'DeepSeek','requested_model':'deepseek-v4-flash'})
            with self.assertRaisesRegex(RuntimeError,'stopped'):
                with paid_request('DeepSeek','deepseek-v4-flash',{}): pass
        saved = json.loads(self.path.read_text())
        self.assertEqual(len(saved['calls']),1)
        self.assertEqual(saved['calls'][0]['usage']['status'],'ok')
        self.assertLess(saved['available_yuan'],saved['budget_yuan'])

    def test_unknown_model_provider_or_usage_aborts(self):
        with controlled_run(self.run):
            with self.assertRaises(RuntimeError):
                with paid_request('Alibaba','unknown',{}): pass
        self.assertEqual(self.run.calls,[])

    def test_identity_change_and_ledger_write_failure_prevent_request(self):
        self.run.identity_check = lambda:{'corpus':'changed'}
        with controlled_run(self.run), self.assertRaisesRegex(RuntimeError,'identity'):
            with paid_request('DeepSeek','deepseek-v4-flash',{}): pass
        self.assertEqual(self.run.calls,[])
        run = self.make_run(Path(self.temp.name)/'write-failure.json')
        with patch.object(run,'save',side_effect=OSError('offline disk failure')):
            with controlled_run(run), self.assertRaises(OSError):
                with paid_request('DeepSeek','deepseek-v4-flash',{}):
                    self.fail('Request must not start without durable reservation')

    def test_background_worker_stops_after_first_business_provider_error(self):
        main = self.api()
        from app.golden_v2 import digest
        from unittest.mock import Mock
        frozen = {'generation_strategy':'business_v2','corpus_fingerprint':{},'chunk_fingerprint':digest([])}
        store = Mock()
        store.generation_run.return_value = {'profile':{},'question_ids':['q1','q2'], 'artifacts':{'hard_validation':{'frozen_plan':frozen}}}
        store.question.side_effect = lambda key:{'id':key,'raw':{'coverage_slot':key},'probe_status':'probe_pending','qc_status':'qc_pending'}
        corpus = SimpleNamespace(chunks=lambda:[])
        with patch.object(main,'current_manifest',return_value={'documents':[]}), patch.object(main,'manifest_identity',return_value={}), patch.object(main,'_business_quality_step',side_effect=ProviderNetworkError('offline')) as step:
            thread = threading.Thread(target=main._run_mini_generation,args=('fixture',store,None,corpus),kwargs={'resume_quality':True,'paid_run':self.run})
            thread.start(); thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(step.call_count,1)
        self.assertEqual(store.update_generation_run.call_args.kwargs['status'],'failed')
        self.assertIsNotNone(self.run.stopped)

    def test_retrieval_execution_failure_is_not_a_content_failure(self):
        main = self.api()
        with controlled_run(self.run):
            main._require_probe_execution({'status':'failed','classification':'EVIDENCE_INVALID'})
            with self.assertRaisesRegex(Exception,'retrieval execution'):
                main._require_probe_execution({'status':'failed','classification':'RETRIEVAL_EXECUTION_FAILED'})

    def test_deepseek_request_keeps_payload_and_records_one_real_boundary(self):
        import io
        from app.providers import DeepSeekProvider
        from app.config import Settings
        provider = DeepSeekProvider(Settings('fixture-secret','https://fixture.invalid','deepseek-v4-flash'))
        body = {'choices':[{'message':{'content':'fixture'}}], 'usage':{'prompt_tokens':100,'completion_tokens':100}}
        with controlled_run(self.run), patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())) as network:
            result = provider.complete_with_metrics('system','user',json_mode=True,temperature=0)
        self.assertEqual(result['content'],'fixture')
        payload = json.loads(network.call_args.args[0].data)
        self.assertNotIn('max_tokens',payload)
        self.assertNotIn('thinking',payload)
        self.assertEqual(payload['temperature'],0)
        self.assertEqual(len(self.run.calls),1)
        self.assertNotIn('fixture-secret',self.path.read_text())

    def test_alibaba_usage_and_insufficient_budget_are_checked_at_network_boundary(self):
        import io
        from app.knowledge_pipeline import AlibabaProvider
        self.run.prices['qwen3-rerank'] = {'provider':'Alibaba','input':.5,'output':0,'max_output':0}
        provider = AlibabaProvider({'DASHSCOPE_API_KEY':'fixture-secret','DASHSCOPE_BASE_URL':'https://fixture.invalid'})
        with controlled_run(self.run), patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"usage":{"total_tokens":100}}')) as network:
            provider._post('/rerank',{'model':'qwen3-rerank','documents':['fixture']})
        self.assertEqual(network.call_count,1)
        self.assertAlmostEqual(self.run.spent,.00005)
        low = self.make_run(Path(self.temp.name)/'blocked-network.json',.01)
        from app.providers import DeepSeekProvider
        from app.config import Settings
        deepseek = DeepSeekProvider(Settings('fixture','https://fixture.invalid','deepseek-v4-flash'))
        with controlled_run(low), patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(RuntimeError,'budget'): deepseek.complete('s','u')
        network.assert_not_called()

    def test_rerank_budget_accounts_for_query_per_document(self):
        prices = {'qwen3-rerank':{'provider':'Alibaba','input':.5,'output':0,'max_output':0}}
        run = PaidRun(Path(self.temp.name)/'rerank-limit.json',.004,prices,{},identity_check=lambda:{})
        with controlled_run(run), self.assertRaisesRegex(RuntimeError,'budget'):
            with paid_request('Alibaba','qwen3-rerank',{'query':'Q'*1000,'documents':['D']*12}):
                self.fail('Repeated query billing must be reserved before network')

    def test_accounting_stops_after_network_failure_and_never_repeats_unknown_payload(self):
        from app.paid_run import accounting_only
        payload = {'messages': [], 'max_tokens':10}
        with accounting_only(), controlled_run(self.run):
            with self.assertRaisesRegex(OSError, 'offline network'):
                with paid_request('DeepSeek','deepseek-v4-flash',payload):
                    raise OSError('offline network')
            self.assertEqual(self.run.calls[0]['status'], 'unknown')
            with self.assertRaisesRegex(RuntimeError, 'stopped'):
                self.run.begin('DeepSeek','deepseek-v4-flash',{'messages':['another']})
            self.run.stopped = None  # Explicit continuation may allow unrelated requests.
            with self.assertRaisesRegex(RuntimeError, 'unknown request'):
                self.run.begin('DeepSeek','deepseek-v4-flash',payload)

    def test_checkpoint_vectors_require_exact_successful_request_identity(self):
        import hashlib, importlib.util
        path = Path(__file__).resolve().parents[2]/'scripts/run_medium50_full_evolution.py'
        spec = importlib.util.spec_from_file_location('medium50_scope_test',path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        response = Path(self.temp.name)/'offline-vector.json'
        response.write_text(json.dumps({'data':[{'index':0,'embedding':[3.,4.]}]}))
        payload = {'model':'text-embedding-v4','input':['actual question'],'dimensions':2}
        digest = hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()
        calls = [{'status':'ok','model':'text-embedding-v4','request_sha256':digest,'raw_response_path':str(response)},
                 {'status':'unknown','model':'text-embedding-v4','request_sha256':'other','raw_response_path':str(response)}]
        service = SimpleNamespace(corpus=SimpleNamespace(index_info=lambda:{'dimension':2,'knowledge_identity':{'fixture':'sha'}}))
        self.assertEqual(module.restore_saved_vectors(service,{'calls':calls},['actual question','unverified question']),1)
        self.assertEqual(set(service._revision_vectors),{'actual question'})
        self.assertAlmostEqual(float(service._revision_vectors['actual question'][0]),.6)


if __name__ == '__main__': unittest.main()
