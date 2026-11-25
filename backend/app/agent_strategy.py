"""031d strategy contract and saved-result round retrospectives."""
import json
import re
from collections import Counter, defaultdict

from . import rules, verdict
from .agent_inputs import case_comparisons, new_failure_ids
from .paid_run import provider_task
from .telemetry import collect_usage, cost_fields


NEW_EXPERIMENT_STRATEGY = {'strategy_contract': 'agent-strategy-4', 'decision_contract_version': '109c'}
PREDICTION_NOTE = '已知题上的预测；同一题可能重复计入'
GENERATION_PARAMETERS = {'prompt_strategy', 'generation_thinking'}


def bad_case_groups(cases, *, questions=None, diagnoses=None):
    from .diagnostics import diagnostic_view

    questions = questions or {}
    diagnoses = diagnoses or {}
    groups = defaultdict(list)
    for case in cases:
        if case.get('passed') is not False:
            continue
        question_id = case['question_id']
        view = diagnoses.get(question_id) or diagnostic_view(case, golden_item=questions.get(question_id))
        layer = view.get('diagnosis_category') or '记录缺失'
        subtype = view.get('subfeature') or view.get('analysis_reason') or '缺少细分错因记录'
        groups[(layer, subtype)].append(question_id)
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
    ids = bad_case_conclusion_ids(response.get('bad_case_summary'), audit['bad_case_groups'])
    for candidate in response['candidates']:
        if not isinstance(candidate.get('adjustments'), list) or not candidate['adjustments'] or not isinstance(candidate.get('risks'), list) or not candidate['risks']:
            raise ValueError('Candidate须由Agent明确写出参数调整、预期题号和风险，不能自动补写')
        validate_bad_case_references(candidate, ids)
        predicted = candidate.get('predicted_fixed_question_ids')
        if not isinstance(predicted, list) or not predicted or any(not isinstance(q, str) or q not in targets for q in predicted) or len(set(predicted)) != len(predicted):
            raise ValueError('每个Candidate必须写预计修好题号predicted_fixed_question_ids，引用当前保存题号')


def bad_case_conclusion_ids(summary, groups):
    if (not isinstance(summary, dict) or summary.get('groups') != groups
            or not isinstance(summary.get('focus'), str) or not summary['focus'].strip()):
        raise ValueError('Bad Case总结必须按保存事实逐层/细分类型统计并指出最集中问题；groups须与输入一致')
    conclusions = summary.get('conclusions')
    if not isinstance(conclusions, list) or not conclusions or any(
            not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id'].strip()
            or not isinstance(c.get('conclusion'), str) or not c['conclusion'].strip() for c in conclusions):
        raise ValueError('Bad Case总结缺少可引用结论')
    ids = {c['id'] for c in conclusions}
    if len(ids) != len(conclusions):
        raise ValueError('Bad Case结论ID重复')
    return ids


def validate_bad_case_references(candidate, ids):
    refs = candidate.get('bad_case_conclusion_ids')
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in ids for ref in refs):
        raise ValueError('每个Candidate必须引用Bad Case总结结论')


def predicted_ids(candidate):
    """A/B/C 的预测写在 predicted_fixed_question_ids；D 的预测写在每个改动的 target_question_ids。"""
    reasoning = candidate.get('reasoning', {})
    if reasoning.get('candidate_label') == 'D' and not reasoning.get('predicted_fixed_question_ids'):
        return sorted({q for row in reasoning.get('changes') or [] if isinstance(row, dict) for q in row.get('target_question_ids') or []})
    return list(reasoning.get('predicted_fixed_question_ids', []))


