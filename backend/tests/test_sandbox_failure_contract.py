"""Offline boundary checks for remote retrieval failures and payment-safe resumption."""
import io,json,unittest,urllib.error
from unittest.mock import patch
from app.knowledge_pipeline import AlibabaProvider
from app.providers import ProviderAPIError,ProviderTimeout
from app.retrieval import RetrievalUnavailable
from app.telemetry import collect_usage
from app.evaluation_stage import perform_stage

class SandboxFailureTests(unittest.TestCase):
    def provider(self):return AlibabaProvider({'DASHSCOPE_API_KEY':'fixture-secret','DASHSCOPE_BASE_URL':'https://fixture.invalid'})
    def test_http_status_body_and_request_id_survive_safe_redaction(self):
        error=urllib.error.HTTPError('https://fixture.invalid',429,'limited',{'x-request-id':'request-fixture'},io.BytesIO(b'{"code":"Throttling","message":"Bearer fixture-secret"}'))
        with patch('urllib.request.urlopen',side_effect=error),collect_usage() as usage,self.assertRaises(ProviderAPIError) as caught:
            self.provider()._post('/embeddings',{'model':'text-embedding-v4'})
        self.assertEqual(caught.exception.status_code,429)
        self.assertNotIn('fixture-secret',str(caught.exception))
        self.assertFalse(usage[0]['request_execution_unknown'])
        wrapped=RetrievalUnavailable('vector_search',caught.exception)
        self.assertEqual(wrapped.status_code,429)
        self.assertNotIn('本地模型',str(wrapped))
    def test_timeout_is_unknown_and_not_retried(self):
        checkpoint={'attempts':[]}
        with patch('urllib.request.urlopen',side_effect=TimeoutError('fixture-secret')) as request:
            with self.assertRaises(ProviderTimeout):
                perform_stage(checkpoint,'generation',lambda:self.provider()._post('/embeddings',{'model':'text-embedding-v4'}),'run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**kw:None)
        self.assertEqual(request.call_count,1)
        self.assertTrue(checkpoint['unknown_execution']['generation'])
        self.assertTrue(checkpoint['attempts'][0]['request_execution_unknown'])
    def test_confirmed_rejection_is_bounded_and_permanent_auth_not_retried(self):
        for status,code,expected in [(429,'Throttling',3),(401,'InvalidApiKey',1),(429,'insufficient_quota',1)]:
            def fail(*a,**kw):raise urllib.error.HTTPError('https://fixture.invalid',status,'rejected',{},io.BytesIO(json.dumps({'code':code,'message':'fixture'}).encode()))
            cp={'attempts':[]}
            with patch('urllib.request.urlopen',side_effect=fail) as request,patch('app.evaluation_stage.time.sleep'):
                with self.assertRaises(ProviderAPIError):perform_stage(cp,'generation',lambda:self.provider()._post('/embedding',{'model':'text-embedding-v4'}),'run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**kw:None)
            self.assertEqual(request.call_count,expected)
            self.assertFalse(cp.get('unknown_execution',{}).get('generation',False))

    def test_rerank_rejection_retries_only_that_rpc_not_successful_embedding(self):
        calls=[]
        def network(request,**kwargs):
            calls.append(request.full_url)
            if request.full_url.endswith('/embeddings'):
                return io.BytesIO(b'{"data":[{"index":0,"embedding":[1,2]}],"usage":{"total_tokens":2}}')
            if calls.count(request.full_url)<3:raise urllib.error.HTTPError(request.full_url,429,'limited',{},io.BytesIO(b'{"code":"Throttling"}'))
            return io.BytesIO(b'{"results":[{"index":0,"relevance_score":0.9}],"usage":{"total_tokens":2}}')
        provider=self.provider();cp={'attempts':[]}
        def action():
            provider.embed(['query'],2)
            return provider.rerank('query',[{'content':'fixture'}])
        with patch('urllib.request.urlopen',side_effect=network),patch('app.evaluation_stage.time.sleep'):
            perform_stage(cp,'generation',action,'run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**kw:None)
        self.assertEqual(len([c for c in calls if c.endswith('/embeddings')]),1)
        self.assertEqual(len(calls),4)

    def test_paid_rejection_retries_keep_audit_without_recharging_prior_calls(self):
        import tempfile
        from pathlib import Path
        from app.paid_run import PaidRun,controlled_run,accounting_only
        with tempfile.TemporaryDirectory() as directory:
            ledger=PaidRun(Path(directory)/'ledger.json',1.,{'text-embedding-v4':{'provider':'Alibaba','input':1.,'output':0.,'max_output':0}}, {},identity_check=lambda:{})
            count=[]
            def network(*args,**kw):
                count.append(1)
                if len(count)<3:raise urllib.error.HTTPError('https://fixture.invalid',429,'limited',{},io.BytesIO(b'{"code":"Throttling"}'))
                return io.BytesIO(b'{"usage":{"total_tokens":2}}')
            with controlled_run(ledger),accounting_only(),patch('urllib.request.urlopen',side_effect=network),patch('app.evaluation_stage.time.sleep'):
                perform_stage({'attempts':[]},'generation',lambda:self.provider()._post('/embeddings',{'model':'text-embedding-v4'}),'run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**kw:None)
            self.assertEqual([c['status'] for c in ledger.calls],['rejected','rejected','ok'])
            self.assertAlmostEqual(ledger.spent,.000002)
            self.assertIsNone(ledger.stopped)

    def test_unknown_or_unsettled_ledger_never_passes_resume_guard(self):
        import tempfile
        from pathlib import Path
        from app.paid_run import require_reconciled_execution
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger.json'
            for status in ['unknown','reserved','failed']:
                path.write_text(json.dumps({'identity':{},'calls':[{'status':status}]}))
                with self.assertRaisesRegex(ValueError,'须先对账'):require_reconciled_execution({'auto_recovery':{'ledger_path':str(path),'ledger_identity':{}}})

    def test_successful_result_without_settled_usage_is_saved_and_never_repeated(self):
        from app.telemetry import record_usage
        from app.providers import ProviderUnavailable
        from app.paid_run import require_reconciled_execution
        result={'answer':'saved answer','retrieval_trace':{'final':[]}};checkpoint={'attempts':[]}
        def answer():
            record_usage({'provider':'DeepSeek','status':'ok'})
            return result
        with self.assertRaisesRegex(ProviderUnavailable,'有效结果已保存'):
            perform_stage(checkpoint,'generation',answer,'run',automatic=True,check_stop=lambda:None,on_state=lambda *a,**kw:None)
        self.assertEqual(checkpoint['execution'],result)
        self.assertFalse(checkpoint.get('unknown_execution',{}).get('generation',False))
        self.assertTrue(checkpoint['unsettled_usage']['generation'])
        with self.assertRaisesRegex(ValueError,'对账'):require_reconciled_execution({'checkpoints':{'q':checkpoint}})

class FiftyCaseCheckpointTests(unittest.TestCase):
    def test_38_results_and_saved_39th_answer_reuse_then_only_50_forms_final_scores(self):
        import test_baseline_resume as fixture
        from app.providers import ProviderTimeout
        fixture.ResumeTests.setUp(self)
        try:
            from app.corpus import current_manifest,manifest_identity
            items=[{'id':f'Q{i}','question':f'Q{i}','reference_answer':'事实',
                'test_category':'positive' if i<=20 else 'ablation' if i<=30 else 'negative',
                'negative_subtype':None if i<=30 else 'safety_critical' if i<=40 else 'prompt_injection','evidence':[]} for i in range(1,51)]
            snapshot={'questions':items,'question_ids':[q['id'] for q in items],'corpus_fingerprint':manifest_identity(current_manifest())}
            with self.store.connection() as c:c.execute('UPDATE dataset_versions SET snapshot_json=?',(json.dumps(snapshot),))
            self.runtime.fail=None
            baseline=self.runner.execute_baseline(*self.runner.start_baseline())
            exp=self.store.create_experiment(baseline['id'],'completed');config={**baseline['config'],'top_k':6};config.pop('run_target',None)
            self.store.save_candidate(exp,'R1-A',config,{'round':1,'candidate_label':'A','observed_evidence':['Q39']})
            cid=exp+'-R1-A';self.runtime.answers=[];self.runtime.judges=[]
            original=self.runtime.judge
            def fail(q,*args,**kwargs):
                if q=='Q39':raise ProviderTimeout('known offline fixture interruption')
                return original(q,*args,**kwargs)
            with patch.object(self.runtime,'judge',side_effect=fail):partial=self.runner.run_candidate(cid,automatic=False)
            self.assertEqual(partial['result']['completed'],38)
            self.assertIsNone(partial['result']['gates']['passed_count'])
            self.assertIsNone(partial['result']['bad_case_count'])
            self.assertIsNone(partial['result']['qualification']['qualified'])
            self.assertEqual(partial['result']['regression']['status'],'NOT_EVALUABLE')
            plan=self.runner.candidate_resume_plan(cid)
            self.assertTrue(plan['can_resume']);self.assertEqual(plan['reusable'],38)
            self.assertEqual((plan['pending_answers'],plan['pending_judges'],plan['saved_answers_waiting_judge']),(11,12,1))
            source=self.store.evaluation_run(partial['result']['evaluation_run_id'])
            completed=self.runner.run_candidate(cid,automatic=False)
            self.assertEqual(completed['result']['completed'],50)
            self.assertEqual(completed['result']['gates']['passed_count'],11)
            self.assertIsNotNone(completed['result']['bad_case_count'])
            self.assertEqual(self.store.evaluation_run(source['id']),source)
            for i in range(1,39):
                self.assertEqual(self.runtime.answers.count(f'Q{i}'),1)
                self.assertEqual(self.runtime.judges.count(f'Q{i}'),1)
            self.assertEqual(self.runtime.answers.count('Q39'),1)
        finally:fixture.ResumeTests.tearDown(self)
