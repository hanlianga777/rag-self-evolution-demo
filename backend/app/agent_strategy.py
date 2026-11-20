"""031d strategy contract and saved-result round retrospectives."""
import json
from collections import defaultdict

from . import rules
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


def predicted_ids(candidate):
    """A/B/C 的预测写在 predicted_fixed_question_ids；D 的预测写在每个改动的 target_question_ids。"""
    reasoning = candidate.get('reasoning', {})
    if reasoning.get('candidate_label') == 'D' and not reasoning.get('predicted_fixed_question_ids'):
        return sorted({q for row in reasoning.get('changes') or [] if isinstance(row, dict) for q in row.get('target_question_ids') or []})
    return list(reasoning.get('predicted_fixed_question_ids', []))


def winner_comparison(store, d, winner):
    """D 相对 Winner 的程序事实：只改了哪些参数、相对 Winner 修好/新错哪些题。"""
    def outcomes(candidate):
        run = candidate['result'].get('evaluation_run_id')
        return {c['question_id']: c.get('passed') for c in (store.evaluation_case_results(run) if run else [])}
    mine, theirs = outcomes(d), outcomes(winner)
    return {'winner_id': winner['id'],
            'changed_parameters_vs_winner': d['reasoning'].get('winner_config_diff', {}),
            'fixed_vs_winner': sorted(q for q, ok in mine.items() if ok is True and theirs.get(q) is False),
            'new_failures_vs_winner': sorted(q for q, ok in mine.items() if ok is False and theirs.get(q) is True)}


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
        predicted = set(predicted_ids(candidate))
        if (set(plan.get('fixed_question_ids', [])) != fixed or set(plan.get('new_failure_question_ids', [])) != broken
                or set(plan.get('matched_question_ids', [])) != fixed & predicted
                or type(plan.get('prediction_match_count')) is not int or plan['prediction_match_count'] != len(fixed & predicted)):
            raise ValueError('本轮结论修好/弄坏/预测吻合题号和数量必须与保存结果一致')
        # 预测与结果完全吻合、也没有弄坏题时，"预测不符原因"本来就无话可说，允许留空并记为吻合。
        if fixed == predicted and not broken and not (isinstance(plan.get('unmatched_reason'), str) and plan['unmatched_reason'].strip()):
            plan['unmatched_reason'] = '预测与结果一致，无不符'
        if isinstance(plan.get('parameter_assessment'), dict) and plan['parameter_assessment'] and all(
                isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in plan['parameter_assessment'].items()):
            values = {v.strip() for v in plan['parameter_assessment'].values()}
            # 逐题复盘只接受"有效/无效/不确定"；各参数判断一致时直接取这个值，不一致才拼成文字（会按原规则退回）。
            plan['parameter_assessment'] = values.pop() if len(values) == 1 else '；'.join(f'{k}：{v}' for k, v in plan['parameter_assessment'].items())
        names = {'unmatched_reason': '预测不符原因', 'parameter_assessment': '参数有效/有害判断', 'evidence_reason': '检索证据', 'conclusion': '结论'}
        missing = [names[k] for k in names if not isinstance(plan.get(k), str) or not plan[k].strip()]
        if missing:
            raise ValueError(f"本轮结论 {plan['candidate_id']} 缺少：{'、'.join(missing)}（字段 {', '.join(k for k in names if names[k] in missing)} 必须是非空文字）")
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
def conclude_round(store, runtime, experiment_id, *, final_d=False):
    """每轮 A/B/C 跑完后的 Agent 复盘；final_d=True 时对 D 做同样的事后复盘（规则总表五.7）。"""
    experiment = store.experiment(experiment_id, light=True)
    if experiment['result'].get('strategy_contract') not in {'agent-strategy-3','agent-strategy-4'}:
        return
    if final_d:
        current = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') == 'D']
        number = 'D'
    else:
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
        golden_questions=json.loads(baseline['dataset_snapshot_json']).get('questions', []), causal_evidence=experiment['result'].get('causal_evidence') is True)
    prompt = {'round':number, 'prior_sandbox_results':facts['prior_sandbox_results'],
              'predictions':{c['id']:predicted_ids(c) for c in evaluated},
              'skipped_candidates':[c['id'] for c in current if c['status']=='skipped'],
              'previous_round_conclusions':experiment['result'].get('round_conclusions', {})}
    system = ('你是RAG优化Agent。只读本实验保存事实，撰写本轮结论，输出JSON。不得编造检索证据或单参数因果关系，记录缺失写未知。'
              'plans逐一覆盖已跑过的Candidate（跳过的不算已跑过）：candidate_id,fixed_question_ids,new_failure_question_ids均采用正式题号；'
              'matched_question_ids是实际修好与predictions交集，prediction_match_count为交集数量；unmatched_reason解释预测不符原因；'
              'parameter_assessment写哪些参数有效/有害/待验证；evidence_reason说明检索位置或耗时依据，多参数写无法单独确定及最可能参数和理由；'
              'conclusion总结有效/有害/待验证；lessons为非空字符串数组，写带入下一轮的经验。格式{"plans":[],"lessons":[]}。')
    if final_d:
        winner = next((c for c in experiment['candidates'] if c['id'] == (evaluated[0]['reasoning'].get('winner_id') if evaluated else None)), None)
        if winner:
            prompt['winner_comparison'] = {d['id']: winner_comparison(store, d, winner) for d in evaluated}
            system += ('D是在已确认Winner上精修：winner_comparison是程序事实，列出D相对Winner只改了哪些参数，以及相对Winner修好/新错的题。'
                       '相对Baseline的多项差异里，除这几项外都是Winner原有的改动，不是D新改的；分析D时不要写成多参数混改。'
                       '相对Winner只改1个参数时，相对Winner的修好/新错可以说与该参数伴随出现，仍不能写成已证明的因果。predictions里的D预测来自改动的目标题。')
    if experiment['result'].get('causal_evidence'):
        prompt['case_comparisons'] = facts['case_comparisons']
        system += ('逐题对比case_comparisons是程序事实。每个plans新增case_reviews数组，逐一覆盖修好、新错、仍错题，每项含question（Q29形式）、state（修好、新错、仍错）、reason（一句中文原因）、attributed_parameter（中文参数名或未知）、assessment（有效、无效、不确定）。'
                   '证据没有变化或未知，不能声称检索参数改变了判定，assessment须无效或不确定。parameter_assessment只写有效、无效、不确定；evidence_reason附逐题依据。多参数写无法单独确定。'
                   '所有业务说明使用中文短句、中文参数名和Q29形式题号，不出现内部编号或英文下划线字段名；机器结构键保留协议。')
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
            response = json.loads(attempt['raw'])
            if experiment['result'].get('causal_evidence'):
                mapping = {r['题号']:r['题目键'] for rows in facts['case_comparisons'].values() for r in rows}
                response = business_output(normalize_question_references(response, mapping), mapping,
                    {c['id']:('方案D' if c['reasoning'].get('candidate_label')=='D' else f"第{c['reasoning'].get('round',1)}轮方案{c['reasoning'].get('candidate_label','')}") for c in evaluated})
            review = validate_round_conclusion(response, evaluated)
            if experiment['result'].get('causal_evidence'):
                for plan in review['plans']:
                    candidate = next(c for c in evaluated if c['id'] == plan['candidate_id'])
                    validate_case_review(plan, facts['case_comparisons'][candidate['id']], candidate['reasoning'].get('changed_parameters', {}))
            saved.update(status='saved', review=review)
            saved.update(cost_fields(getattr(getattr(runtime.provider,'settings',None),'model',None), [u for a in saved['attempts'] for u in a.get('token_usage', [])]))
            _save(store, experiment_id, number, saved)
            return saved
        except (ValueError, TypeError, KeyError) as error:
            attempt['error'] = str(error)
            _save(store, experiment_id, number, saved)
    raise ValueError('本轮结论连续校验拒绝：'+saved['attempts'][-1]['error'])