def validate_history_decisions(response, lessons, findings, baseline):
    decisions = response.get('history_decisions')
    labels = {candidate['id'] for candidate in response['candidates']}
    if not isinstance(decisions, list) or any(
            not isinstance(row, dict) or not isinstance(row.get('lesson'), str) for row in decisions
    ) or Counter(row['lesson'] for row in decisions) != Counter(lessons):
        raise ValueError('history_decisions 必须逐条按原文完整覆盖上一轮 lesson')
    exceptions = set()
    for row in decisions:
        affected = row.get('affected_candidates')
        reason = row.get('reason')
        decision = row.get('decision')
        if (decision not in ('采纳', '拒绝', '例外探索') or not isinstance(reason, str) or not reason.strip()
                or not isinstance(affected, list) or any(not isinstance(label, str) or label not in labels for label in affected)
                or len(set(affected)) != len(affected)):
            raise ValueError('history_decisions 需要有效的决定、理由及本轮方案标签')
        if decision == '例外探索':
            parts = re.fullmatch(r'上次[：:]\s*(.+?)[；;]\s*这次[：:]\s*(.+)', reason.strip(), re.S)
            if not affected or not parts or not all(part.strip() for part in parts.groups()) or parts[1].strip() == parts[2].strip():
                raise ValueError('例外探索必须指定方案，并写清不同前提（上次：…；这次：…）')
            exceptions.update((row['lesson'], label) for label in affected)
    for candidate in response['candidates']:
        changes = {**candidate.get('inherited_parameters', {}), **candidate['config_diff']}
        for finding in findings:
            key = finding['parameter']
            if (key in changes and parameter_direction(baseline.get(key), changes[key]) == finding['direction']
                    and (finding['lesson'], candidate['id']) not in exceptions):
                raise ValueError(f"方案 {candidate['id']} 重复 {finding['assessment']} 的 {key} 参数方向，须对对应 lesson 写明例外探索")


def parameter_direction(original, value):
    if type(original) in (int, float) and type(value) in (int, float):
        return '调高' if value > original else '调低' if value < original else '未改'
    if type(original) is bool and type(value) in (int, float):
        return '启用'
    return json.dumps(value, ensure_ascii=False)


def save_parameter_lessons(review, candidates, baseline):
    from .display_summaries import PARAMETER_NAMES
    from .optimization import gate_harming_changes

    baseline_gates = (baseline['result'].get('gates') or {}).get('gates')
    harmed = {row['candidate_id'] for row in gate_harming_changes(candidates, baseline_gates)}
    plans = {p['candidate_id']: p for p in review['plans']}
    findings = []
    for candidate in candidates:
        cid = candidate['id']
        plan = plans[cid]
        assessed = plan['parameter_assessment']
        result = candidate['result']
        if new_failure_ids(result) or cid in harmed or assessed in {'有害', '有副作用'}:
            assessment = '有副作用'
        elif assessed == '无效' or result.get('no_effect') or result.get('all_fixed_question_ids') == []:
            assessment = '无效'
        else:
            continue
        reasoning = candidate['reasoning']
        changes = reasoning.get('changed_parameters_vs_baseline', reasoning.get('changed_parameters', {}))
        label = reasoning.get('candidate_label', '')
        for key, value in changes.items():
            direction = parameter_direction(baseline['config'].get(key), value)
            caveat = '（与其他参数一起试过，无法单独归因）' if len(changes) > 1 else ''
            lesson = f'方案{label}的{PARAMETER_NAMES.get(key, key)}方向 {direction} 在原配置下{assessment}{caveat}。'
            if lesson not in review['lessons']:
                review['lessons'].append(lesson)
            findings.append({'lesson':lesson, 'candidate_id':cid, 'parameter':key, 'direction':direction,
                             'tested_value':value, 'assessment':assessment})
    return findings


