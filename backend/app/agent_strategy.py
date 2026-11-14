"""031d strategy contract and saved-result round retrospectives."""
import json
from collections import defaultdict

from .agent_inputs import new_failure_ids
from .paid_run import provider_task
from .telemetry import collect_usage, cost_fields


def bad_case_groups(cases):
    groups = defaultdict(list)
    for case in cases:
        if case.get('passed') is not False:
            continue
        from .diagnostics import diagnostic_view
        view = diagnostic_view(case)
        groups[(view.get('diagnosis_category') or '未知', view.get('subfeature') or '未知')].append(case['question_id'])
    return [{'layer':layer, 'subtype':subtype, 'question_ids':sorted(ids), 'count':len(ids)}
            for (layer, subtype), ids in sorted(groups.items())]


def validate_strategy(response, prior, audit, targets):
    review = response.get('prior_round_review')
    if not isinstance(review, dict) or not isinstance(review.get('summary'), str) or not review['summary'].strip():
        raise ValueError('前几轮总结必须有summary，第1轮写无')
    if not prior and review['summary'] != '无':
        raise ValueError('第1轮前几轮总结必须写无')
    for plan in review.get('plans', []):
        previous = next(c for c in prior if c['id'] == plan['candidate_id'])
        if len(previous.get('reasoning', {}).get('changed_parameters_vs_baseline', previous.get('reasoning', {}).get('changed_parameters', {}))) > 1:
            if any(not isinstance(plan.get(k), str) or not plan[k].strip() for k in ('most_likely_parameter', 'attribution_reason')):
                raise ValueError('多参数复盘须说明无法单独确定、最可能参数及理由')
    summary = response.get('bad_case_summary')
    if (not isinstance(summary, dict) or summary.get('groups') != audit['bad_case_groups']
            or not isinstance(summary.get('focus'), str) or not summary['focus'].strip()):
        raise ValueError('Bad Case总结必须按保存事实逐层/细分类型统计并指出最集中问题；groups须与输入一致')
    conclusions = summary.get('conclusions')
    if not isinstance(conclusions, list) or not conclusions or any(not isinstance(c, dict) or not c.get('id') or not isinstance(c.get('conclusion'), str) or not c['conclusion'].strip() for c in conclusions):
        raise ValueError('Bad Case总结缺少可引用结论')
    ids = {c['id'] for c in conclusions}
    if len(ids) != len(conclusions):
        raise ValueError('Bad Case结论ID重复')
    for candidate in response['candidates']:
        if not isinstance(candidate.get('adjustments'), list) or not candidate['adjustments'] or not isinstance(candidate.get('risks'), list) or not candidate['risks']:
            raise ValueError('Candidate须由Agent明确写出参数调整、预期题号和风险，不能自动补写')
        refs = candidate.get('bad_case_conclusion_ids')
        predicted = candidate.get('predicted_fixed_question_ids')
        if not isinstance(refs, list) or not refs or any(r not in ids for r in refs):
            raise ValueError('每个Candidate必须引用Bad Case总结结论')
        if not isinstance(predicted, list) or not predicted or any(not isinstance(q, str) or q not in targets for q in predicted) or len(set(predicted)) != len(predicted):
            raise ValueError('每个Candidate必须写预计修好题号predicted_fixed_question_ids，引用当前保存题号')


def validate_round_conclusion(review, candidates):
    if not isinstance(review, dict) or not isinstance(review.get('plans'), list):
        raise ValueError('本轮结论必须包含plans')
    plans = review['plans']
    if len(plans) != len(candidates) or {p.get('candidate_id') for p in plans if isinstance(p, dict)} != {c['id'] for c in candidates}:
        raise ValueError('本轮结论必须逐一覆盖已跑过的Candidate')
    for plan in plans:
        candidate = next(c for c in candidates if c['id'] == plan['candidate_id'])
        result = candidate['result']
        fixed = set(result.get('all_fixed_question_ids', []))
        broken = set(new_failure_ids(result))
        predicted = set(candidate['reasoning'].get('predicted_fixed_question_ids', []))
        if (set(plan.get('fixed_question_ids', [])) != fixed or set(plan.get('new_failure_question_ids', [])) != broken
                or set(plan.get('matched_question_ids', [])) != fixed & predicted
                or type(plan.get('prediction_match_count')) is not int or plan['prediction_match_count'] != len(fixed & predicted)):
            raise ValueError('本轮结论修好/弄坏/预测吻合题号和数量必须与保存结果一致')
        if any(not isinstance(plan.get(k), str) or not plan[k].strip() for k in ('unmatched_reason','parameter_assessment','evidence_reason','conclusion')):
            raise ValueError('本轮结论缺少预测不符原因、参数有效/有害判断、检索证据或结论')
    if not isinstance(review.get('lessons'), list) or not review['lessons'] or any(not isinstance(s, str) or not s.strip() for s in review['lessons']):
        raise ValueError('本轮结论缺少带入下一轮的经验lessons')
    return review


def _save(store, experiment_id, number, saved):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        state = json.loads(db.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()[0])
        state.setdefault('round_conclusions', {})[str(number)] = saved
        db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(state, ensure_ascii=False), experiment_id))


