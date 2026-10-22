"""Read-only evidence plus disposable DB copy. Stub strategy is never a real run."""
import argparse,hashlib,json,os,sqlite3,sys,tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def verify(database,run_id):
    before=hashlib.sha256(database.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as temporary,ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ,{'RAG_DEMO_DB_PATH':temporary+'/demo.db','RAG_DEMO_ENV_PATH':temporary+'/missing.env','RAG_DIAGNOSTIC_DIR':temporary+'/diagnostics'}))
        for method in ['urllib.request.urlopen','app.providers.DeepSeekProvider.complete','app.knowledge_pipeline.AlibabaProvider._post']:
            stack.enter_context(patch(method,side_effect=AssertionError('offline verification prohibits Provider/network')))
        from app.governance import GovernanceStore
        from app.diagnostics import _current_corpus,diagnostic_view
        from app.evidence_resolver import diagnostic_plan
        from app.optimization import OptimizationAgent,validate_intervention
        from app.policy import DEFAULT_PIPELINE_CONFIG
        source=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
        copy=sqlite3.connect(temporary+'/demo.db')
        source.backup(copy);source.close();copy.close()
        store=object.__new__(GovernanceStore);store.database_path=Path(temporary)/'demo.db'
        baseline=store.evaluation_run(run_id)
        if not baseline or baseline['status']!='completed':raise ValueError('requires actual completed Baseline')
        chunks,fingerprint=_current_corpus({'corpus_fingerprint':json.loads(baseline['dataset_snapshot_json'])['corpus_fingerprint']})
        if not chunks:raise ValueError('current Canonical required')
        stack.enter_context(patch('app.diagnostics._current_corpus',return_value=(chunks,fingerprint)))
        cases=[row for row in store.bad_case_rows() if row['run_id']==run_id]
        base={**DEFAULT_PIPELINE_CONFIG,**baseline['config']}
        for key in ('run_target','knowledge_identity'):base.pop(key,None)
        routes=[]
        for row in cases:
            view=diagnostic_view(row['result'],corpus_chunks=chunks,corpus_fingerprint=fingerprint)
            plan=view['experiment_plan']
            if plan['status']!='exploratory':
                routes.append({'question_id':row['question_id'],'path':plan,'candidate_legal':False})
                continue
            direction=next(d for d in ('candidate_recall','context_selection','grounded_generation') if d in plan['directions'])
            diff={'candidate_k':24} if direction=='candidate_recall' else {'rerank':'query_only'} if direction=='context_selection' and view['primary_root_cause']=='Unknown' else {'top_k':6} if direction=='context_selection' else {'prompt_strategy':'Completeness'}
            observation={'candidate_recall':'candidate_pool_gap','context_selection':'context_pool_gap','grounded_generation':'answer_requirement_gap'}[direction]
            proposal={'experiment_kind':'exploratory','root_cause':view['primary_root_cause'],
                'target_bad_cases':[row['question_id']],'root_cause_evidence':[row['question_id']],
                'target_group':'offline material audit','intervention_direction':direction,'config_diff':diff,
                'evidence_assertions':[{'target_id':row['question_id'],'observation':observation}],
                'parameter_dependencies':[],'hypothesis':plan['hypothesis'],'falsification':plan['falsification'],
                'why':'只读真实冻结材料的结构覆盖差异，语义与现场适用性仍未知',
                'expected_improvement':'需要真实新答及完整50题验证，不预先宣称改善','risk':plan['risk']}
            validate_intervention(proposal,{row['question_id']:row['result']},base)
            routes.append({'question_id':row['question_id'],'path':plan,'candidate_legal':True,'proposal':proposal})
        # Explicit offline strategy fixture: groups material-backed hypotheses, never model efficacy.
        class OfflineStrategy:
            def complete(self,system,user,**kwargs):
                self.prompt=json.loads(user);groups={}
                for row in routes:
                    if not row['candidate_legal']:continue
                    p=row['proposal'];key=(p['root_cause'],p['intervention_direction'],json.dumps(p['config_diff'],sort_keys=True))
                    if key not in groups:groups[key]={**p,'target_bad_cases':[],'root_cause_evidence':[],'evidence_assertions':[]}
                    group=groups[key]
                    for field in ('target_bad_cases','root_cause_evidence','evidence_assertions'):group[field].extend(p[field])
                candidates=[{**p,'id':label} for label,p in zip('ABC',groups.values())]
                return json.dumps({'candidates':candidates,'insufficient_evidence':'OFFLINE fixture strategy; no real model optimization result'})
        provider=OfflineStrategy()
        result=OptimizationAgent(store,provider).generate(run_id)
        assert {r['question_id'] for r in cases}=={r['question_id'] for r in provider.prompt['diagnostic_tasks']}
        assert len(provider.prompt['bad_cases'])==len(cases)
        from types import SimpleNamespace
        from app.ai_service import AiService
        from app.corpus import CorpusStore,INDEX_DIR
        from app.evaluation import EvaluationRunner
        class OfflineSandboxProvider:
            settings=SimpleNamespace(configured=True,model=baseline['judge']['model'])
            def complete_with_metrics(self,*args,**kwargs):
                return {'content':'离线占位响应：未运行真实模型，无法确认现场条件。','ttft_ms':1,'input_tokens':None,'output_tokens':None}
            def judge(self,q,expected,answer,**kwargs):
                category=kwargs['context']['category']
                return {'verdict':'FAIL','checks':[{'requirement':'OFFLINE fixture: no real business conclusion',
                    'check_type':'negative_behavior' if category=='negative' else 'fact',
                    'met':False,'answer_quotes':[answer] if category=='negative' else [],'support':[]}],
                    'issues':[],'reason':'OFFLINE fixed failure, not a new real Judge result',
                    'quality':{'correctness':0,'completeness':0,'faithfulness':1}}
        runtime=AiService(store,CorpusStore(INDEX_DIR),OfflineSandboxProvider(),False)
        # Explicit synthetic vector scores; BM25/fusion/selection/Parent/TopK run production code.
        runtime.retriever.vector_candidates=lambda q,limit,**kwargs:[{'chunk_id':c['chunk_id'],'score':1-i/max(1,len(chunks))} for i,c in enumerate(chunks[:limit])]
        stack.enter_context(patch('app.knowledge_pipeline.AlibabaProvider.rerank',side_effect=lambda q,hits:hits))
        sandboxes=[]
        for candidate in result['candidates']:
            checked=EvaluationRunner(store,runtime).run_candidate(candidate['id'],automatic=False)
            evaluation=store.evaluation_run(checked['result']['evaluation_run_id'])
            outputs=store.evaluation_case_results(evaluation['id'])
            assert checked['status']=='evaluated',checked['result'].get('error')
            assert len(outputs)==len(json.loads(baseline['dataset_snapshot_json'])['question_ids'])
            assert all(all(c['programmatic_metrics']['retrieval_trace']['config'].get(k)==v for k,v in candidate['config'].items()) for c in outputs)
            assert not checked['result']['qualification']['qualified']
            sandboxes.append({'candidate_id':candidate['id'],'status':checked['status'],'completed':len(outputs),
                'config_used':candidate['config'],'comparison_complete':checked['result']['comparison_complete'],
                'regression_passed':checked['result']['regression']['passed'],'qualification':checked['result']['qualification'],
                'all_fixed_question_ids':checked['result']['all_fixed_question_ids'],
                'new_regression_question_ids':checked['result']['new_regression_question_ids'],
                'kind':'synthetic vector/rerank/answer/Judge; REAL frozen 50 + production retrieval/executor; NOT efficacy'})
        assert store.evaluation_run(run_id)==baseline
        recommendation=store.recommendation(result['id'])['result']
        assert recommendation['recommended_candidate'] is None
        rows=[{'question_id':row['question_id'],'question':row['result']['question'],
            'diagnosis':diagnostic_view(row['result'],corpus_chunks=chunks,corpus_fingerprint=fingerprint)} for row in cases]
        output={'run_id':run_id,'kind':'offline_isolated_copy_NOT_real_agent_or_repair','provider_calls':0,'business_failures':len(cases),
            'failures_in_agent_input':len(provider.prompt['bad_cases']),'diagnostic_plan':diagnostic_plan(store,run_id),'cases':rows,
            'question_paths':routes,'legal_exploration_count':sum(r['candidate_legal'] for r in routes),
            'isolated_recommendation':recommendation['status'],'isolated_frozen50_sandboxes':sandboxes,'isolated_fixture_candidates':[{'id':c['id'],'config':c['config'],'reasoning':c['reasoning']} for c in result['candidates']],
            'processing_progress':result['result']['processing_progress'],'real_verified_repairs':0,
            'original_run_summary':{k:v for k,v in baseline['result'].items() if k not in {'checkpoints','cases','execution_checkpoints'}},'original_database_sha256':before}
    output['original_database_unchanged']=hashlib.sha256(database.read_bytes()).hexdigest()==before
    assert output['original_database_unchanged']
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=ROOT/'backend/data/demo.db');parser.add_argument('--run',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=verify(args.database.resolve(),args.run)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ['provider_calls','business_failures','failures_in_agent_input','legal_exploration_count','real_verified_repairs','original_database_unchanged']},ensure_ascii=False))
