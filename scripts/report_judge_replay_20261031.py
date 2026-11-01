#!/usr/bin/env python3
"""Read-only saved-answer Judge replay comparison. No Provider or evaluation writes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/judge_vnext_20261030'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def load_old_cases(database, audit):
    db = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        run = db.execute('SELECT * FROM evaluation_runs WHERE id=?', (audit['source_run_id'],)).fetchone()
        rows = list(db.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=? ORDER BY id', (audit['source_run_id'],)))
        if run is None or digest({'run':dict(run), 'cases':[(r['question_id'],r['result_json']) for r in rows]}) != audit['source_sha256']:
            raise ValueError('Historical source hash changed; use the exact audited source')
        return {r['question_id']:json.loads(r['result_json']) for r in rows}
    finally:
        db.close()


def indexed(rows):
    result = {row['question_id']:row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate question identity')
    return result


def completed_row(row, answer_sha, final_sha):
    judgment=row.get('judgment') or {}
    return (row.get('status')=='completed' and row.get('business_result') in {'PASS','FAIL'}
        and judgment.get('verdict')==row['business_result']
        and isinstance(judgment.get('atomic_results'),list) and bool(judgment['atomic_results'])
        and isinstance(judgment.get('checks'),list) and isinstance(judgment.get('issues'),list)
        and row.get('answer_sha256')==answer_sha and row.get('final_sha256')==final_sha)


def with_correction(audit, bundle, replay, directory, review_directory, authorization_path):
    files={}
    def load(path):
        raw=path.read_bytes();files[str(path.resolve())]=hashlib.sha256(raw).hexdigest()
        return json.loads(raw)
    plan=load(review_directory/'request_plan.json');fields=load(review_directory/'request_input.json')
    wire=load(review_directory/'request_wire_body.json');authorization=load(authorization_path)
    binding=plan['review_binding'];question_id=plan['question_id'];request=plan['request']
    if digest({k:v for k,v in plan.items() if k!='review_binding'})!=binding:
        raise ValueError('Correction review binding is invalid')
    if (plan.get('common50_binding')!=audit['binding'] or plan.get('target_snapshot_id')!=audit['target_snapshot_id']
        or plan.get('versions')!=audit['judge_versions'] or plan.get('judge_prompt_sha256')!=audit['judge_prompt_sha256']):
        raise ValueError('Correction differs from common Judge/Snapshot binding')
    required={'approved':True,'question_id':question_id,'additional_max_calls':1,
        'max_attempts_per_sample':1,'automatic_retries':0,'request_sha256':request['request_sha256'],'review_binding':binding,
        'common50_binding':audit['binding'],'target_snapshot_id':audit['target_snapshot_id']}
    if (authorization.get('approved') is not True or authorization.get('source') not in {'direct_user_instruction','direct_user_instruction_async_reply'}
        or any(authorization.get(k)!=v for k,v in required.items()) or not authorization.get('user_answer')):
        raise ValueError('Exact additional one-call user authorization required')
    for source in plan['source_files']:
        path=Path(source['path']);raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest();files[str(path.resolve())]=sha
        if sha!=source['sha256']:raise ValueError('Correction reviewed source hash changed')
    for name,sha in plan['artifact_file_sha256'].items():
        path=(review_directory/name).resolve()
        if not path.is_relative_to(review_directory.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('Correction request artifact hash changed')
        files[str(path)]=sha
    previous_traces=replay.get('correction_traces') or ([replay['correction_trace']] if replay.get('correction_trace') else [])
    if any(t['question_id']==question_id for t in previous_traces):
        raise ValueError('Duplicate correction for an already attempted extra-call question')
    original=indexed(replay['cases']).get(question_id)
    saved=indexed(bundle['cases']).get(question_id)
    common_request=next((r for r in audit['requests'] if r['question_id']==question_id),None)
    if not original or original.get('status')!='NOT_EVALUABLE' or original.get('business_result') is not None or not saved or not common_request:
        raise ValueError('Correction may supersede only the exact original NOT_EVALUABLE question')
    answer_sha=text_sha(saved['answer']);final_sha=digest(saved['retrieval_trace']['final'])
    if (original.get('answer_sha256')!=answer_sha or original.get('final_sha256')!=final_sha
        or fields.get('actual_answer')!=saved['answer'] or fields.get('final_context')!=saved['retrieval_trace']['final']
        or (fields.get('judge_correction') or {}).get('previous_response')!=(original.get('error') or {}).get('raw_response')
        or (fields.get('scoring_contract') or {}).get('compiled_contract_hash')!=common_request['compiled_contract_hash']
        or request.get('max_tokens')!=common_request['request']['max_tokens']
        or request.get('model')!=common_request['request']['model']
        or request.get('request_sha256')==common_request['request']['request_sha256']
        or json.loads(wire['messages'][1]['content'])!=fields
        or hashlib.sha256(json.dumps(wire).encode()).hexdigest()!=request['request_sha256']):
        raise ValueError('Correction changed original Answer/Final/contract/request provenance')
    original_inputs={}
    candidates={Path(source['path']) for source in plan['source_files'] if Path(source['path']).name=='ledger.json'}
    candidates.update(review_directory/name for name in plan['artifact_file_sha256'] if name.endswith('.json'))
    for path in candidates:
        value=load(path)
        calls=[value] if isinstance(value,dict) and isinstance(value.get('request_payload'),dict) else value.get('calls',[]) if isinstance(value,dict) and path.name=='ledger.json' else []
        for call in calls:
            if (call.get('usage') or {}).get('request_sha256')==common_request['request']['request_sha256']:
                payload=call['request_payload']
                if hashlib.sha256(json.dumps(payload).encode()).hexdigest()!=common_request['request']['request_sha256']:
                    raise ValueError('Bound original single-call wire hash differs')
                original_inputs[digest(payload)]=json.loads(payload['messages'][1]['content'])
    original_inputs=list(original_inputs.values())
    if len(original_inputs)!=1 or {k:v for k,v in fields.items() if k!='judge_correction'}!=original_inputs[0]:
        raise ValueError('Correction must keep the entire original Judge input except explicit technical feedback')
    recovered=load(directory/'replay.json');recovered_audit=load(directory/'audit.json');ledger=load(directory/'ledger.json')
    rows=recovered.get('cases') or [];calls=ledger.get('calls') or []
    if (recovered.get('binding')!=binding or recovered.get('common50_binding')!=audit['binding'] or ledger.get('identity')!=binding
        or recovered_audit.get('review_binding')!=binding or recovered_audit.get('common50_binding')!=audit['binding']
        or recovered_audit.get('question_id')!=question_id or recovered_audit.get('execute') is not True
        or recovered_audit.get('request')!=request or recovered.get('network_calls')!=1 or len(rows)!=1 or len(calls)!=1
        or rows[0].get('question_id')!=question_id or rows[0].get('status') not in {'completed','NOT_EVALUABLE'}):
        raise ValueError('Correction must be one explicit matching request and result')
    row,call=rows[0],calls[0];usage=call.get('usage') or {};payload=call.get('request_payload')
    if (row.get('answer_sha256')!=answer_sha or row.get('final_sha256')!=final_sha or payload!=wire
        or hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()!=call.get('request_sha256')
        or call.get('provider')!='DeepSeek' or call.get('model')!=request['model'] or call.get('task')!='judge'
        or call.get('max_tokens')!=request['max_tokens']):
        raise ValueError('Correction result/request source hash mismatch')
    settled=(call.get('status')=='ok' and usage.get('status')=='ok' and usage.get('provider')=='DeepSeek'
        and usage.get('requested_model')==request['model'] and usage.get('request_sha256')==request['request_sha256']
        and usage.get('request_execution_unknown') is not True
        and all(type(usage.get(k)) is int and usage[k]>=0 for k in ('prompt_tokens','completion_tokens')))
    if settled:
        raw_path=Path(call.get('raw_response_path') or '')
        raw_path=raw_path.resolve() if raw_path.is_absolute() else (ROOT/raw_path).resolve()
        if not raw_path.is_relative_to(directory.resolve()):raise ValueError('Correction raw response is outside its output directory')
        body=load(raw_path);raw=(row.get('judgment') or {}).get('raw_provider_response') if row['status']=='completed' else (row.get('error') or {}).get('raw_response')
        if ((body.get('choices') or [{}])[0].get('message',{}).get('content')!=raw
            or any((body.get('usage') or {}).get(k)!=usage[k] for k in ('prompt_tokens','completion_tokens'))):
            raise ValueError('Correction raw response or Usage differs from the recorded result')
    applied=settled and completed_row(row,answer_sha,final_sha)
    if row['status']=='completed' and not applied:raise ValueError('Incomplete or invalid correction cannot supply a business verdict')
    view=json.loads(json.dumps(replay))
    if applied:view['cases']=[row if r['question_id']==question_id else r for r in view['cases']]
    view['network_calls']=replay.get('network_calls',0)+1
    view['correction_trace']={'question_id':question_id,'applied':applied,'superseded_original':original,'correction_result':row,
        'original_request_sha256':common_request['request']['request_sha256'],'correction_request_sha256':request['request_sha256'],
        'common50_binding':audit['binding'],'review_binding':binding,'authorization':authorization,'file_sha256':files,
        'scope':'read_only_effective_view; original Replay/correction artifacts remain immutable'}
    view['correction_traces']=previous_traces+[view['correction_trace']]
    return view


def build_report(audit, bundle, snapshot, replay, old_cases):
    if replay.get('binding') != audit['binding']:
        raise ValueError('Replay binding differs from approved preflight')
    if (bundle['source_run_id'],bundle['source_sha256']) != (audit['source_run_id'],audit['source_sha256']):
        raise ValueError('Saved bundle source identity differs')
    if snapshot['id'] != audit['target_snapshot_id'] or snapshot['scoring_contract_manifest'] != audit['target_scoring_manifest']:
        raise ValueError('Frozen target snapshot/manifest differs')
    saved, audited, fresh = indexed(bundle['cases']), indexed(audit['cases']), indexed(replay['cases'])
    expected = set(snapshot['question_ids'])
    if set(saved) != expected or set(audited) != expected or set(old_cases) != expected or not set(fresh) <= expected:
        raise ValueError('Question coverage differs from frozen audited source')
    rows = []
    for question in snapshot['questions']:
        key = question['id']; execution = saved[key]; final = execution['retrieval_trace']['final']
        answer_sha, final_sha = text_sha(execution['answer']), digest(final)
        if answer_sha != audited[key]['answer_sha256'] or final_sha != audited[key]['stages']['final']['sha256']:
            raise ValueError('Original saved provenance mismatch: ' + key)
        old = old_cases[key]
        if 'model_answer' in old and old['model_answer'] != execution['answer']:
            raise ValueError('Historical answer differs from saved bundle: ' + key)
        outcome = old.get('evaluation_outcome') or {}
        old_verdict = outcome.get('verdict') if outcome.get('execution_complete') is True else None
        if old_verdict not in {'PASS','FAIL'}:
            old_verdict = 'NOT_EVALUABLE' if outcome else 'PASS' if old.get('passed') is True else 'FAIL' if old.get('passed') is False else 'NOT_EVALUABLE'
        new = fresh.get(key, {}); judgment = new.get('judgment') or {}
        valid = completed_row(new,answer_sha,final_sha)
        verdict = new['business_result'] if valid else 'NOT_EVALUABLE'
        comparison = ('UNCHANGED' if old_verdict == verdict else old_verdict + '→' + verdict) if valid and old_verdict in {'PASS','FAIL'} else 'NOT_COMPARABLE'
        rows.append({'question_id':key, 'coverage_slot':question.get('coverage_slot'), 'question':question['question'],
            'old_verdict':old_verdict, 'new_verdict':verdict, 'comparison':comparison,
            'new_execution_status':new.get('status','unrun'),
            'technical_error':new.get('error') or (None if valid else {'reason':'unrun_or_incomplete_or_inconsistent_replay_row'}),
            'judge_reason':judgment.get('reason') if valid else None,
            'new_atomic_results':judgment.get('atomic_results',[]) if valid else [],
            'new_checks':judgment.get('checks',[]) if valid else [], 'new_issues':judgment.get('issues',[]) if valid else [],
            'original_answer':execution['answer'], 'answer_sha256':answer_sha, 'final_sha256':final_sha,
            'actual_final':final, 'golden_norms':question.get('business_requirements',{}).get('sources',[]),
            'frozen_business_requirements':question.get('business_requirements',{})})
    counts = Counter(r['new_verdict'] for r in rows)
    return {'artifact_type':'readonly_judge_replay_comparison_not_formal_baseline', 'source_run_id':audit['source_run_id'],
        'target_snapshot_id':snapshot['id'], 'binding':audit['binding'], 'replay_status':replay.get('status'),
        'counts':{k:counts[k] for k in ('PASS','FAIL','NOT_EVALUABLE')},
        'effective_question_count':len(rows),'historical_judge_attempt_count':replay.get('network_calls',0),
        'correction_trace':replay.get('correction_trace'),
        'correction_traces':replay.get('correction_traces') or ([replay['correction_trace']] if replay.get('correction_trace') else []),
        'legacy_scores_used_as_truth':False, 'independent_rescoring_performed':False,
        'verdict_source':'completed formal Provider Judge rows with matching saved provenance; technical/unrun excluded',
        'generation_calls':0, 'network_calls':0, 'production_database_writes':0,
        'timing_provenance':audit.get('timing_provenance','historical_generation_only_not_new_v2_or_max_performance'),
        'cases':rows, 'flips':[r for r in rows if '→' in r['comparison']]}


def markdown(report):
    counts = report['counts']
    lines = ['# 历史答案 Judge-only Replay 比较', '',
        f"源Run：`{report['source_run_id']}`；新Snapshot：`{report['target_snapshot_id']}`。", '',
        f"新Judge有效完成：PASS {counts['PASS']} / FAIL {counts['FAIL']}；NOT_EVALUABLE {counts['NOT_EVALUABLE']}；裁决变化 {len(report['flips'])} 题。", '',
        '仅比较保存裁决，不把旧裁决视为真值。新裁决来自唯一正式Judge已完成且原答案/Final哈希匹配的Replay记录；本报告未独立重评分。技术失败、未运行及不一致记录均不计业务PASS/FAIL。', '',
        '旧答案保持原样；Generation为历史V1，不证明V2/Max性能。本报告不推断技术根因，不创建正式Baseline/Gate。Golden规范与实际Final分列，规范不能补作实际Final证据。', '',
        f"本报告覆盖{report['effective_question_count']}题，历史Judge尝试累计{report['historical_judge_attempt_count']}次；报告本身不调用Provider。", '',
        '| 题号 | 历史裁决 | 新裁决 | 比较 |', '|---|---|---|---|']
    lines.extend(f"| {r['coverage_slot'] or r['question_id']} | {r['old_verdict']} | {r['new_verdict']} | {r['comparison']} |" for r in report['cases'])
    for trace in report.get('correction_traces',[]):
        lines += ['', '显式额外纠正调用：'+trace['question_id']+'；已应用到只读LATEST视图：'+str(trace['applied'])+'。原NOT_EVALUABLE及原错误完整保留在comparison.json的correction_traces中。', '',
                  '原请求SHA：`'+trace['original_request_sha256']+'`；额外纠正请求SHA：`'+trace['correction_request_sha256']+'`。两者是不同调用，不把纠正伪装成原50题首次输出。']
    for row in report['flips']:
        lines += ['', f"## {row['coverage_slot'] or row['question_id']}：{row['comparison']}", '', row['question'], '',
                  '新Judge原理由：' + str(row['judge_reason']), '', '逐原子判断（原文）：', '']
        lines.extend('- ' + str(a.get('atomic_id')) + ' / ' + str(a.get('state')) + '：' + str(a.get('reason')) for a in row['new_atomic_results'])
        lines += ['', 'checks 与 issues（完整原字段）：', '', '```json', json.dumps({'checks':row['new_checks'],'issues':row['new_issues']},ensure_ascii=False,indent=2), '```', '',
                  '原答案：', '', row['original_answer'], '', '实际保存Final（全文与页码/Chunk）：', '']
        for entry in row['actual_final']:
            identity={k:entry.get(k) for k in ('chunk_id','parent_chunk_id','matched_child_ids','document','document_id','product','version','page_start','page_end','parent_page_start','parent_page_end') if entry.get(k) is not None}
            lines += ['- ' + json.dumps(identity,ensure_ascii=False), '', '```text',entry['content'],'```','']
        lines += ['Golden冻结规范（独立参考，不能补作Final）：', '', '```json',json.dumps(row['golden_norms'],ensure_ascii=False,indent=2),'```']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',type=Path,default=BASE/'historical_replay_frozen_preflight_20261031')
    parser.add_argument('--snapshot',type=Path,default=BASE/'golden_frozen_20261031/new-snapshot.json')
    parser.add_argument('--replay',type=Path,default=BASE/'historical_replay_real_20261031/replay.json')
    parser.add_argument('--database',type=Path,default=ROOT/'backend/data/demo.db')
    parser.add_argument('--correction-dir',type=Path,help='optional separately authorized one-call correction output')
    parser.add_argument('--correction-review-dir',type=Path)
    parser.add_argument('--correction-authorization',type=Path)
    parser.add_argument('--correction-set',nargs=3,action='append',type=Path,default=[],metavar=('OUTPUT','REVIEW','AUTH'),help='repeatable explicitly authorized correction set')
    parser.add_argument('--output',type=Path,required=True,help='new directory for comparison.json and comparison.md')
    args = parser.parse_args()
    input_hashes={}
    def load(path):
        raw=path.read_bytes();input_hashes[str(path)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
    audit=load(args.preflight/'audit.json');bundle=load(args.preflight/'saved_execution_bundle.json')
    snapshot=load(args.snapshot);replay=load(args.replay)
    correction_sets=[]
    if any((args.correction_dir,args.correction_review_dir,args.correction_authorization)):
        if not all((args.correction_dir,args.correction_review_dir,args.correction_authorization)):
            parser.error('legacy correction arguments require directory, review directory and authorization together')
        correction_sets.append((args.correction_dir,args.correction_review_dir,args.correction_authorization))
    for directory,review,authorization in correction_sets+args.correction_set:
        replay=with_correction(audit,bundle,replay,directory,review,authorization)
    report=build_report(audit,bundle,snapshot,replay,load_old_cases(args.database,audit))
    report['input_file_sha256']=input_hashes
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (args.output/'comparison.md').write_text(markdown(report))
    print(json.dumps({'output':str(args.output),'counts':report['counts'],'flips':len(report['flips']),'network_calls':0,'database_writes':0},ensure_ascii=False))


if __name__ == '__main__':
    main()