def prediction_comparison(review, candidates, winner_facts=None):
    plans = {plan['candidate_id']: plan for plan in review['plans']}
    totals = {direction:{'hits':0, 'predictions':0} for direction in ('检索方向', '生成方向')}
    rows = []
    for candidate in candidates:
        reasoning = candidate['reasoning']
        if reasoning.get('candidate_label') == 'D':
            keys = set(reasoning.get('winner_config_diff', {}))
        else:
            keys = set(reasoning.get('changed_parameters', {}))
        directions = (['检索方向'] if keys - GENERATION_PARAMETERS else []) + (['生成方向'] if keys & GENERATION_PARAMETERS else [])
        predicted = sorted(set(predicted_ids(candidate)))
        plan = plans[candidate['id']]
        winner = (winner_facts or {}).get(candidate['id'])
        actual = winner['fixed_vs_winner'] if winner is not None else plan['fixed_question_ids']
        matched = sorted(set(predicted) & set(actual))
        for direction in directions:
            totals[direction]['hits'] += len(matched)
            totals[direction]['predictions'] += len(predicted)
        rows.append({'candidate_id':candidate['id'], 'directions':directions, 'predicted_fixed_question_ids':predicted,
                     'actual_fixed_question_ids':actual, 'matched_question_ids':matched,
                     'unmatched_reason':'预测与结果一致' if set(predicted) == set(actual) else plan['unmatched_reason']})
    return {'rows':rows, 'by_direction':totals, 'note':PREDICTION_NOTE}


def winner_comparison(store, d, winner):
    """D 相对 Winner 的程序事实：只改了哪些参数、相对 Winner 修好/新错哪些题。"""
    def outcomes(candidate):
        run = candidate['result'].get('evaluation_run_id')
        return verdict.final_verdicts(run, store=store, use_final=verdict.uses_final(candidate['result']))
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


EXPLANATION_CONFLICT = '解释与程序事实冲突'
REVIEW_STATES = {'修好', '新错', '仍错'}
FINAL_MISS = r'(?:未[能曾]?|没(?:有)?)\s*(?:进入|进|到达)'
FINAL_HIT = r'(?:已(?:经)?\s*(?:进入|进)|(?:进入|进)了)'
NEW_FINAL_HITS = (r'新增\s*(?:Final|最终资料)\s*命中(?:数)?\s*(?:为|是|[:：=])?\s*(\d+)'
                  r'|新增(?:了)?\s*(\d+)\s*(?:条|个|次)?\s*(?:Final|最终资料)')
ENHANCEMENT_TERMS = {
    'query_decompose':r'Query[ _]Decompose|拆分查询|查询拆分|查询拆解|拆解',
    'query_rewrite':r'Query[ _]Rewrite|查询改写',
    'multi_query':r'Multi[- _]Query|多查询',
    'hyde':r'HyDE',
}


def _conflicts_with_case(text, facts, *, question=None, label=None):
    """Check explicit prose claims, including older reviews without typed references."""
    if not isinstance(text,str):
        return False
    for clause in re.split(r'[，,；;。！？\n]',text):
        labels = set(re.findall(r'(?:方案|候选)\s*([A-D])\b',clause))
        if (labels and label not in labels) or re.search(r'基线|Baseline|从.*(?:→|变为|变成)|如果|是否|可能',clause,re.I):
            continue
        questions = re.findall(r'Q\d{2,3}(?!\d)',clause) or ([question] if question else [])
        for q in questions:
            row = facts.get(q)
            if not row:
                continue
            verdict = re.search(r'(?:判(?:定)?(?:为)?|答)\s*([对错])',clause)
            if verdict and type(row['候选判对']) is bool and row['候选判对']!=(verdict[1]=='对'):
                return True
            hits = re.search(NEW_FINAL_HITS,clause,re.I)
            if hits and row['候选增强新增命中'] is not None:
                effect = row['候选增强新增命中']
                methods = [key for key,pattern in ENHANCEMENT_TERMS.items() if re.search(pattern,clause,re.I)]
                observed = (effect.get('new_final_hits') if not methods else
                            effect['by_method'].get(methods[0],{}).get('new_final_hits') if len(methods)==1 else None)
                if type(observed) is int and observed!=int(hits[1] or hits[2]):
                    return True
            if not re.search(r'标准(?:证据|引文|原文)|C-\d+|证据.*(?:最终|Final|位置)',clause,re.I):
                continue
            positions = row['候选标准证据位置']
            final = re.search(r'最终|Final',clause,re.I)
            if not isinstance(positions,list) or not final and re.search(r'候选|重排|排序|召回',clause):
                continue
            chunk_ids = re.findall(r'C-\d+',clause)
            ranks = [p['final'] for p in positions if not chunk_ids or any(p['chunk_id'].endswith(k) for k in chunk_ids)]
            if ranks and ((all(type(r) is int or '按原文判定' in str(r) for r in ranks) and re.search(FINAL_MISS,clause))
                          or (all(r=='未进入' for r in ranks) and re.search(FINAL_HIT,clause))):
                return True
            if re.search(r'位置(?:仍)?(?:未变|没变|没有变化)',clause):
                previous = row['基线标准证据位置']
                if (isinstance(previous,list) and all(p['final']!='记录缺失' for p in [*previous,*positions])
                        and [p['final'] for p in previous]!=[p['final'] for p in positions]):
                    return True
    return False