@provider_task('agent')
def conclude_round(store, runtime, experiment_id):
    experiment = store.experiment(experiment_id, light=True)
    if experiment['result'].get('strategy_contract') not in {'agent-strategy-3','agent-strategy-4'}:
        return
    abc = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A','B','C'}]
    number = max((c['reasoning'].get('round', 1) for c in abc), default=0)
    current = [c for c in abc if c['reasoning'].get('round', 1) == number]
    if not current or any(c['status'] not in {'evaluated','skipped'} for c in current):
        return
    saved = experiment['result'].get('round_conclusions', {}).get(str(number), {'status':'pending', 'attempts':[]})
    if saved['status'] == 'saved':
        return saved
    evaluated = [c for c in current if c['status'] == 'evaluated']
    from .optimization import build_agent_prompt
    baseline = store.evaluation_run(experiment['baseline_run_id'])
    _, facts = build_agent_prompt([], baseline['config'], evaluated, [], list('ABC'),
        baseline_cases=store.evaluation_case_results(baseline['id']),
        candidate_cases={c['id']:store.evaluation_case_results(c['result'].get('evaluation_run_id')) if c['result'].get('evaluation_run_id') else [] for c in evaluated},
        golden_questions=json.loads(baseline['dataset_snapshot_json']).get('questions', []))
    prompt = {'round':number, 'prior_sandbox_results':facts['prior_sandbox_results'],
              'predictions':{c['id']:c['reasoning'].get('predicted_fixed_question_ids', []) for c in evaluated},
              'skipped_candidates':[c['id'] for c in current if c['status']=='skipped'],
              'previous_round_conclusions':experiment['result'].get('round_conclusions', {})}
    system = ('你是RAG优化Agent。只读本实验保存事实，撰写本轮结论，输出JSON。不得编造检索证据或单参数因果关系，记录缺失写未知。'
              'plans逐一覆盖已跑过的Candidate（跳过的不算已跑过）：candidate_id,fixed_question_ids,new_failure_question_ids均采用正式题号；'
              'matched_question_ids是实际修好与predictions交集，prediction_match_count为交集数量；unmatched_reason解释预测不符原因；'
              'parameter_assessment写哪些参数有效/有害/待验证；evidence_reason说明检索位置或耗时依据，多参数写无法单独确定及最可能参数和理由；'
              'conclusion总结有效/有害/待验证；lessons为非空字符串数组，写带入下一轮的经验。格式{"plans":[],"lessons":[]}。')
    from .optimization_cycle import check_cycle_stop
    from .paid_schedule import wait_for_off_peak
    for index in range(4):
        check_cycle_stop(store, experiment_id)
        if len(saved['attempts']) <= index:
            saved['attempts'].append({})
        attempt = saved['attempts'][index]
        if 'raw' not in attempt:
            wait_for_off_peak(store, 'cycle:'+experiment_id, lambda pause:None, lambda:check_cycle_stop(store,experiment_id))
            from .evaluation_stage import _request_checkpoint
            token = _request_checkpoint.set((attempt.setdefault('request_checkpoint', {'attempts':[]}), 'agent', experiment_id,
                lambda *_args, **_kw:_save(store,experiment_id,number,saved), lambda:check_cycle_stop(store,experiment_id)))
            try:
                with collect_usage() as usage:
                    attempt['raw'] = runtime.provider.complete(system, json.dumps({**prompt, 'validation_errors':[a['error'] for a in saved['attempts'] if a.get('error')]}, ensure_ascii=False), json_mode=True)
                attempt['token_usage'] = usage
            finally:
                _request_checkpoint.reset(token)
                _save(store, experiment_id, number, saved)
        try:
            review = validate_round_conclusion(json.loads(attempt['raw']), evaluated)
            saved.update(status='saved', review=review)
            saved.update(cost_fields(getattr(getattr(runtime.provider,'settings',None),'model',None), [u for a in saved['attempts'] for u in a.get('token_usage', [])]))
            _save(store, experiment_id, number, saved)
            return saved
        except (ValueError, TypeError, KeyError) as error:
            attempt['error'] = str(error)
            _save(store, experiment_id, number, saved)
    raise ValueError('本轮结论连续校验拒绝：'+saved['attempts'][-1]['error'])


def validate_d_mode(suggestion, winner, history):
    mode = suggestion.get('combination_mode')
    if mode not in {'partial_fusion','winner_plus_verified'} or not isinstance(suggestion.get('mode_reason'), str) or not suggestion['mode_reason'].strip():
        raise ValueError('D须选择部分融合或Winner加有效参数，并说明原因')
    if suggestion.get('should_generate_d') is not True:
        return
    changes = suggestion.get('changes', [])
    selected = {winner['id']} | {cid for c in changes for cid in c.get('source_candidates', [])}
    qualified = {c['id'] for c in history if c['result'].get('qualification', {}).get('qualified') is True}
    if mode == 'partial_fusion' and (len(selected & qualified) < 2 or not selected <= qualified):
        raise ValueError('部分融合须引用两个以上合格方案的有效且不冲突参数')
    if any(c.get('source_type') not in {'verified','partial','已验证','部分取用'} for c in changes):
        raise ValueError('本次D只取已验证有效参数，不能新增未验证取值')
