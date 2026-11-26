"""Generation-only trials and their experiment-local mechanism evidence."""

import json

from . import rules, verdict
from .judge_replay import resolve_question_ids

SOURCE = '生成诊断'


def _experiment_state(connection, experiment_id):
    row = connection.execute('SELECT baseline_run_id,result_json FROM experiments WHERE id=?',
                             (experiment_id,)).fetchone()
    state = json.loads(row['result_json']) if row else {}
    if not verdict.current(state) or 'parameter_effect_ledger' not in state:
        raise ValueError('生成诊断需要使用当前规则和参数效果账本的实验')
    verdict.require_empty_history(state['parameter_effect_ledger'])
    return row['baseline_run_id'], state


def run_probe(store, evaluator, experiment_id, base_run_id, changes_list, question_ids, repetitions=3, base_key='Baseline'):
    """Run independent samples on the saved Final and publish evidence after each group."""
    allowed = {'generation_thinking': rules.AGENT['thinking_values'],
               'prompt_strategy': rules.PIPELINE_VALUES['prompt_strategy']}
    if not changes_list or any(not isinstance(changes, dict) or not changes or any(
            key not in allowed or value not in allowed[key] for key, value in changes.items())
            for changes in changes_list):
        raise ValueError('生成诊断只允许改 generation_thinking 或 prompt_strategy，且必须使用允许值')
    with store.connection() as connection:
        baseline_run_id, _ = _experiment_state(connection, experiment_id)
        if base_key == 'Baseline':
            matches = base_run_id == baseline_run_id
        else:
            row = connection.execute(
                "SELECT 1 FROM candidate_configs WHERE id=? AND experiment_id=? AND status='evaluated' "
                "AND json_extract(result_json,'$.evaluation_run_id')=?",
                (base_key, experiment_id, base_run_id)).fetchone()
            matches = row is not None
    if not matches:
        raise ValueError('诊断运行与本实验指定底座不匹配')

    base = store.evaluation_run(base_run_id)
    if not base or base['status'] != 'completed':
        raise ValueError('生成诊断需要已完成的底座运行')
    if not question_ids:
        raise ValueError('至少指定一道题')
    selected = resolve_question_ids(json.loads(base['dataset_snapshot_json']), question_ids)
    before = verdict.records(store, base_run_id)
    if any(q not in before or type(before[q]['final_passed']) is not bool for q in selected):
        raise ValueError('诊断题缺少底座最终判定')

    diagnostics = []
    for changes in changes_list:
        result = evaluator.diagnostic_retest(base_run_id, selected, repetitions=repetitions, config_override=changes)
        result.update(experiment_id=experiment_id, base_id=base_key, changes=changes,
                      config={**base['config'], **changes})
        entries = []
        for number, question in enumerate(result['questions'], 1):
            question_id = question['question_id']
            status = '未知'
            if not question['unknown']:
                after = not question['risk'] and question['passed'] > repetitions // 2
                status = ('无效' if after == before[question_id]['final_passed'] else '修好' if after else '弄坏')
            entries.append({
                'candidate_id': f"PROBE-{result['id']}-{number}", 'candidate_run_id': result['id'],
                'base_id': base_key, 'question_id': question_id, 'changes': changes, 'status': status,
                'final_added': None, 'final_lost': None, 'source': SOURCE,
                'confidence': f'生成诊断，{repetitions} 份多数，未经全量 Sandbox',
            })
        with store.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            _, state = _experiment_state(connection, experiment_id)
            written = connection.execute('INSERT INTO job_checkpoints VALUES (?,?,?) ON CONFLICT(run_id,question_id) DO NOTHING',
                                         (result['id'], 'generation_probe', json.dumps(result, ensure_ascii=False)))
            if written.rowcount:
                state['parameter_effect_ledger']['current'].extend(entries)
                connection.execute('UPDATE experiments SET result_json=? WHERE id=?',
                                   (json.dumps(state, ensure_ascii=False), experiment_id))
        diagnostics.append(result)
    return diagnostics


def winner_probe_evidence(ledger, winner_id, remaining_failures):
    remaining = {item['question_id'] for item in remaining_failures}
    return [row for row in ledger if row['source'] == SOURCE and row['base_id'] == winner_id
            and row['question_id'] in remaining and row['status'] == '修好']
