"""Copy a self-contained prefix of completed A/B/C rounds into a new experiment."""
import json
import re
from uuid import uuid4

from . import agent126c as policy, task_leases, verdict
from .agent126c_workflow import dump, sandbox_facts
from .evaluation_snapshot import shared_judge
from .request_reuse import request_identity

E8_ID = 'EXP-20261127161008706100'


def detach_recovery(result):
    """Keep historical recovery evidence without the old worker's authorization."""
    if auto := result.get('auto_recovery'):
        result['auto_recovery'] = {key: value for key, value in auto.items()
                                   if key not in {'ledger_identity', 'ledger_path', 'authorized', 'worker_token'}}
        result['auto_recovery']['enabled'] = False
    return result


def copy_rounds(store, db, experiment_id, baseline_id, result, source_id, count):
    source = db.execute('SELECT * FROM experiments WHERE id=?', (source_id,)).fetchone()
    source_result = json.loads(source['result_json']) if source else {}
    saved = source_result.get('strategy126c') or {}
    if (not source or source['baseline_run_id'] != baseline_id or not policy.enabled(source_result)
            or not saved.get('final') or task_leases.cycle_active(db, source_id, source_result.get('optimization_cycle') or {})):
        raise ValueError('只能继承已完成的 126c 或 127a 实验')
    baseline = store.require_current_baseline(baseline_id, db)
    snapshot = json.loads(baseline['dataset_snapshot_json'])
    question_ids = snapshot['question_ids']
    safety = {q['id'] for q in snapshot['questions']
              if q.get('negative_subtype') in {'safety_critical', 'prompt_injection'}}
    base_facts = sandbox_facts(store, baseline, question_ids, safety)
    facts = {baseline_id: base_facts}
    rows = db.execute('SELECT * FROM candidate_configs WHERE experiment_id=?', (source_id,)).fetchall()
    by_round = {}
    for row in rows:
        reasoning = json.loads(row['reasoning_json'])
        label, number = reasoning.get('candidate_label'), reasoning.get('round')
        if label in policy.LABELS and type(number) is int and 1 <= number <= count:
            entries = by_round.setdefault(number, {})
            if label in entries:
                raise ValueError('来源轮次含重复候选')
            entries[label] = (row, reasoning, json.loads(row['result_json']))
    if len(by_round) != count:
        raise ValueError('来源实验没有指定的完整轮次')

    state = {'rounds': {}, 'ledger': [], 'winner_id': None, 'branch_id': None,
             'streak': 0, 'd_attempts': [], 'layers_with_faults': []}
    identifiers = {}
    runs = {}
    copies = []
    for number in range(1, count + 1):
        original = saved.get('rounds', {}).get(str(number), {})
        original_review = original.get('review') or {}
        historical = {row['id']: row for row in original_review.get('outcomes', [])}
        entries = by_round[number]
        if set(entries) != set(policy.LABELS) or not original_review or not original.get('plan'):
            raise ValueError(f'第 {number} 轮须有 A/B/C 和保存复盘')
        previous_facts = facts.copy()
        old_winner = state['winner_id']
        outcomes = []
        for label in policy.LABELS:
            row, reasoning, candidate_result = entries[label]
            cid = row['id']
            parent = reasoning['parent_id']
            if parent not in previous_facts:
                raise ValueError(f'第 {number} 轮依赖被排除的父方案')
            if row['status'] != 'evaluated' or not candidate_result.get('evaluation_complete') or cid not in historical:
                raise ValueError(f'第 {number} 轮缺少 {label} 的最终判定或预测对账')
            current_run = candidate_result.get('evaluation_run_id')
            if not current_run:
                raise ValueError('继承轮次缺少 Sandbox 运行 ID')
            roots = [current_run]
            for attempt in reasoning.get('sandbox_attempts', ()):
                roots.extend([attempt.get('evaluation_run_id'), *attempt.get('resume_run_ids', ())])
            for root in roots:
                run_id, visited = root, set()
                while run_id:
                    if run_id in visited:
                        raise ValueError('Sandbox 续跑链存在循环')
                    if run_id in runs:
                        if json.loads(runs[run_id]['config_json']).get('candidate_id') != cid:
                            raise ValueError('Sandbox 续跑链引用了其他候选')
                        break
                    visited.add(run_id)
                    run = db.execute('SELECT * FROM evaluation_runs WHERE id=?', (run_id,)).fetchone()
                    if not run:
                        raise ValueError('继承轮次缺少 Sandbox 运行记录')
                    run_result = json.loads(run['result_json'])
                    config, judge = json.loads(run['config_json']), json.loads(run['judge_json'])
                    if (config.get('candidate_id') != cid or config.get('run_target') != 'sandbox_candidate'
                            or json.loads(run['dataset_snapshot_json']) != snapshot
                            or shared_judge(judge) != shared_judge(baseline['judge'])):
                        raise ValueError('继承轮次的 Sandbox 与冻结身份不匹配')
                    runs[run_id] = run
                    identifiers[run_id] = f'EVAL-{uuid4().int}'
                    if run_id == current_run:
                        if run['status'] != 'completed' or run_result.get('evaluation_complete') is not True:
                            raise ValueError('继承轮次缺少完整 Sandbox')
                        if policy.pipeline_config(config) != policy.pipeline_config(json.loads(row['config_json'])):
                            raise ValueError('候选与 Sandbox 参数不匹配')
                        facts[cid] = sandbox_facts(store, {'id': run_id, 'result': run_result}, question_ids, safety)
                    run_id = run_result.get('resume_source_id')
            identifiers[cid] = f'{experiment_id}-R{number:06d}-{label}'
            labels = policy.qualifications(facts[cid], base_facts, facts[parent], facts[old_winner or baseline_id])
            outcome = {**historical[cid], **facts[cid], 'id': cid, 'labels': labels,
                       'higher_score': len(facts[cid]['passed']) > len(facts[old_winner or baseline_id]['passed'])}
            outcomes.append(outcome)
            copies.append((row, reasoning, candidate_result, labels))

        state['ledger'].extend(outcomes)
        promotions = [row for row in outcomes if row['labels']['promoted']]
        chosen = next((row for row in promotions if row['id'] == original_review.get('winner_id')), None)
        if chosen is None and promotions:
            chosen = max(promotions, key=lambda row: len(facts[row['id']]['passed']))
        winner = chosen['id'] if chosen else old_winner
        for outcome in outcomes:
            outcome['labels']['promoted'] = outcome['id'] == winner
        branches = policy.branch_options(state['ledger'], winner, facts[winner or baseline_id])
        branch = original_review.get('branch_id')
        if not any(row['id'] == branch for row in branches):
            branch = None
        # The saved plan lists the inactive layers. Their complement is the original round's diagnosis.
        inactive = next((row['evidence']['inactive'] for row in original['plan']['signals'] if row['id'] == 'S10'), [])
        state.update(winner_id=winner, branch_id=branch, streak=0 if chosen else state['streak'] + 1,
                     layers_with_faults=sorted(set(state['layers_with_faults']) | (set(policy.LAYERS) - set(inactive))))
        review = {**original_review, 'outcomes': outcomes, 'winner_id': winner, 'branch_id': branch,
                  'plateau': not chosen, 'next': 'continue',
                  'conditions': {key: value for key, value in original_review.get('conditions', {}).items() if key != 'd'}}
        review['signals'] = [dict(row) for row in review['signals']]
        policy.round_actions(review['signals'])
        legal = {row['id']: row['legal_actions'] for row in review['signals']}
        review['actions'] = [
            {**row, 'action': 'record_tradeoff' if row['action'] == 'leave_for_d' else row['action']}
            for row in review['actions']
            if row['action'] == 'leave_for_d' or row['action'] in legal[row['signal']]]
        state['rounds'][str(number)] = {'plan': original['plan'], 'review': review,
                                       'recoveries': [item for item in original.get('recoveries', [])
                                                      if item['event']['candidate_id'] in historical
                                                      and item['event']['candidate_id'] in identifiers],
                                       'inherited_from': {'experiment_id': source_id, 'round': number,
                                                          'label': 'E8' if source_id == E8_ID else source_id}}

    # Remap identifiers including composite checkpoint keys and diagnostic IDs. The
    # frozen question set, Judge contract and original evidence remain intact.
    pattern = re.compile('|'.join(map(re.escape, sorted(identifiers, key=len, reverse=True))))

    def remap(value):
        if isinstance(value, dict):
            return {remap(key): remap(child) for key, child in value.items()}
        if isinstance(value, list):
            return [remap(child) for child in value]
        return pattern.sub(lambda match: identifiers[match[0]], value) if isinstance(value, str) else value

    def remapped_json(value):
        return dump(remap(json.loads(value)))

    cache_exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='model_request_reuse'").fetchone()
    for old_id, run in sorted(runs.items(), key=lambda item: (item[1]['created_at'], item[0])):
        new_id = identifiers[old_id]
        raw = dict(run)
        copied_result = detach_recovery(json.loads(run['result_json']))
        raw.update(id=new_id, config_json=remapped_json(run['config_json']), result_json=dump(remap(copied_result)))
        db.execute('''INSERT INTO evaluation_runs VALUES (:id,:status,:run_mode,:data_source,:dataset_version_id,
            :dataset_snapshot_json,:config_json,:judge_json,:result_json,:error_message,:created_at,:completed_at)''', raw)
        for table, column in (('job_checkpoints', 'checkpoint_json'),
                              ('evaluation_checkpoints', 'checkpoint_json'), ('evaluation_case_results', 'result_json')):
            records = db.execute(f'SELECT question_id,{column} FROM {table} WHERE run_id=?', (old_id,)).fetchall()
            db.executemany(f'INSERT INTO {table}(run_id,question_id,{column}) VALUES (?,?,?)',
                           ((new_id, remap(qid), remapped_json(payload)) for qid, payload in records))
        for row in db.execute('SELECT * FROM bad_cases WHERE run_id=?', (old_id,)).fetchall():
            db.execute('INSERT INTO bad_cases VALUES (?,?,?,?,?,?,?,?)',
                       (remap(row['id']), new_id, row['question_id'], row['category'], row['severity'],
                        row['status'], remapped_json(row['result_json']), row['created_at']))
        if cache_exists:
            config, judge = json.loads(run['config_json']), json.loads(run['judge_json'])
            old_identity = request_identity(snapshot, config, judge, source_id,
                                            cross_config=source_result['decision_contract_version'] == policy.FINAL_ONLY_VERSION)
            new_identity = request_identity(snapshot, config, judge, experiment_id, cross_config=True)
            records = db.execute('SELECT kind,request_hash,result_json FROM model_request_reuse WHERE origin=? AND identity=?',
                                 (old_id, old_identity)).fetchall()
            db.executemany('INSERT OR IGNORE INTO model_request_reuse VALUES (?,?,?,?,?)',
                           ((new_identity, kind, request_hash, new_id, remapped_json(payload))
                            for kind, request_hash, payload in records))

    for row, reasoning, candidate_result, labels in copies:
        cid = identifiers[row['id']]
        candidate_result['strategy126c_labels'] = labels
        number = reasoning['round']
        reasoning = {**remap(reasoning), 'inherited_round': state['rounds'][str(number)]['inherited_from']}
        db.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)',
                   (cid, experiment_id, row['status'], row['config_json'], dump(reasoning),
                    dump(remap(detach_recovery(candidate_result))), row['created_at']))
    result['strategy126c'] = state = remap(state)
    for number, series in state['rounds'].items():
        db.execute("INSERT INTO agent_traces(experiment_id,status,result_json,created_at) VALUES (?, 'completed', ?, ?)",
                   (experiment_id, dump({'round': int(number), 'decision_contract_version': policy.FINAL_ONLY_VERSION,
                                         **series}), source['created_at']))
    db.execute("UPDATE experiments SET status='generated',result_json=? WHERE id=?", (dump(result), experiment_id))