def _review_with_facts(response, candidates, case_facts, causal):
    if not isinstance(response,dict) or not isinstance(response.get('plans'),list):
        raise ValueError('本轮结论必须包含plans')
    by_id = {c['id']:c for c in candidates}
    case_by_id = {cid:{r['题号']:r for r in rows} for cid,rows in case_facts.items()}
    prose_fields = ('unmatched_reason','parameter_assessment','evidence_reason','conclusion')
    plans = []
    round_conflict = 'case_facts' in response and response['case_facts']!=case_facts
    for item in response['plans']:
        if not isinstance(item,dict) or item.get('candidate_id') not in by_id:
            raise ValueError('本轮结论必须逐一覆盖已跑过的Candidate')
        cid = item['candidate_id']
        candidate = by_id[cid]
        label = candidate['reasoning'].get('candidate_label')
        facts = case_by_id[cid]
        plan = {k:item[k] for k in ('candidate_id',*prose_fields) if k in item}
        fixed = candidate['result'].get('all_fixed_question_ids', [])
        matched = sorted(set(fixed) & set(predicted_ids(candidate)))
        totals = {'fixed_question_ids':fixed,'new_failure_question_ids':new_failure_ids(candidate['result']),
                  'matched_question_ids':matched,'prediction_match_count':len(matched)}
        def disagrees(key, expected):
            value = item.get(key)
            if isinstance(expected,list):
                return not isinstance(value,list) or sorted(value)!=sorted(expected)
            return type(value) is not type(expected) or value!=expected
        conflict = any(disagrees(k,v) for k,v in totals.items() if k in item)
        conflict |= any(_conflicts_with_case(item.get(k),facts,label=label) for k in prose_fields)
        plan.update(totals)
        if causal:
            reviews = item.get('case_reviews')
            if not isinstance(reviews,list) or any(not isinstance(r,dict) for r in reviews):
                raise ValueError('逐题复盘必须覆盖修好、新错、仍错题')
            plan['case_reviews'] = []
            for review in reviews:
                q = review.get('question')
                if q not in facts or facts[q]['变化'] not in REVIEW_STATES:
                    raise ValueError('逐题复盘必须覆盖修好、新错、仍错题')
                fact = facts[q]
                row = {k:review[k] for k in ('question','reason','attributed_parameter','assessment') if k in review}
                claims = review.get('fact_claims',{})
                if (not isinstance(claims,dict) or any(k not in fact or type(v) is not type(fact[k]) or v!=fact[k] for k,v in claims.items())
                        or ('state' in review and review['state']!=fact['变化'])
                        or _conflicts_with_case(row.get('reason'),facts,question=q,label=label)
                        or _unsupported_retrieval_assessment(row,fact)):
                    conflict = True
                row['state'] = fact['变化']
                plan['case_reviews'].append(row)
        if conflict:
            plan.update(unmatched_reason=EXPLANATION_CONFLICT,parameter_assessment='不确定',
                        evidence_reason=EXPLANATION_CONFLICT,conclusion=EXPLANATION_CONFLICT)
            for row in plan.get('case_reviews',[]):
                row.update(reason=EXPLANATION_CONFLICT,attributed_parameter='未知',assessment='不确定')
            round_conflict = True
        plans.append(plan)
    lessons = response.get('lessons')
    if isinstance(lessons,list):
        round_conflict |= any(_conflicts_with_case(lesson,case_by_id[cid],label=c['reasoning'].get('candidate_label'))
                              for lesson in lessons for cid,c in by_id.items())
    return {'plans':plans,'lessons':[EXPLANATION_CONFLICT] if round_conflict else lessons}


