"""Read-only OFFLINE historical shadow; never a Provider/Judge accuracy measurement."""
import collections,json,os,pathlib,shutil,sqlite3,sys,tempfile
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]

def verify():
    from app.safety_guard import check_safety,adjudicate,SAFETY_IDENTITY
    from verify_evaluation_vnext import digest
    fixture=json.loads((ROOT/'backend/tests/fixtures/rag_200_vnext_review.json').read_text())
    db=sqlite3.connect((ROOT/'backend/data/demo.db').as_uri()+'?mode=ro',uri=True);db.execute('pragma query_only=on');db.execute('begin')
    records=[];counts=collections.Counter();false_positive=[]
    for row in fixture['records']:
        c=json.loads(db.execute('select result_json from evaluation_case_results where run_id=? and question_id=?',(row['run_id'],row['question_id'])).fetchone()[0])
        snapshot=json.loads(db.execute('select dataset_snapshot_json from evaluation_runs where id=?',(row['run_id'],)).fetchone()[0]);item=next(x for x in snapshot['questions'] if x['id']==row['question_id'])
        final=c['programmatic_metrics']['retrieval_trace']['final'];assert digest(c['model_answer'])==row['answer_sha256'] and digest(final)==row['final_sha256']
        historical='PASS' if c['passed'] else 'FAIL';assert historical==row['historical']
        guard=check_safety(item['question'],c['model_answer'],final,constraints=item)
        decision=adjudicate({'verdict':historical},guard)
        counts[guard['status']]+=1
        if guard['status']=='confirmed_violation' and row['expected']=='PASS':false_positive.append([row['group'],row['question_number']])
        records.append({'run_id':row['run_id'],'question_id':row['question_id'],'group':row['group'],'number':row['question_number'],'independent_expected':row['expected'],'stored_historical_business_verdict':historical,'shadow_final_verdict':decision['verdict'],'safety_guard':guard,'risk_status':decision['risk_status'],'qualification_blocking':decision['qualification_blocking'],'safety_review_required':decision['safety_review_required']})
    db.close()
    return {'kind':'OFFLINE historical business-verdict + deterministic guard SHADOW; not new LLM output','versions':SAFETY_IDENTITY,'records':records,'summary':{'records':len(records),'statuses':dict(counts),'confirmed_on_independent_PASS_false_positive':false_positive,'confirmed_on_independent_FAIL':sum(r['safety_guard']['status']=='confirmed_violation' and r['independent_expected']=='FAIL' for r in records),'independent_FAIL_not_confirmed_by_this_limited_guard':sum(r['safety_guard']['status']!='confirmed_violation' and r['independent_expected']=='FAIL' for r in records),'inconclusive_rate':counts['inconclusive']/len(records),'review_required':sum(r['safety_review_required'] for r in records),'stored_historical_PASS':sum(r['stored_historical_business_verdict']=='PASS' for r in records),'shadow_final_PASS':sum(r['shadow_final_verdict']=='PASS' for r in records),'shadow_agreements_with_independent_expected':sum(r['shadow_final_verdict']==r['independent_expected'] for r in records),'q42_family':[{k:r[k] for k in ['group','independent_expected','shadow_final_verdict','risk_status']}|{'guard_status':r['safety_guard']['status']} for r in records if r['number']==42]},'provider_calls':0,'formal_database_writes':0}

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='rag-hybrid-offline-') as directory:
        p=pathlib.Path(directory);shutil.copytree(ROOT/'backend/documents',p/'documents');shutil.copytree(ROOT/'backend/data/index',p/'index');(p/'.env').write_text('')
        os.environ.update(RAG_DEMO_DB_PATH=str(p/'test.db'),RAG_DEMO_INDEX_DIR=str(p/'index'),RAG_DEMO_DOCUMENTS_DIR=str(p/'documents'),RAG_DEMO_UPLOADS_DIR=str(p/'uploads'),RAG_DEMO_ENV_PATH=str(p/'.env'),RAG_FORCE_MOCK='1',DEEPSEEK_API_KEY='',DASHSCOPE_API_KEY='',MINERU_API_KEY='')
        sys.path.insert(0,str(ROOT/'backend'))
        with patch('urllib.request.urlopen',side_effect=AssertionError('Hybrid offline verification forbids Provider')):result=verify()
        print(json.dumps(result,ensure_ascii=False,indent=2))
