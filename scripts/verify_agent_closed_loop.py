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
        from app.corpus import current_manifest
        from app.evidence_resolver import diagnostic_plan
        from app.optimization import OptimizationAgent
        source=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
        copy=sqlite3.connect(temporary+'/demo.db')
        source.backup(copy);source.close();copy.close()
        store=object.__new__(GovernanceStore);store.database_path=Path(temporary)/'demo.db'
        baseline=store.evaluation_run(run_id)
        if not baseline or baseline['status']!='completed':raise ValueError('requires actual completed Baseline')
        chunks,fingerprint=_current_corpus({'corpus_fingerprint':json.loads(baseline['dataset_snapshot_json'])['corpus_fingerprint']})
        if not chunks:raise ValueError('current Canonical required')
        stack.enter_context(patch('app.diagnostics._current_corpus',return_value=(chunks,fingerprint)))
        plan=diagnostic_plan(store,run_id)
        cases=[row for row in store.bad_case_rows() if row['run_id']==run_id]
        class OfflineStrategy:
            def complete(self,system,user,**kwargs):
                self.prompt=json.loads(user)
                return json.dumps({'candidates':[],'insufficient_evidence':'offline stub: no model claims or new answer; diagnosis and Sandbox pending'})
        provider=OfflineStrategy()
        result=OptimizationAgent(store,provider).generate(run_id)
        assert {r['question_id'] for r in cases}=={r['question_id'] for r in provider.prompt['diagnostic_tasks']}
        assert len(provider.prompt['bad_cases'])==len(cases)
        rows=[{'question_id':row['question_id'],'question':row['result']['question'],
            'diagnosis':diagnostic_view(row['result'],corpus_chunks=chunks,corpus_fingerprint=fingerprint)} for row in cases]
        output={'run_id':run_id,'kind':'offline_isolated_copy_NOT_real_agent_or_repair','provider_calls':0,'business_failures':len(cases),
            'failures_in_agent_input':len(provider.prompt['bad_cases']),'diagnostic_plan':plan,'cases':rows,
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
    print(json.dumps({key:result[key] for key in ['provider_calls','business_failures','failures_in_agent_input','real_verified_repairs','original_database_unchanged']},ensure_ascii=False))