def _round_case_facts(baseline_cases, candidate_cases, questions):
    frozen = {q['id']:q for q in questions}
    return {cid:case_comparisons(baseline_cases,cases,frozen,include_facts=True)
            for cid,cases in candidate_cases.items()}


def round_conclusions_for_prompt(store, baseline, candidates, conclusions):
    """Recheck old saved reviews for decision prompts without rewriting the audit."""
    by_id = {c['id']:c for c in candidates}
    projected = {}
    for number,saved in (conclusions or {}).items():
        if saved.get('status')!='saved':
            continue
        item = {k:saved[k] for k in ('status','review','case_facts','parameter_findings') if k in saved}
        projected[number] = item
        if 'case_facts' in item or 'review' not in item:
            continue
        review = item['review']
        plans = review.get('plans',[])
        selected = [by_id[p['candidate_id']] for p in plans if p.get('candidate_id') in by_id]
        if len(selected)!=len(plans):
            item['review'] = {'plans':[],'lessons':['复盘引用的保存方案缺失，待核对']}
            continue
        use_final = any(verdict.uses_final(c['result']) for c in selected)
        candidate_cases = {c['id']: verdict.final_cases(store, c['result'].get('evaluation_run_id'), use_final=use_final)
                           for c in selected}
        facts = _round_case_facts(verdict.final_cases(store, baseline['id'], use_final=use_final),candidate_cases,
                                  json.loads(baseline['dataset_snapshot_json']).get('questions',[]))
        try:
            item['review'] = _review_with_facts(review,selected,facts,any('case_reviews' in p for p in plans))
        except (ValueError, TypeError, KeyError):
            item['review'] = {'plans':[],'lessons':['旧复盘的逐题说明无法与保存记录核对']}
        item['case_facts'] = facts
    return projected


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
    use_final = verdict.uses_final(experiment['result'])
    baseline_cases = verdict.final_cases(store, baseline['id'], use_final=use_final)
    candidate_cases = {c['id']: verdict.final_cases(store, c['result'].get('evaluation_run_id'), use_final=use_final)
                       for c in evaluated}
    questions = json.loads(baseline['dataset_snapshot_json']).get('questions', [])
    case_facts = _round_case_facts(baseline_cases,candidate_cases,questions)
    causal = experiment['result'].get('causal_evidence') is True
    _, facts = build_agent_prompt([], baseline['config'], evaluated, [], list('ABC'),
        baseline_cases=baseline_cases, candidate_cases=candidate_cases, golden_questions=questions)
    prompt = {'round':number, 'prior_sandbox_results':facts['prior_sandbox_results'],
              'case_comparisons':case_facts,
              'predictions':{c['id']:predicted_ids(c) for c in evaluated},
              'skipped_candidates':[c['id'] for c in current if c['status']=='skipped'],
              'previous_round_conclusions':round_conclusions_for_prompt(store,baseline,experiment['candidates'],
                  {n:r for n,r in experiment['result'].get('round_conclusions',{}).items() if n!=str(number)})}
    if 'parameter_effect_ledger' in experiment['result']:
        ledger = experiment['result']['parameter_effect_ledger']
        if use_final:
            verdict.require_empty_history(ledger)
        prompt['parameter_effect_ledger'] = ledger
    system = ('你是RAG优化Agent。只读本实验保存事实，撰写解释，输出JSON。case_comparisons是程序事实。'
              '标准证据在最终资料的位置与辅助查询新增命中是不同的记录。引用时以对应字段为准，缺失写未知。'
              'plans逐一覆盖已跑过的Candidate（跳过的不算），每项给candidate_id。实际修好、新错、预测命中题号和数量由程序填写。'
              'unmatched_reason解释预测不符原因；parameter_assessment写哪些参数有效/有害/待验证；'
              'evidence_reason解释检索或耗时，多参数写无法单独确定及最可能参数和理由；'
              'conclusion总结有效/有害/待验证；lessons为非空字符串数组，写带入下一轮的经验。格式{"plans":[],"lessons":[]}。')
    if final_d:
        winner = next((c for c in experiment['candidates'] if c['id'] == (evaluated[0]['reasoning'].get('winner_id') if evaluated else None)), None)
        if winner:
            prompt['winner_comparison'] = {d['id']: winner_comparison(store, d, winner) for d in evaluated}
            system += ('D是在已确认Winner上精修：winner_comparison是程序事实，列出D相对Winner只改了哪些参数，以及相对Winner修好/新错的题。'
                       '相对Baseline的多项差异里，除这几项外都是Winner原有的改动，不是D新改的；分析D时不要写成多参数混改。'
                       '相对Winner只改1个参数时，相对Winner的修好/新错可以说与该参数伴随出现，仍不能写成已证明的因果。predictions里的D预测来自改动的目标题。')
    if causal:
        system += ('每个plans包含case_reviews数组，逐一覆盖修好、新错、仍错题，每项含question（Q29形式）、reason（一句中文原因）、attributed_parameter（中文参数名或未知）、assessment（有效、无效、不确定）。状态由程序填写。'
                   '如需明确引用程序事实，fact_claims可选，只写引用的case_comparisons字段名及字段原值。'
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
                mapping = {r['题号']:r['题目键'] for rows in case_facts.values() for r in rows if r['题号']!='未知'}
                response = business_output(normalize_question_references(response, mapping), mapping,
                    {c['id']:('方案D' if c['reasoning'].get('candidate_label')=='D' else f"第{c['reasoning'].get('round',1)}轮方案{c['reasoning'].get('candidate_label','')}") for c in evaluated})
            review = validate_round_conclusion(_review_with_facts(response,evaluated,case_facts,causal), evaluated)
            if causal:
                for plan in review['plans']:
                    candidate = next(c for c in evaluated if c['id'] == plan['candidate_id'])
                    validate_case_review(plan, case_facts[candidate['id']], candidate['reasoning'].get('changed_parameters', {}))
            if experiment['result'].get('decision_contract_version') == '109c':
                saved['prediction_comparison'] = prediction_comparison(review, evaluated, prompt.get('winner_comparison'))
                if not final_d:
                    saved['parameter_findings'] = save_parameter_lessons(review, evaluated, baseline)
            saved.update(status='saved', case_facts=case_facts, review=review)
            saved.update(cost_fields(getattr(getattr(runtime.provider,'settings',None),'model',None), [u for a in saved['attempts'] for u in a.get('token_usage', [])]))
            _save(store, experiment_id, number, saved)
            return saved
        except (ValueError, TypeError, KeyError) as error:
            attempt['error'] = str(error)
            _save(store, experiment_id, number, saved)
    raise ValueError('本轮结论连续校验拒绝：'+saved['attempts'][-1]['error'])


def _d_fusion_already_evaluated(history, qualified, base):
    from .composite import parameter_diff

    evaluated = {c['id']: parameter_diff(c['config'], base) for c in history if c.get('status') == 'evaluated'}
    combined = {}
    for candidate_id in qualified:
        for key, value in evaluated[candidate_id].items():
            if key in combined and combined[key] != value:
                return False
            combined[key] = value
    return bool(combined) and combined in evaluated.values()


def validate_d_mode(suggestion, winner, history, facts=None):
    """规则总表六.7：多个合格方案可部分合并，组合已跑过时改为 Winner 加一项。
    优先用验证过的参数；没验证过的参数可以用，但已有可用的验证参数时不能全部用新参数。D 必须生成。"""
    mode = suggestion.get('combination_mode')
    if mode == 'winner_plus_verified':
        mode = suggestion['combination_mode'] = 'winner_plus'
    if mode not in {'partial_fusion','winner_plus'} or not isinstance(suggestion.get('mode_reason'), str) or not suggestion['mode_reason'].strip():
        raise ValueError('D须选择partial_fusion（部分合并）或winner_plus（基于Winner精修），并说明原因')
    if suggestion.get('should_generate_d') is not True:
        raise ValueError('有合格方案时必须生成D（规则总表五.7）')
    qualified = {c['id'] for c in history if c.get('status') == 'evaluated' and c['reasoning'].get('candidate_label') in {'A','B','C'}
                 and c['result'].get('qualification', {}).get('qualified') is True}
    changes = suggestion.get('changes', [])
    if not isinstance(changes, list) or not changes:
        raise ValueError('D至少要改1个参数')
    from .composite import effective_d_config, parameter_diff, pipeline_config, validate_d_parameter_limit

    base = (facts or {}).get('baseline_config')
    addition = suggestion.get('proposed_config_diff')
    effective = None
    if base and isinstance(addition, dict):
        winner_config = pipeline_config(winner['config'])
        effective = effective_d_config({**winner_config, **addition}, addition)
        if effective is not None:
            validate_d_parameter_limit(effective, base)
    min_fusion = rules.AGENT['min_qualified_for_fusion']
    fusion_repeated = len(qualified) >= min_fusion and base and _d_fusion_already_evaluated(history, qualified, base)
    if len(qualified) >= min_fusion and not fusion_repeated:
        if mode != 'partial_fusion':
            raise ValueError(f'已有 {min_fusion} 个及以上合格方案，D须为partial_fusion')
        others = qualified - {winner['id']}
        if not any(set(c.get('source_candidates') or []) & others for c in changes if isinstance(c, dict)):
            raise ValueError('partial_fusion须取用另一个合格方案的有效参数')
    else:
        if mode != 'winner_plus':
            reason = '合格方案的参数并集已评测' if fusion_repeated else '合格方案数未达到融合门槛'
            raise ValueError(f'{reason}，D须为winner_plus')
        extra = rules.AGENT['winner_extra_parameters']
        if base and (effective is None or len(addition) != extra or addition.keys() & parameter_diff(winner_config, base).keys()
                     or parameter_diff(effective, winner_config) != addition):
            raise ValueError(f'D 须保留 Winner 改动且只新增 {extra} 个参数')
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
        raise ValueError(f"每个方案相对基础方案最多改 {rules.AGENT['max_changed_parameters']} 个参数")
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


def _unsupported_retrieval_assessment(review, fact):
    from .display_summaries import PARAMETER_NAMES
    retrieval = set(PARAMETER_NAMES) - {'prompt_strategy','generation_thinking'}
    return (review.get('attributed_parameter') in retrieval | {PARAMETER_NAMES[k] for k in retrieval}
            and fact['证据变化'] is not True and review.get('assessment') not in {'无效','不确定'})


def validate_case_review(plan, rows, changes):
    """Require an explicit, checked cause per changed or still failing case."""
    facts = {r['题号']:r for r in rows if r['变化'] in REVIEW_STATES}
    reviews = plan.get('case_reviews')
    if not isinstance(reviews,list) or len(reviews) != len(facts) or {r.get('question') for r in reviews} != set(facts):
        raise ValueError('逐题复盘必须覆盖修好、新错、仍错题')
    for row in reviews:
        fact = facts[row['question']]
        if row.get('state') != fact['变化'] or not isinstance(row.get('reason'),str) or not row['reason'].strip():
            raise ValueError('逐题复盘状态或原因缺失')
        if _unsupported_retrieval_assessment(row,fact):
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
