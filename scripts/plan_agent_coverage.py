#!/usr/bin/env python3
"""Preview/apply same-round coverage with network disabled; never runs an evaluation."""
import argparse,json,os,socket,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))


def blocked(*args,**kwargs):raise RuntimeError('Coverage planning prohibits network / Provider calls')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('database','index','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--experiment',required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--binding');parser.add_argument('--backup',type=Path)
    args=parser.parse_args()
    os.environ.update(RAG_DEMO_DB_PATH=str(args.database.resolve()),RAG_DEMO_INDEX_DIR=str(args.index.resolve()),RAG_DEMO_ENV_PATH='/tmp/rag-coverage-no-env')
    with patch.object(socket.socket,'connect',blocked),patch.object(socket.socket,'connect_ex',blocked):
        from app.governance import GovernanceStore
        from app.agent_coverage import coverage_inputs,complete_coverage
        store=object.__new__(GovernanceStore);store.database_path=args.database.resolve()
        experiment,baseline,rows,base,result=coverage_inputs(store,args.experiment)
        store.require_current_baseline(baseline['id'])
        if args.apply:
            if not args.binding or not args.backup:parser.error('--apply requires --binding and --backup')
            complete_coverage(store,args.experiment,expected_binding=args.binding,backup_path=args.backup)
            experiment,baseline,rows,base,result=coverage_inputs(store,args.experiment)
        result['baseline_id']=baseline['id']
        result['evaluation_identity']=baseline['judge'].get('evaluation_identity')
        if result['status']!='incomplete':
            from types import SimpleNamespace
            from app.evaluation import EvaluationRunner
            runner=EvaluationRunner(store,SimpleNamespace(model=baseline['judge']['model']))
            result['sandbox_admission']=[]
            for candidate in experiment['candidates']:
                try:
                    approved,config,_,_=runner.candidate_inputs(candidate['id'])
                    check={'id':candidate['id'],'admitted':True,'snapshot_count':len(approved),'config':config}
                except ValueError as error:check={'id':candidate['id'],'admitted':False,'reason':str(error)}
                result['sandbox_admission'].append(check)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','covered_count','planned_count','total','binding','provider_calls')},ensure_ascii=False))
    for p in result['proposals']:print(p['id'],p['config_diff'],p['target_bad_cases'])
