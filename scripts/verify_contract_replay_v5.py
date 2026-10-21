"""Read-only real50 eligibility + optional isolated Mock proof, never a paid Replay."""
import argparse,contextlib,hashlib,json,os,pathlib,sqlite3,sys,tempfile
from types import SimpleNamespace
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def verify(simulate=False):
    database=ROOT/'backend/data/demo.db';before=hashlib.sha256(database.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as temporary,contextlib.ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ,{'RAG_DEMO_DB_PATH':str(database),'RAG_DEMO_ENV_PATH':temporary+'/missing.env','RAG_DIAGNOSTIC_DIR':temporary+'/diagnostics','RAG_JUDGE_PROBE_DIR':temporary+'/probes','RAG_DEMO_INDEX_DIR':str(ROOT/'backend/data/index'),'RAG_DEMO_DOCUMENTS_DIR':str(ROOT/'backend/documents')}))
        from app.governance import GovernanceStore
        from app.corpus import CorpusStore
        from app.evaluation import EvaluationRunner
        from app.evaluation_contract import BUSINESS_JUDGE_PROMPT,scope_quote_present,quote_present,validate_business_judgment
        from app.diagnostic_evidence import digest
        from app.diagnostics import _current_corpus
        for method in ['urllib.request.urlopen','app.providers.DeepSeekProvider.complete','app.knowledge_pipeline.AlibabaProvider._post']:
            stack.enter_context(patch(method,side_effect=AssertionError('offline Provider forbidden')))
        store=object.__new__(GovernanceStore);store.database_path=database
        @contextlib.contextmanager
        def readonly():
            c=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
            try:yield c
            finally:c.close()
        store.connection=readonly
        source_id='EVAL-20261021013401711966';source=store.evaluation_run(source_id)
        runtime=SimpleNamespace(model=source['judge']['model'],corpus=CorpusStore())
        runner=EvaluationRunner(store,runtime);plan=runner.judge_replay_preflight(source_id,include_executions=True)
        snapshot,items,config,judge=runner.baseline_inputs(source_id)
        chunks,fp=_current_corpus({'corpus_fingerprint':snapshot['corpus_fingerprint']})
        inputs=[];q18_checks=[];norms=[]
        for item in items:
            execution=plan['executions'].get(item['id'])
            if not execution:continue
            context=runner.judge_context(item,execution)
            text=BUSINESS_JUDGE_PROMPT+json.dumps({'question':item['question'],'reference_answer':item['reference_answer'] or item['raw'].get('expected_behavior','拒答或澄清'),'actual_answer':execution['answer'],**{k:v for k,v in context.items() if k!='programmatic_evidence_observation' and not k.startswith('_')}},ensure_ascii=False)
            nonascii=sum(ord(c)>127 for c in text);inputs.append(round((len(text)-nonascii)*.3+nonascii*.6))
            norms.append({'question_id':item['id'],'sources':[{k:n[k] for k in ('chunk_id','role','frozen_summary')}|{'full_characters':len(n['content'])} for n in context['golden_norms']]})
            for entry in context['final_context']:
                scope=entry.get('source_scope')
                if not scope:continue
                quote={'source_id':entry['chunk_id'],'heading_source_id':scope['source_id'],'quote':scope['quote']}
                assert scope_quote_present(quote,context['final_context'],chunks)
                q18_checks.append({'question_id':item['id'],'final_id':entry['chunk_id'],'title_id':scope['source_id'],'title':scope['quote'],'scope_valid':True,'body_fact_valid':quote_present({'source_id':entry['chunk_id'],'quote':scope['quote']},[entry],display=True)})
        assert plan['can_replay'] and plan['reusable']==50,(plan['reusable'],[(e['question_id'],e['blockers']) for e in plan['eligibility'] if not e['eligible']])
        assert plan['new_evaluation_identity']!=plan['source_evaluation_identity']
        proof=None
        if simulate:
            copied=pathlib.Path(temporary)/'mock.db'
            with readonly() as original,sqlite3.connect(copied) as target:original.backup(target)
            fake_store=object.__new__(GovernanceStore);fake_store.database_path=copied
            calls=[]
            def mock_judge(q,expected,answer,category,context=None):
                calls.append(q)
                return {'verdict':'FAIL','checks':[{'requirement':'offline independent mock judgment','met':False,'answer_quotes':[],'support':[]}],
                    'issues':[],'reason':'Mock only, not a new semantic evaluation','quality':{'correctness':0,'faithfulness':0,'completeness':0}}
            runtime.judge=mock_judge;runtime.answer=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Replay called generation'))
            isolated_runner=EvaluationRunner(fake_store,runtime)
            old=deepcopy_json(fake_store.evaluation_run(source_id));old_cases=deepcopy_json(fake_store.evaluation_case_results(source_id))
            try:isolated_runner.start_judge_replay(source_id,automatic=False)
            except ValueError as error:assert 'Q18' in str(error)
            else:raise AssertionError('Replay bypassed Q18 probe')
            # Explicit test-only bypass; no fake real probe/human approval is saved.
            stack.enter_context(patch('app.q18_probe.require_reviewed_probe',return_value='ISOLATED_TEST_GATE_ONLY'))
            run_id,approved,cfg=isolated_runner.start_judge_replay(source_id,automatic=False)
            completed=isolated_runner.execute_baseline(run_id,approved,cfg)
            assert completed['status']=='completed' and len(calls)==50,(completed['status'],completed.get('error_message'))
            assert fake_store.require_current_baseline(run_id)['id']==run_id
            assert old==fake_store.evaluation_run(source_id) and old_cases==fake_store.evaluation_case_results(source_id)
            assert len(completed['result']['gates']['gates'])==11
            # Damaged checkpoints and their resumed child must never fall back to generation.
            broken_id,approved,cfg=isolated_runner.start_judge_replay(source_id,automatic=False)
            broken=fake_store.evaluation_run(broken_id)['result'];broken['checkpoints'][approved[0]['id']].pop('execution')
            fake_store.update_evaluation_progress(broken_id,broken)
            called_before=len(calls);failed=isolated_runner.execute_baseline(broken_id,approved,cfg)
            assert failed['status']!='completed' and len(calls)==called_before
            child_id,approved,cfg=isolated_runner.start_baseline(broken_id)
            resumed=isolated_runner.execute_baseline(child_id,approved,cfg)
            assert resumed['status']!='completed' and len(calls)==called_before and resumed['result'].get('judge_replay')
            assert fake_store.evaluation_run(source_id)==old
            proof={'kind':'ISOLATED_MOCK_NOT_PROVIDER','judges':50,'generations':0,'completed':50,'probe_gate_explicit_test_only_bypass':True,'require_current_baseline':True,'old_source_unchanged':True,
                'damaged_execution_blocks_without_generation':True,'resumed_child_keeps_no_generation_guard':True}
        plan.pop('executions');plan['normative_input_inventory']=norms;plan['scope_binding_checks']=q18_checks;plan['mock_proof']=proof
        rates=json.loads((ROOT/'backend/config/deepseek-prices.json').read_text())
        token_input=sum(inputs);cap=50*32768
        plan['cost_preflight']={'pricing':'local snapshot only, recheck before authorization','price_snapshot':rates,
            'input_estimate':token_input,'input_estimate_method':'existing approximate_character_ratio_not_model_tokenizer',
            'input_conservative_range':[round(token_input*.7),round(token_input*1.5)],'output_expected_range':[50*1000,50*6000],'output_per_attempt_cap':32768,
            'expected_usd_range':[(token_input*.7*.15+50*1000*.6)/1e6,(token_input*1.5*.3+50*6000*1.2)/1e6],
            'correction_feedback_extra_input_estimate_cap':50*32768*2,
            'worst_150_attempts_estimate_usd':((token_input*1.5*3+50*32768*2)*.3+cap*3*1.2)/1e6,
            'q18_probe_calls':1,'q18_probe_max_calls':3,'full_replay_calls':50,'full_replay_max_calls':150,
            'semantic_diagnostics_extra_calls':'0 in Replay; separate explicit authorization, at most one per requested case',
            'hard_cost_cap':'must freeze a user-authorized budget/token limits before real execution; estimate is not billing proof'}
        assert hashlib.sha256(database.read_bytes()).hexdigest()==before
        plan.update(provider_calls=0,database_sha256=before,production_history_unchanged=True)
        return plan


def deepcopy_json(value):return json.loads(json.dumps(value,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--simulate',action='store_true');parser.add_argument('--output');args=parser.parse_args()
    result=verify(args.simulate);text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:pathlib.Path(args.output).write_text(text+'\n')
    print(text)
