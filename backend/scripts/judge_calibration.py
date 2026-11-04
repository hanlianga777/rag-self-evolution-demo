"""Saved-answer Judge calibration. Dry by default; --apply explicitly starts judging.

PYTHONPATH=backend python backend/scripts/judge_calibration.py --baseline RUN \
    --judge-thinking low --output /tmp/judge-low.csv [--apply]
Results and resumable checkpoints are separate local files; formal rows stay intact.
"""
import argparse
from contextlib import closing
import csv
import json
import sqlite3
from pathlib import Path

from app.judge_replay import saved_case_execution, source_digest
from app.evaluation_contract import evaluation_identity
from app.providers import judge_thinking, thinking_config


def read_baseline(database, run_id):
    """No GovernanceStore initialization or migrations during a dry run."""
    from app.sqlite_support import open_database
    with closing(open_database(database, read_only=True)) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM evaluation_runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise ValueError('Baseline 不存在')
        source = dict(row)
        source.update(config=json.loads(row['config_json']), judge=json.loads(row['judge_json']),
                      result=json.loads(row['result_json']))
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'evaluation_checkpoints' in tables:
            checkpoints = {saved['question_id']: json.loads(saved['checkpoint_json']) for saved in db.execute(
                'SELECT question_id,checkpoint_json FROM evaluation_checkpoints WHERE run_id=?', (run_id,))}
            if checkpoints:
                source['result']['checkpoints'] = {**source['result'].get('checkpoints', {}), **checkpoints}
        if 'job_checkpoints' in tables:
            for saved in db.execute("SELECT question_id,checkpoint_json FROM job_checkpoints WHERE run_id=? AND question_id LIKE 'review:%'", (run_id,)):
                source['result'].setdefault('baseline_review', {}).setdefault('cases', {})[saved['question_id'].removeprefix('review:')] = json.loads(saved['checkpoint_json'])
        cases = [{'question_id': row['question_id'], **json.loads(row['result_json']), 'run_id': run_id}
                 for row in db.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=? ORDER BY id', (run_id,))]
    snapshot = json.loads(source['dataset_snapshot_json'])
    if (source['status'] != 'completed' or source['config'].get('run_target') != 'baseline'
            or source['result'].get('evaluation_complete') is not True
            or source['result'].get('technical_failed') != 0
            or len(cases) != len(snapshot['question_ids'])
            or {case['question_id'] for case in cases} != set(snapshot['question_ids'])
            or any(type(case.get('passed')) is not bool for case in cases)):
        raise ValueError('需要完整且无技术失败的 Baseline')
    return source, cases


def calibration_plan(source, cases, effort):
    with judge_thinking(effort):
        judge = {**source['judge'], 'judge_thinking': thinking_config('judge')}
    snapshot = json.loads(source['dataset_snapshot_json'])
    if judge.get('common_identity_version') != 'round0-common-1':
        raise ValueError('原 Baseline 缺少可核对的判分思考档位身份')
    if source['judge'].get('evaluation_identity') != evaluation_identity(snapshot, source['judge']):
        raise ValueError('原 Baseline 判分身份与保存内容不一致')
    judge['evaluation_identity'] = evaluation_identity(snapshot, judge)
    return {'source_run_id': source['id'], 'source_sha256': source_digest(source, cases),
            'source_evaluation_identity': source['judge'].get('evaluation_identity'),
            'new_evaluation_identity': judge['evaluation_identity'], 'judge': judge,
            'generation_calls': 0, 'planned_questions': len(cases)}


def comparison_rows(source, cases, checkpoints, effort):
    snapshot = json.loads(source['dataset_snapshot_json'])
    saved = {case['question_id']: case for case in cases}
    rows = []
    labels = {'safety_critical': '安全关键题', 'prompt_injection': '提示注入题'}
    for index, item in enumerate(snapshot['questions'], 1):
        key = item['id']
        old = saved[key]
        checkpoint = checkpoints.get(key, {})
        new = checkpoint.get('scored_result', {})
        valid = type(new.get('passed')) is bool
        subtype = item.get('negative_subtype')
        rows.append({'题号': item.get('coverage_slot') or f'Q{index:02d}', '原始题号': key,
                     '问题': item['question'], '重点标记': labels.get(subtype, '负向题' if item.get('test_category') == 'negative' else ''),
                     '负向子类型': subtype or '', '原判分档位': source['judge'].get('judge_thinking', {}).get('reasoning_effort', '未知'),
                     '新判分档位': effort, '原判分': '对' if old['passed'] else '错',
                     '新判分': ('对' if new['passed'] else '错') if valid else '未知',
                     '是否一致': ('是' if old['passed'] == new['passed'] else '否') if valid else '未知',
                     '技术状态': '完成' if valid else checkpoint.get('technical_error', '未运行')})
    return rows


def run_calibration(runner, source, cases, effort, state, save):
    """Judge saved executions only. No answer(), retrieval(), or formal writes."""
    from app.evaluation_stage import perform_stage, correction_for
    from app.paid_run import accounting_only, execution_limits
    from app.providers import permanent_provider_error
    from app.corpus import current_manifest, manifest_identity
    from app.evaluation_contract import policy_current
    snapshot = json.loads(source['dataset_snapshot_json'])
    plan = calibration_plan(source, cases, effort)
    if state.get('plan') != plan:
        raise ValueError('校准源数据或目标判分身份发生变化')
    if (not policy_current(plan['judge'])
            or snapshot.get('corpus_fingerprint') != manifest_identity(current_manifest())):
        raise ValueError('Baseline 冻结身份与当前合同或语料不一致')
    items = {item['id']: item for item in runner.snapshot_items(snapshot)}
    with judge_thinking(effort), accounting_only(), execution_limits(plan['judge'].get('execution_snapshot', {}).get('request_limits')):
        runner._require_generation_contract(plan['judge'])
        for case in cases:
            key = case['question_id']
            checkpoint = state['cases'].setdefault(key, {'attempts': []})
            if 'scored_result' in checkpoint:
                continue
            from app.paid_schedule import wait_for_off_peak
            def price_state(pause):
                state.setdefault('_job', {})['price_pause'] = pause
                save()
            wait_for_off_peak(runner.store, 'calibration:' + source['id'] + ':' + effort, price_state)
            execution = saved_case_execution(case)
            if (not isinstance(execution['answer'], str) or not execution['answer'].strip()
                    or not isinstance(execution.get('retrieval_trace', {}).get('final'), list)):
                raise ValueError(f'{key} 缺少已保存的完整回答或最终内容')
            stage_id = 'judge-calibration:' + plan['new_evaluation_identity'] + ':' + key
            try:
                checkpoint['scored_result'] = perform_stage(checkpoint, 'judge',
                    lambda: runner.score_execution(items[key], execution, judge_correction=correction_for(checkpoint, stage_id)),
                    stage_id, automatic=False, check_stop=lambda: None, on_state=save)
                checkpoint.pop('technical_error', None)
            except Exception as error:
                checkpoint['technical_error'] = type(error).__name__ + ': ' + str(error)
                save()
                if permanent_provider_error(error):
                    raise
            save()
    state['complete'] = all(type(state['cases'].get(case['question_id'], {}).get('scored_result', {}).get('passed')) is bool for case in cases)
    save()
    return state


def calibrated_cases(source, cases, state, effort):
    """Validate saved calibration scores without replaying a paid request."""
    expected = calibration_plan(source, cases, effort)
    # Concurrent follow-up reviews append metadata to the source summary only.
    if (state.get('complete') is not True
            or any(state.get('plan', {}).get(k) != v for k, v in expected.items() if k != 'source_sha256')
            or set(state.get('cases', {})) != {c['question_id'] for c in cases}):
        raise ValueError('校准未完成或源题集、判分身份不一致')
    scored = []
    for case in cases:
        checkpoint = state['cases'][case['question_id']]
        result = checkpoint.get('scored_result', {})
        if (checkpoint.get('technical_error') or type(result.get('passed')) is not bool
                or saved_case_execution(result) != saved_case_execution(case)):
            raise ValueError('校准判分缺失或保存的回答、检索记录已变化：' + case['question_id'])
        scored.append({'question_id': case['question_id'], **result})
    return scored


def import_calibration(store, source_id, state, effort='low'):
    """Persist a complete Baseline using normal case and summary writers; no RPCs."""
    from app.evaluation import summarize_evaluation_cases
    from app.evaluation_stage import checkpoint_usage
    from app.telemetry import cost_fields
    from app.paid_run import unsettled_usage
    source, cases = read_baseline(store.database_path, source_id)
    scored = calibrated_cases(source, cases, state, effort)
    lineage = {'source_run_id': source_id, 'generation_thinking': source['config'].get('generation_thinking'),
               'judge_thinking': effort, 'judge_source': '010a 校准',
               'calibration_source_sha256': state['plan']['source_sha256'],
               'source_sha256_at_import': source_digest(source, cases),
               'timing_provenance': '回答耗时、TTFT、检索记录沿用源 Baseline'}
    existing = next((r for r in store.evaluation_runs() if r['result'].get('calibration_import') == lineage), None)
    if existing and existing['status'] == 'completed':
        return existing
    run_id = existing['id'] if existing else store.create_evaluation_run(
        json.loads(source['dataset_snapshot_json']), source['config'], state['plan']['judge'])
    store.update_evaluation_progress(run_id, {'calibration_import': lineage})
    for case in scored:
        store.record_evaluation_case(run_id, case['question_id'], {k: v for k, v in case.items() if k != 'question_id'}, with_bad_case=True)
    events = [u for cp in state['cases'].values() for u in checkpoint_usage(cp)]
    result = {**summarize_evaluation_cases(scored), 'calibration_import': lineage,
              'evaluation_complete': True, 'technical_failed': 0, 'technical_error_count': 0,
              'technical_errors': [], 'attempted': len(scored), 'total': len(scored),
              'checkpoints': {k: {field: v for field, v in cp.items() if field != 'scored_result'} for k, cp in state['cases'].items()},
              'calibration_job': state.get('_job'), 'runtime_limits': source['result'].get('runtime_limits'),
              'request_accounting': {'provenance': '010a 校准已支付判分；本次导入无调用', 'call_events': len(events),
                                     'unknown_usage_events': sum(unsettled_usage(u) for u in events),
                                     'known_input_tokens': sum(u.get('prompt_tokens', 0) for u in events if type(u.get('prompt_tokens')) is int),
                                     'known_output_tokens': sum(u.get('completion_tokens', 0) for u in events if type(u.get('completion_tokens')) is int),
                                     **cost_fields(source['judge']['model'], events)}}
    return store.finish_evaluation_run(run_id, 'completed', result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--judge-thinking', required=True, choices=('low', 'high', 'max'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--apply', action='store_true', help='显式开始判分，会调用已配置的模型；默认仅预览')
    args = parser.parse_args(argv)
    if args.output.suffix.lower() != '.csv':
        parser.error('--output 必须是 .csv 文件')
    from app.config import load_values
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    source, cases = read_baseline(database, args.baseline)
    plan = calibration_plan(source, cases, args.judge_thinking)
    if not args.apply:
        return {**plan, 'dry_run': True, 'provider_calls': 0, 'output': str(args.output)}
    # Import the runtime only after the explicit execution flag.
    import os
    import fcntl
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store, ai_service
    from app.evaluation import EvaluationRunner
    if Path(store.database_path).resolve() != database.resolve():
        raise ValueError('已加载的数据库与指定数据库不一致')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    state_path = args.output.with_suffix('.json')
    with state_path.with_suffix('.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(state_path.read_text()) if state_path.exists() else {'plan': plan, 'cases': {}, 'complete': False}
        def save(*_args, **_kwargs):
            temporary = state_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
            temporary.replace(state_path)
            rows = comparison_rows(source, cases, state['cases'], args.judge_thinking)
            with args.output.open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        run_calibration(EvaluationRunner(store, ai_service), source, cases, args.judge_thinking, state, save)
    return {'complete': state['complete'], 'source_run_id': source['id'], 'output': str(args.output), 'state': str(state_path), 'generation_calls': 0}


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=2))
