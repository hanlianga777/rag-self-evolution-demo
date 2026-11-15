import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from api_fixture import main
from app.governance import GovernanceStore

class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=GovernanceStore(Path(self.tmp.name)/'test.db')
        self.patch=patch.object(main,'store',self.store);self.patch.start();self.addCleanup(self.patch.stop)
        self.client=TestClient(main.app)

    def test_pdf_is_confined_to_documents_and_missing_files_return_404(self):
        directory=Path(self.tmp.name)/'documents';directory.mkdir();(directory/'manual.pdf').write_bytes(b'%PDF-1.4\n')
        (Path(self.tmp.name)/'outside.pdf').write_bytes(b'private')
        (directory/'link.pdf').symlink_to(Path(self.tmp.name)/'outside.pdf')
        with patch('app.corpus.DOCUMENTS_DIR',directory):
            self.assertEqual(self.client.get('/api/source-pdf',params={'name':'manual.pdf'}).content,b'%PDF-1.4\n')
            head=self.client.head('/api/source-pdf',params={'name':'manual.pdf'})
            self.assertEqual(head.status_code,200);self.assertEqual(head.content,b'')
            for name in ['../outside.pdf','link.pdf','missing.pdf','manual.txt']:
                self.assertEqual(self.client.get('/api/source-pdf',params={'name':name}).status_code,404)

    def test_human_reason_survives_without_changing_answer_or_metrics(self):
        event=self.store.record_monitoring_event(question='问题',answer='原始回答',bad_case=False,severity='ordinary',determinable=False,metrics={'latency_ms':42})
        response=self.client.post('/api/monitoring/events/'+event['id']+'/assessment',json={'bad_case':True,'severity':'ordinary','reason':'遗漏安全前提'})
        self.assertEqual(response.status_code,200)
        row=self.store.monitoring_events()[0]
        self.assertEqual(row['metrics']['human_assessment']['reason'],'遗漏安全前提')
        self.assertEqual((row['answer'],row['metrics']['latency_ms']),('原始回答',42))

    def test_stream_delivers_generation_deltas_and_records_one_final_answer(self):
        def answer(question,*,on_token=None):
            on_token('甲');on_token('乙')
            return {'answer':'甲乙','mode':'live','model':'stub','latency_ms':42,'retrieval':[],'evidence':[],'sources':[],'version':'v','config':{'top_k':4},'fallback_reason':None}
        with patch.object(main.ai_service,'baseline_preview',side_effect=answer) as call:
            response=self.client.post('/api/preview/stream',json={'question':'问题'})
        self.assertEqual(response.status_code,200);self.assertIn('text/event-stream',response.headers['content-type'])
        frames=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        self.assertEqual([f['text'] for f in frames if f['type']=='delta'],['甲','乙'])
        self.assertEqual(frames[-1]['type'],'done');self.assertEqual(frames[-1]['result']['baseline']['answer'],'甲乙')
        self.assertEqual(len(self.store.monitoring_events()),1);self.assertEqual(call.call_count,1)

    def test_release_review_missing_records_are_unknown_and_read_only(self):
        response=self.client.get('/api/release-review')
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()['checks']),5)
        self.assertTrue(all(c['ok'] is None for c in response.json()['checks']))
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM approvals').fetchone()[0],0)

    def test_release_signatures_belong_to_frozen_snapshot_and_checks_do_not_invent_success(self):
        from app.release_view import release_review_view
        from app.policy import DEFAULT_PIPELINE_CONFIG
        run={'status':'completed','config':dict(DEFAULT_PIPELINE_CONFIG),'judge':{'evaluation_identity':'j'},'dataset_version_id':'g','dataset_snapshot_json':json.dumps({'id':'g','question_ids':['q'],'corpus_fingerprint':{'v':'saved'},'gate1':{'status':'frozen','actor':'签字人','confirmed_at':'saved-time'}})}
        candidate={'id':'c','experiment_id':'e','config':dict(DEFAULT_PIPELINE_CONFIG),'result':{'evaluation_run_id':'r','gates':{'passed':False},'regression':{'new_critical_failures':1}}}
        with patch.object(self.store,'candidate',return_value=candidate),patch.object(self.store,'evaluation_run',return_value=run),patch('app.release_view.current_manifest',return_value={}),patch('app.release_view.manifest_identity',return_value={'v':'changed'}):
            result=release_review_view(self.store,'c')
        self.assertEqual(result['gates'][0]['actor'],'签字人')
        self.assertEqual(result['gates'][0]['created_at'],'saved-time')
        self.assertEqual([c['ok'] for c in result['checks']],[False,False,True,True,False])

    def test_provider_observer_receives_content_before_completion_and_never_reasoning(self):
        import io
        from app.providers import DeepSeekProvider,answer_content
        from app.config import Settings
        received=[]
        class Response(io.BytesIO):
            status=200;headers={}
            def __iter__(inner):
                yield b'data: {"choices":[{"delta":{"reasoning_content":"PRIVATE"}}]}\n\n'
                yield 'data: {"choices":[{"delta":{"content":"答"}}]}\n\n'.encode()
                self.assertEqual(received,[None,'答'])
                yield b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":1}}\n\n'
        provider=DeepSeekProvider(Settings('fake','https://invalid','deepseek-flash'))
        request=provider._request('system','user',False,True)
        with patch('urllib.request.urlopen',return_value=Response()),patch('app.paid_run.payment_usage'),answer_content(received.append):
            result=provider._complete_request(request,True)
        self.assertEqual(result['content'],'答');self.assertNotIn('PRIVATE',str(received))
