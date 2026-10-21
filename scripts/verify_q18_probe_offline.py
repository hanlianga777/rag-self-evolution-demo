"""Disposable real-execution copy + fake HTTP: never a real probe or approval."""
import contextlib,hashlib,io,json,os,shutil,sqlite3,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def verify():
    database=ROOT/'backend/data/demo.db';before=hashlib.sha256(database.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory,contextlib.ExitStack() as stack:
        directory=Path(directory);copied=directory/'test.db'
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(copied) as target:source.backup(target)
        for original,name in [(ROOT/'backend/data/index','index'),(ROOT/'backend/documents','documents')]:shutil.copytree(original,directory/name)
        stack.enter_context(patch.dict(os.environ,{'RAG_DEMO_DB_PATH':str(copied),'RAG_DEMO_INDEX_DIR':str(directory/'index'),'RAG_DEMO_DOCUMENTS_DIR':str(directory/'documents'),
            'RAG_DEMO_ENV_PATH':str(directory/'missing.env'),'RAG_JUDGE_PROBE_DIR':str(directory/'probes'),'RAG_DIAGNOSTIC_DIR':str(directory/'diagnostics'),
            'DEEPSEEK_API_KEY':'OFFLINE_FIXTURE','DEEPSEEK_MODEL':'deepseek-v4-flash','DEEPSEEK_BASE_URL':'https://api.deepseek.com'}))
        stack.enter_context(patch('urllib.request.urlopen',side_effect=AssertionError('No network in offline probe test')))
        from app.q18_probe import probe_preflight,run_probe,review_probe,require_reviewed_probe,save_json,QUESTION_ID
        from app.governance import GovernanceStore
        from app.evaluation import EvaluationRunner
        from app.ai_service import AiService
        from app.corpus import CorpusStore
        from app.providers import DeepSeekProvider,ProviderTimeout,ProviderInvalidResponse
        from app.config import load_settings
        from app.paid_run import paid_request,current_paid_run
        from app.evaluation_contract import business_judge_input,BUSINESS_JUDGE_PROMPT
        from app.telemetry import record_usage
        store=object.__new__(GovernanceStore);store.database_path=copied
        runtime=AiService(store,CorpusStore(),DeepSeekProvider(load_settings()),force_mock=False)
        runtime.answer=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Probe called generation'))
        runner=EvaluationRunner(store,runtime);source_id='EVAL-20261021013401711966'
        pre=probe_preflight(runner,source_id);plan=pre['plan'];assert plan['reusable']==50
        original=hashlib.sha256(copied.read_bytes()).hexdigest()
        def blocked():
            try:runner.start_judge_replay(source_id)
            except ValueError as error:assert 'Q18' in str(error)
            else:raise AssertionError('Probe gate bypassed')
            snapshot,_,config,judge=runner.baseline_inputs(source_id)
            try:store.create_baseline_run(snapshot,config,judge,judge_replay=plan)
            except ValueError as error:assert 'Q18' in str(error)
            else:raise AssertionError('Transactional probe gate bypassed')
        blocked()
        price=directory/'prices.json';save_json(price,{'checked_at':datetime.now(timezone.utc).isoformat(),'model':'deepseek-v4-flash','currency':'USD',
            'source_url':'https://api-docs.deepseek.com/quick_start/pricing/','input_per_million':.3,'output_per_million':1.2,'authorization_budget_cap_usd':.5})
        valid={'verdict':'FAIL','reason':'OFFLINE FIXTURE ONLY: independent business review still required',
            'checks':[{'check_type':'fact','requirement':'完整校准规范','met':False,'answer_quotes':[],'support':[]}],
            'issues':[],'quality':{'correctness':0,'completeness':0,'faithfulness':0}}
        invalid={'verdict':'PASS','reason':'scope only fixture','issues':[],'quality':{'correctness':4,'completeness':1,'faithfulness':1},
            'checks':[{'check_type':'scope','requirement':'R3遥控器','met':True,'answer_quotes':['R3遥控器'],'support':[],
                'scope_support':[{'source_id':'DOC-003-C-00009','heading_source_id':'DOC-003-C-00004','quote':'R3遥控器'}]}]}
        calls=[];responses=[]
        def fake_complete(provider,system,user,json_mode=False,*,temperature=.2,**kwargs):
            assert system==BUSINESS_JUDGE_PROMPT and json_mode and temperature==0
            payload=json.loads(provider._request(system,user,json_mode,False,temperature).data)
            assert payload['max_tokens']==32768
            data=json.loads(user);assert data['actual_answer']==pre['execution']['answer'] and data['final_context']==pre['context']['final_context']
            if not calls:assert user==business_judge_input(pre['item']['question'],pre['item']['reference_answer'],pre['execution']['answer'],pre['context'])
            calls.append(payload)
            reply=responses.pop(0)
            with paid_request('DeepSeek',provider.settings.model,payload):
                if reply=='unknown':
                    record_usage({'provider':'DeepSeek','requested_model':provider.settings.model,'status':'unknown'})
                    raise ProviderTimeout('Unknown fixture request')
                raw=json.dumps(valid if reply=='known-timeout' else reply,ensure_ascii=False);current_paid_run().response({'choices':[{'message':{'content':raw}}]})
                record_usage({'provider':'DeepSeek','requested_model':provider.settings.model,'status':'ok','prompt_tokens':12000,'completion_tokens':1000})
            if reply=='known-timeout':raise ProviderTimeout('Known settled fixture request')
            return raw
        def run(auth,**kwargs):
            return run_probe(runner,source_id,expected_binding=pre['binding'],authorize_provider=True,authorization_id=auth,budget_usd=.5,price_snapshot=price,**kwargs)
        real_complete=DeepSeekProvider.complete
        stack.enter_context(patch.object(DeepSeekProvider,'complete',fake_complete));stack.enter_context(patch('app.evaluation_stage.time.sleep',return_value=None))
        # Every authorization prerequisite fails before any HTTP request or artifact claim.
        from dataclasses import replace
        with patch.object(runtime.provider,'settings',replace(runtime.provider.settings,base_url='https://stale.example')):
            try:probe_preflight(runner,source_id)
            except ValueError:pass
            else:raise AssertionError('Loaded Provider differs from verified settings')
        fresh_price=json.loads(price.read_text());stale_price={**fresh_price,'checked_at':'2000-01-01T00:00:00+00:00'}
        save_json(price,stale_price)
        try:run('OFFLINE-STALE-PRICE')
        except ValueError:pass
        else:raise AssertionError('Stale price accepted')
        save_json(price,fresh_price)
        try:run_probe(runner,source_id,expected_binding=pre['binding'],authorize_provider=False,authorization_id='OFFLINE-NO-AUTH',budget_usd=.5,price_snapshot=price)
        except ValueError:pass
        else:raise AssertionError('Unapproved probe accepted')
        assert not calls
        responses.extend([invalid,valid]);result=run('OFFLINE-CORRECTION-FIXTURE')
        assert len(calls)==2 and 'judge_correction' in json.loads(calls[1]['messages'][1]['content'])
        assert result['status']=='judge_complete' and result['business_review_required'];blocked()
        try:run('OFFLINE-CORRECTION-FIXTURE')
        except FileExistsError:pass
        else:raise AssertionError('Authorization reused')
        review_probe(runner,source_id,result['path'],actor='OFFLINE_TEST_NOT_HUMAN',decision='approved',facts='Fixture review only',safety='Fixture safety only',scope_separation='Fixture scope only')
        assert require_reviewed_probe(copied,plan)==result['path']
        record=json.loads(Path(result['path']).read_text())
        record['item']['question']+='tampered';save_json(result['path'],record);blocked()
        record['item']['question']=pre['item']['question'];record['mode']='mock';save_json(result['path'],record);blocked()
        # Rejected result integrity and model/config changes cannot reuse approval.
        record['mode']='real';record['case']['judge_result']['checks'][0]['met']=True;save_json(result['path'],record);blocked()
        calls.clear();responses.extend(['unknown'])
        try:run('OFFLINE-UNKNOWN-FIXTURE')
        except (ProviderTimeout,RuntimeError):pass
        else:raise AssertionError('Unknown request should stop')
        assert len(calls)==1
        artifact=json.loads(next(p for p in (directory/'probes').glob('*.probe.json') if json.loads(p.read_text())['authorization_id']=='OFFLINE-UNKNOWN-FIXTURE').read_text())
        assert artifact['status']=='technical_error' and artifact['checkpoint']['unknown_execution']['judge']
        calls.clear();responses.extend([invalid,invalid,valid])
        try:run('OFFLINE-INVALID-TWICE')
        except ProviderInvalidResponse:pass
        else:raise AssertionError('Two invalid outputs should stop')
        assert len(calls)==2
        calls.clear();responses.clear();responses.extend(['known-timeout','known-timeout',valid])
        third=run('OFFLINE-THREE-KNOWN-ATTEMPTS');assert len(calls)==3 and third['status']=='judge_complete'
        third_record=json.loads(Path(third['path']).read_text());third_record['mode']='mock';save_json(third['path'],third_record)
        # Real Provider HTTP parsing, including paid_request's stopped flag on truncation.
        bodies=[io.BytesIO(json.dumps({'id':'OFFLINE_HTTP_FIXTURE','choices':[{'message':{'content':json.dumps(valid,ensure_ascii=False)},'finish_reason':reason}],
            'usage':{'prompt_tokens':12000,'completion_tokens':1000}}).encode()) for reason in ['length','stop']]
        with patch.object(DeepSeekProvider,'complete',real_complete),patch('urllib.request.urlopen',side_effect=bodies) as http:
            truncated=run('OFFLINE-REAL-PARSER-TRUNCATION');assert http.call_count==2 and truncated['status']=='judge_complete'
        truncated_record=json.loads(Path(truncated['path']).read_text());assert len(truncated_record['known_response_retries'])==1
        truncated_record['mode']='mock';save_json(truncated['path'],truncated_record)
        assert hashlib.sha256(copied.read_bytes()).hexdigest()==original
        assert hashlib.sha256(database.read_bytes()).hexdigest()==before
        return {'kind':'ISOLATED_HTTP_MOCK_NOT_REAL_PROBE','provider_calls':0,'reusable':50,'authorization_price_loaded_config_preflight_blocks':True,'correction_uses_official_input':True,
            'real_http_parser_truncation_corrected':True,'known_attempt_limit':3,'invalid_response_attempt_limit':2,'unknown_stops_after':1,'authorization_reuse_rejected':True,
            'parser_complete_requires_business_review':True,'mock_tampered_unreviewed_blocked':True,'start_and_transaction_gate':True,
            'production_and_copy_database_unchanged':True,'generation_calls':0}

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
