"""Query-only saved-pool counterfactual. No online strategy or parameter is added."""
import argparse,json,os,sqlite3,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
os.environ['RAG_DEMO_ENV_PATH']='/nonexistent/offline.env'
from app.retrieval import VectorRetriever
from app.knowledge_pipeline import expand_parents
from app.evaluation_contract import quote_present
from app.diagnostics import _current_corpus,diagnostic_view


def probe(run_id,question_id):
    with sqlite3.connect((ROOT/'backend/data/demo.db').as_uri()+'?mode=ro',uri=True) as connection:
        raw=connection.execute('SELECT result_json FROM evaluation_case_results WHERE run_id=? AND question_id=?',(run_id,question_id)).fetchone()
    if raw is None:raise ValueError('Saved case not found')
    case=json.loads(raw[0]);trace=case['programmatic_metrics']['retrieval_trace'];chunks,fingerprint=_current_corpus(trace)
    if not fingerprint:raise ValueError('Canonical Corpus identity unverified')
    # Selection sees only the original query and saved Candidate bodies.
    pool=trace['candidates'];retriever=VectorRetriever(SimpleNamespace(chunks=lambda:[{**h,'chunk_text':h['content']} for h in pool]))
    scores=retriever._bm25(case['question']);selected=sorted(pool,key=lambda h:(-scores[h['chunk_id']],h['chunk_id']))
    parents={x['canonical_parent']['chunk_id']:x['canonical_parent'] for x in chunks if x.get('canonical_parent')}
    # Held-out evaluation occurs after selection; these requirements are never search inputs.
    view=diagnostic_view(case);missing=[q for f in view['evidence_checks'] if f.get('technical_root')=='Ranking' for q in f.get('reference_support',[])]
    preserve=[q for check in case['judge_result']['checks'] if check['met'] for q in check['support']]
    if not missing:raise ValueError('No verified missing Ranking requirements')
    result={'kind':'offline_query_only_BM25_counterfactual_NOT_online_strategy','run_id':run_id,'question_id':question_id,'question':case['question'],'selected_rank':[h['chunk_id'] for h in selected],'trials':[]}
    for top_k in [4,6]:
        final=expand_parents(selected,list(parents.values()),top_k) if trace.get('parent_expand') else selected[:top_k]
        result['trials'].append({'top_k':top_k,'restore_missing_norm':all(quote_present(q,final,display=True) for q in missing),'preserve_met_facts':all(quote_present(q,final,display=True) for q in preserve),'final_ids':[h['chunk_id'] for h in final]})
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--question',required=True);parser.add_argument('--output');args=parser.parse_args()
    text=json.dumps(probe(args.run,args.question),ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(text+'\n')
    print(text)