def validate_d_mode(suggestion, winner, history, facts=None):
    """规则总表五.7：≥2个合格→部分合并（D须取用另一个合格方案的参数）；只有1个合格→在它上面至少再加1个参数。
    优先用验证过的参数；没验证过的参数可以用，但已有可用的验证参数时不能全部用新参数。D 必须生成。"""
    mode = suggestion.get('combination_mode')
    if mode == 'winner_plus_verified':
        mode = suggestion['combination_mode'] = 'winner_plus'
    if mode not in {'partial_fusion','winner_plus'} or not isinstance(suggestion.get('mode_reason'), str) or not suggestion['mode_reason'].strip():
        raise ValueError('D须选择partial_fusion（部分合并）或winner_plus（在合格方案上加参数），并说明原因')
    if suggestion.get('should_generate_d') is not True:
        raise ValueError('有合格方案时必须生成D（规则总表五.7）')
    qualified = {c['id'] for c in history if c.get('status') == 'evaluated' and c['reasoning'].get('candidate_label') in {'A','B','C'}
                 and c['result'].get('qualification', {}).get('qualified') is True}
    changes = suggestion.get('changes', [])
    if not isinstance(changes, list) or not changes:
        raise ValueError('D至少要改1个参数')
    if len(qualified) >= 2:
        if mode != 'partial_fusion':
            raise ValueError('已有2个及以上合格方案，D须为partial_fusion')
        others = qualified - {winner['id']}
        if not any(set(c.get('source_candidates') or []) & others for c in changes if isinstance(c, dict)):
            raise ValueError('partial_fusion须取用另一个合格方案的有效参数')
    elif mode != 'winner_plus':
        raise ValueError('只有1个合格方案，D须为winner_plus')
    kinds = [{'已验证':'verified','部分取用':'partial','新尝试':'new_attempt'}.get(c.get('source_type'), c.get('source_type')) for c in changes if isinstance(c, dict)]
    if (facts or {}).get('usable_repairs') and kinds and all(k == 'new_attempt' for k in kinds):
        raise ValueError('事实表已有可用的验证参数（usable_repairs），须优先使用，未验证参数只能作为补充')


