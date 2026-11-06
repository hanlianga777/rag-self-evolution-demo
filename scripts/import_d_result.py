#!/usr/bin/env python3
"""Import one completed same-configuration D result; no model or evaluation execution."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path

from internal_recheck import ROOT, ReadOnlyStore, digest, index_state, now
from app.governance import GovernanceStore, _json
from app.evaluation import EvaluationRunner
from app.composite import pipeline_config


class TransactionStore(GovernanceStore):
    """Keep the existing candidate/recommendation writers in the import transaction."""
    def __init__(self, database_path, connection):
        super().__init__(database_path, migrate=False)
        self.db = connection

    @contextmanager
    def connection(self):
        yield self.db


def import_saved_d(store, source, run_id, candidate_id, saved_index, current_index):
    candidate=store.candidate(candidate_id)
    if not candidate or candidate['reasoning'].get('candidate_label')!='D':
        raise ValueError('目标必须是已有 D 候选')
    run=source.evaluation_run(run_id)
    old_id=candidate['result'].get('evaluation_run_id')
    audit=candidate['result'].get('_evaluation_audit',{})
    replaced_id=audit.get('superseded_evaluations',[old_id])[0]
    old=store.evaluation_run(replaced_id)
    if not run or not old or run['status']!='completed' or not run['result'].get('evaluation_complete'):
        raise ValueError('运行必须已完整结束')
    strip=lambda config:{k:v for k,v in config.items() if k not in {'candidate_id','run_target'}}
    if digest(strip(run['config']))!=digest(strip(old['config'])) or digest(pipeline_config(run['config']))!=digest(pipeline_config(candidate['config'])):
        raise ValueError('业务配置不一致，拒绝导入')
    if not saved_index or digest(saved_index)!=digest(current_index):
        raise ValueError('索引清单哈希不一致，拒绝导入')
    for key in ('dataset_version_id','dataset_snapshot_json','judge_json'):
        if digest(json.loads(run[key]) if key.endswith('_json') else run[key])!=digest(json.loads(old[key]) if key.endswith('_json') else old[key]):
            raise ValueError('Golden或评分配置不一致，拒绝导入')
    cases=source.evaluation_case_results(run_id)
    snapshot=json.loads(run['dataset_snapshot_json'])
    expected=set(snapshot['question_ids'])
    if len(cases)!=len(expected) or {c['question_id'] for c in cases}!=expected or any(type(c.get('passed')) is not bool for c in cases):
        raise ValueError('逐题结果不完整，拒绝导入')
    with source.connection() as db:
        raw=dict(db.execute('select * from evaluation_runs where id=?',(run_id,)).fetchone())
        rows={table:[dict(r) for r in db.execute('select * from '+table+' where run_id=?',(run_id,))]
              for table in ('evaluation_case_results','evaluation_checkpoints','job_checkpoints')}
    if len(rows['evaluation_checkpoints'])!=len(expected):
        raise ValueError('检查点不完整，拒绝导入')
    metadata=audit or {'imported_from':'internal_trial','source_database':str(source.database_path.resolve()),
        'original_candidate_id':run['config'].get('candidate_id'),'imported_at':now(),
        'superseded_evaluations':[old_id], 'original_sandbox_attempts':candidate['reasoning'].get('sandbox_attempts',[]),
        'index_manifest_sha256':digest(saved_index)}
    config={**run['config'],'candidate_id':candidate_id,'run_target':'sandbox_candidate'}
    raw['config_json']=_json(config)
    raw['result_json']=_json({**json.loads(raw['result_json']),'_evaluation_audit':metadata})
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("select 1 from evaluation_runs where status in ('queued','running')").fetchone():
            raise ValueError('存在活动评测，拒绝导入')
        current=store.candidate(candidate_id)
        if current!=candidate:raise ValueError('D候选已变化，拒绝导入')
        existing=db.execute('select * from evaluation_runs where id=?',(run_id,)).fetchone()
        if existing:
            if dict(existing)!=raw:raise ValueError('运行编号冲突，拒绝覆盖')
        else:
            db.execute('insert into evaluation_runs ('+','.join(raw)+') values ('+','.join('?' for _ in raw)+')',tuple(raw.values()))
            for table,items in rows.items():
                for row in items:
                    if table=='evaluation_case_results':row.pop('id')
                    db.execute('insert into '+table+' ('+','.join(row)+') values ('+','.join('?' for _ in row)+')',tuple(row.values()))
        transactional=TransactionStore(store.database_path,db)
        baseline=transactional.evaluation_run(transactional.experiment(candidate['experiment_id'])['baseline_run_id'])
        # All comparisons read the destination's frozen Baseline and Winner.
        result=EvaluationRunner(transactional,None).finalize_saved_candidate(transactional.evaluation_run(run_id),candidate,baseline)
        reasoning={**candidate['reasoning']}
        if 'sandbox_attempts' in reasoning:
            reasoning['sandbox_attempts']=[{**attempt,'evaluation_run_id':run_id,'started_at':run['created_at']} if attempt.get('evaluation_run_id') in {replaced_id,run_id} else attempt for attempt in reasoning['sandbox_attempts']]
            db.execute('update candidate_configs set reasoning_json=? where id=?',(_json(reasoning),candidate_id))
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=ROOT/'backend/data/demo.db')
    parser.add_argument('--source',type=Path,default=ROOT/'output/task021c2/internal.db')
    parser.add_argument('--state',type=Path,default=ROOT/'output/task021c2/state.json')
    parser.add_argument('--run-id',default='EVAL-20261106102815663551')
    parser.add_argument('--candidate-id',default='EXP-20261105143048349606-D')
    args=parser.parse_args()
    source=ReadOnlyStore(args.source,migrate=False)
    job=next(j for j in json.loads(args.state.read_text())['jobs'] if j['run_id']==args.run_id)
    saved={k:job['index'][k] for k in ('identity','files')}
    current=index_state(source.evaluation_run(args.run_id)['config'])
    current={k:current[k] for k in ('identity','files')}
    result=import_saved_d(GovernanceStore(args.database,migrate=False),source,args.run_id,args.candidate_id,saved,current)
    print(json.dumps({'candidate_id':result['id'],'evaluation_run_id':result['result']['evaluation_run_id'],
        'recommendation':result['recommendation']['recommended_candidate'],'winner_comparison':result['result']['winner_comparison']},ensure_ascii=False))


if __name__=='__main__':main()