def validate_causal_proposals(response, comparisons):
    from .display_summaries import PARAMETER_NAMES
    retrieval = set(PARAMETER_NAMES) - {'prompt_strategy','generation_thinking'}
    names = {PARAMETER_NAMES[k] for k in retrieval}
    candidates = response.get('candidates', [])
    directions = [c.get('direction') for c in candidates]
    if len(directions) != len(set(directions)):
        raise ValueError('同轮方案方向必须不同')
    if any(len(c.get('config_diff', {})) > rules.AGENT['max_changed_parameters'] for c in candidates):
        raise ValueError('每个方案相对基础方案最多改两个参数')
    for plan in response.get('prior_round_review', {}).get('plans', []):
        facts = comparisons.get(plan.get('candidate_id'), [])
        claims = plan.get('causal_claims')
        required = {r['题号'] for r in facts if r['变化'] in {'修好','新错'}}
        if not isinstance(claims,list) or not required <= {c.get('question_id') for c in claims}:
            raise ValueError('逐题归因必须覆盖修好与新错题')
        for claim in claims:
            if claim.get('conclusion') not in {'有效','无效','不确定','未改变证据'}:
                raise ValueError('逐题归因结论只能为有效、无效、不确定或未改变证据')
            row = next((r for r in facts if claim.get('question_id') in {r['题号'], r['题目键']}), None)
            if not row:
                raise ValueError('归因必须引用保存的逐题对比')
            if (row['证据变化'] is not True and claim.get('parameter') in retrieval | names
                    and claim.get('conclusion') not in {'无效','不确定','未改变证据'}):
                raise ValueError('证据未变，不得归因于检索参数')


def validate_case_review(plan, rows, changes):
    """Require an explicit, checked cause per changed or still failing case."""
    facts = {r['题号']:r for r in rows if r['变化'] != '仍对'}
    reviews = plan.get('case_reviews')
    if not isinstance(reviews,list) or len(reviews) != len(facts) or {r.get('question') for r in reviews} != set(facts):
        raise ValueError('逐题复盘必须覆盖修好、新错、仍错题')
    from .display_summaries import PARAMETER_NAMES
    retrieval = set(PARAMETER_NAMES) - {'prompt_strategy','generation_thinking'}
    for row in reviews:
        fact = facts[row['question']]
        if row.get('state') != fact['变化'] or not isinstance(row.get('reason'),str) or not row['reason'].strip():
            raise ValueError('逐题复盘状态或原因缺失')
        if (row.get('attributed_parameter') in retrieval | {PARAMETER_NAMES[k] for k in retrieval}
                and fact['证据变化'] is not True and row.get('assessment') not in {'无效','不确定'}):
            raise ValueError('证据未变或未知，不得声称检索参数有效')
    if plan.get('parameter_assessment') not in {'有效','无效','不确定'}:
        raise ValueError('参数判断只能是有效、无效或不确定')
    if len(changes) > 1 and plan['parameter_assessment'] == '有效' and '无法单独确定' not in plan.get('evidence_reason',''):
        raise ValueError('多参数必须注明无法单独确定')


def normalize_question_references(value, mapping):
    """Resolve display aliases only in typed question-reference fields."""
    fields = {'fixed_question_ids','new_failure_question_ids','matched_question_ids','predicted_fixed_question_ids'}
    if isinstance(value,dict):
        return {k:([mapping.get(q,q) for q in v] if k in fields and isinstance(v,list) else normalize_question_references(v,mapping)) for k,v in value.items()}
    if isinstance(value,list):return [normalize_question_references(v,mapping) for v in value]
    return value


def business_output(value, mapping, candidates=None):
    """Translate saved prose without changing protocol keys, facts or config values."""
    from .display_summaries import PARAMETER_NAMES
    fields = {'summary','baseline_remaining_assessment','conclusion','focus','action_name','strategy_name','core_idea','hypothesis','why','proposal','risk','reason','expected_impact','expected_improvement','unmatched_reason','parameter_assessment','evidence_reason','attribution_reason','most_likely_parameter','lessons'}
    replacements = {**PARAMETER_NAMES, **{v:k for k,v in mapping.items()}, **(candidates or {})}
    def prose(text):
        for source,target in sorted(replacements.items(),key=lambda pair:-len(pair[0])):
            text=text.replace(source,target)
        return text
    def walk(item, human=False):
        if isinstance(item,str):return prose(item) if human else item
        if isinstance(item,list):return [walk(v,human) for v in item]
        if isinstance(item,dict):return {k:walk(v,human or k in fields) for k,v in item.items()}
        return item
    return walk(value)
