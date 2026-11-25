"""Decision contract v2, based on frozen evidence and saved evaluations."""
import json
import re

from . import rules
from .agent_inputs import MISSING, evidence_positions, prepare_baseline_rows
from .composite import parameter_diff, pipeline_config
from .diagnostic_categories import MISSED_SUBQUESTION, TABLE_ERROR, WRONG_DENIAL
from .evaluation_contract import VERSIONS, business_verdict
from .policy import FIXED_PIPELINE_PARAMETERS

CONTRACT = '113b'
STAGES = ('candidates', 'reranked', 'final')
NOT_PRESENT = '未进入'
FAULT_LABELS = {'recall': '未召回', 'ranking': '排序靠后', 'generation': '进了 Final 但生成出错',
                'safety': '安全相关', 'unknown': '未知'}
DIRECT_STAGES = {'recall': {'recall'}, 'ranking': {'ranking', 'final'},
                 'generation': {'generation'}, 'safety': {'generation'}}
PREVIEW_KEYS = rules.AGENT_PARAMETER_STAGES.keys() - {'prompt_strategy', 'generation_thinking'}


def same_base(left, right):
    return (pipeline_config({**FIXED_PIPELINE_PARAMETERS, **left})
            == pipeline_config({**FIXED_PIPELINE_PARAMETERS, **right}))


def rank(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and (match := re.fullmatch(r'(\d+)（原文在同一父块内，按原文判定）', value)):
        return int(match[1])
    return None


def saved_passed(case):
    if type(case.get('final_passed')) is bool:
        return case['final_passed']
    outcome = case.get('evaluation_outcome') or {}
    if outcome.get('contract_version') == VERSIONS['scoring_policy']:
        return {'PASS': True, 'FAIL': False}.get(business_verdict(case))
    if outcome.get('execution_complete') is False or case.get('technical_error'):
        return None
    return case.get('passed') if type(case.get('passed')) is bool else None


def _diagnostic_positions(view):
    return [{'chunk_id': p.get('evidence_index'), **{
        stage: p.get(field) if p.get(field) is not None else NOT_PRESENT if p.get(hit) is False else MISSING
        for stage, field, hit in (('candidates', 'candidate_rank', 'candidate_hit'),
                                  ('reranked', 'rerank_rank', ''), ('final', 'final_rank', 'final_hit'))}}
        for p in view.get('evidence_checks', [])]


def fault_stage(row):
    case, view = row['result'], row['diagnostic_view']
    subtype = view.get('subfeature') or ''
    positions = (row.get('retrieval_facts') or {}).get('standard_evidence_positions')
    if not isinstance(positions, list):
        positions = _diagnostic_positions(view)
    code, reason, detail = 'unknown', '标准证据位置或已保存诊断不足。', None
    if saved_passed(case) is True:
        reason = '对照底座已答对。'
    elif view.get('primary_root_cause') == 'Safety' or subtype == '安全提示丢失':
        code, reason, detail = 'safety', view.get('analysis_reason') or '已保存诊断指出安全问题。', subtype or None
    elif saved_passed(case) is False and isinstance(positions, list) and positions:
        missing = [p for p in positions if p.get('final') == NOT_PRESENT]
        if any(p.get('candidates') == NOT_PRESENT for p in missing):
            code, reason = 'recall', '至少一段缺失的最终标准证据也没有进入候选。'
        elif missing and all(rank(p.get('candidates')) for p in missing):
            code, reason = 'ranking', '缺失的最终标准证据能在候选中定位。'
        elif all(rank(p.get('final')) for p in positions):
            code, reason = 'generation', '标准证据均已进入 Final，底座仍判错。'
            issues = (case.get('judge_result') or {}).get('issues') or []
            detail = {WRONG_DENIAL: '错误否定', TABLE_ERROR: '表格归类', MISSED_SUBQUESTION: '漏子问'}.get(subtype)
            if detail is None and any(i.get('failure_kind') == 'scope' for i in issues if isinstance(i, dict)):
                detail = '资料边界过度断言'
            if detail is None and subtype == '答案出现幻觉':
                detail = '幻觉'
    return {'code': code, 'stage': FAULT_LABELS[code], 'subtype': detail, 'reason': reason,
            'evidence_positions': positions or MISSING}


def _evidence_delta(question, before, after):
    def positions(case):
        trace = (case.get('programmatic_metrics') or {}).get('retrieval_trace') or {}
        records = evidence_positions(question, trace)
        if not isinstance(records, list):
            from .diagnostics import automatic_analysis
            records = _diagnostic_positions(automatic_analysis(case, golden_item=question))
        return {r['chunk_id']: r for r in records}

    left, right = positions(before), positions(after)
    records, added, lost = [], [], []
    for chunk in dict.fromkeys([*left, *right]):
        a = {stage: left.get(chunk, {}).get(stage, MISSING) for stage in STAGES}
        b = {stage: right.get(chunk, {}).get(stage, MISSING) for stage in STAGES}
        delta = {stage: rank(b[stage]) - rank(a[stage])
                 if rank(a[stage]) and rank(b[stage]) else None for stage in STAGES}
        records.append({'chunk_id': chunk, 'before': a, 'after': b, 'rank_delta': delta})
        if MISSING in (a['final'], b['final']):
            added.append(None)
            lost.append(None)
        else:
            added.append(a['final'] == NOT_PRESENT and rank(b['final']) is not None)
            lost.append(rank(a['final']) is not None and b['final'] == NOT_PRESENT)
    return records, _known_change(added), _known_change(lost)


def _known_change(values):
    return True if True in values else None if not values or None in values else False


def effect_entries(changes, source, questions, bad_cases, before, after, *, historical=False):
    """One row per tested intervention and affected or known Bad Case."""
    if not changes:
        return []
    statuses = {(False, True): '修好', (True, False): '弄坏', (False, False): '无效', (True, True): '无效'}
    question_ids = set(bad_cases) | {q for q, c in before.items() if saved_passed(c) is False}
    question_ids.update(q for q, c in after.items() if saved_passed(c) is False and saved_passed(before.get(q, {})) is True)
    parameter = next(iter(changes)) if len(changes) == 1 else None
    confidence = ('组合观察，不可归因' if parameter is None else '单参数对照，未复验'
                  if source.get('base_run_id') else '对照底座缺少实测，不可归因')
    entries = []
    for qid in sorted(question_ids):
        left, right = before.get(qid, {}), after.get(qid, {})
        question = questions.get(qid, {})
        evidence, added, lost = _evidence_delta(question, left, right)
        entries.append({**source, 'question_id': qid,
                        'display_question_id': question.get('display_id') or question.get('coverage_slot') or
                        (question.get('raw') or {}).get('coverage_slot') or qid,
                        'changes': changes, 'parameter': parameter, 'value': changes.get(parameter),
                        'status': statuses.get((saved_passed(left), saved_passed(right)), '未知'),
                        'confidence': confidence, 'evidence': evidence, 'final_added': added, 'final_lost': lost,
                        'source': '历史观察（改造前实验）' if historical else '本实验保存结果'})
    return entries


def _preview_signal(preview, base_id, changes, base_changes, display_id):
    variants = preview.get('configs') or []
    if set(changes) - PREVIEW_KEYS or base_id != 'Baseline' and base_changes is None:
        # A preview cannot distinguish configurations whose generation strategy changed.
        return False, False, False
    base_changes = base_changes or {}
    retrieval_base = {k: v for k, v in base_changes.items() if k in PREVIEW_KEYS}
    trial = {**retrieval_base, **changes}
    selected = next((c for c in variants if c.get('change') == trial), {})
    if not selected:
        return False, False, False
    if base_id == 'Baseline':
        return (display_id in selected.get('evidence_enters_final', []),
                display_id in selected.get('evidence_lost_from_final', []),
                display_id in selected.get('context_changed_question_ids', []))
    original = next((c for c in variants if c.get('change') == retrieval_base), None) if retrieval_base else {}
    if original is None or not base_id:
        return False, False, False
    all_hit = (preview.get('baseline_evidence', {}).get(display_id) or {}).get('all_hit')

    def hit(variant):
        if display_id in variant.get('evidence_enters_final', []):
            return True
        if display_id in variant.get('evidence_lost_from_final', []):
            return False
        return all_hit

    previous_hit, trial_hit = hit(original), hit(selected)
    left = (original if retrieval_base else preview).get('context_fingerprints', {}).get(display_id)
    right = selected.get('context_fingerprints', {}).get(display_id)
    return (previous_hit is False and trial_hit is True, previous_hit is True and trial_hit is False,
            bool(left and right and left != right))


def validate_mechanism(proposal, targets, base_id, preview, ledger, *, base_changes=None):
    changes = proposal['config_diff']
    stages = {key: rules.AGENT_PARAMETER_STAGES.get(key, ()) for key in changes}
    actions = {stage for values in stages.values() for stage in values}
    explanations = proposal.get('cross_layer_mechanisms')
    rows = []
    for target in targets:
        qid = target['question_id']
        display = target['diagnostic_view'].get('display_question_id') or qid
        fault = target.get('mechanism_fault') or fault_stage(target)
        code = fault['code']
        enters, lost, changed_context = _preview_signal(preview, base_id, changes, base_changes, display)
        supporting = [r for r in ledger if base_id and r['base_id'] == base_id and r['question_id'] == qid
                      and r['changes'] == changes and r['status'] == '修好'
                      and (code not in {'recall', 'ranking'} or r['final_added'] is True and r['final_lost'] is False)]
        proof = [{'source': r['source'], 'candidate_id': r['candidate_id'], 'run_id': r['candidate_run_id']} for r in supporting]
        if enters and not lost:
            proof.append({'source': '检索预演', 'observation': '标准证据进入 Final'})
        if code == 'generation' and 'retrieval_max_tokens' in changes and changed_context and not lost:
            proof.append({'source': '检索预演', 'observation': '上下文长度变化，标准证据未丢失'})
        mechanism = (explanations.get(qid) or explanations.get(display)) if isinstance(explanations, dict) else None
        mechanism = mechanism.strip() if isinstance(mechanism, str) else None
        decision = '拒绝'
        if code == 'unknown':
            reason = fault['reason']
        elif code in {'recall', 'ranking'} and set(changes) == {'prompt_strategy'}:
            reason = '标准证据未进 Final，单改回答提示词无法补回证据。'
        elif code == 'generation' and actions and actions <= {'recall', 'ranking'}:
            reason = '标准证据已进入 Final，单从召回或排序调整不能解决已确认的生成错误。'
        elif DIRECT_STAGES[code] & actions:
            if proof:
                decision, reason = '放行', '作用环节匹配，且同底座的保存证据支持试验。'
            else:
                reason = '作用环节匹配，缺同底座、同改动、同题的预演或账本证据。'
        elif set(changes).intersection(rules.AGENT_CONTEXT_PARAMETERS):
            cross_preview = (changed_context if code in {'generation', 'safety'} else enters) and not lost
            if mechanism and cross_preview:
                decision, reason = '补证', 'Agent 已写明中间机制，同底座检索预演支持交付资料改变。'
                proof.append({'source': '检索预演', 'observation': '交付资料改变，标准证据未丢失'})
            else:
                reason = '跨层作用缺少逐题中间机制或同底座预演证据。'
        else:
            reason = '参数作用环节与该题的故障环节不匹配。'
        rows.append({'question_id': qid, 'display_question_id': display, 'base_id': base_id,
                     'fault': fault, 'parameter_stages': stages, 'decision': decision,
                     'reason': reason, 'mechanism': mechanism, 'evidence': proof})
    return rows


def faults_for_cases(baseline, cases, bad_cases):
    reference = {row['question_id']: row['id'] for row in bad_cases}
    rows = [{'id': reference[c['question_id']], 'question_id': c['question_id'], 'result': c}
            for c in cases if c['question_id'] in reference]
    return {row['question_id']: fault_stage(row) for row in prepare_baseline_rows(baseline, rows)}


def candidate_effects(db, experiment, candidate, result, *, historical=False):
    """Read from the same transaction as candidate completion or history import."""
    base_id = experiment['baseline_run_id']
    baseline = db.execute('SELECT config_json, judge_json, dataset_snapshot_json FROM evaluation_runs WHERE id=?',
                          (base_id,)).fetchone()
    base_config = pipeline_config(json.loads(baseline['config_json']))
    identity = json.loads(baseline['judge_json']).get('evaluation_identity')
    questions = {q['id']: q for q in json.loads(baseline['dataset_snapshot_json']).get('questions', [])}
    reasoning = json.loads(candidate['reasoning_json'])
    related = reasoning.get('winner_id') or reasoning.get('inherited_from')
    compare_id, compare_run, compare_config = 'Baseline', base_id, base_config
    if related:
        reference = db.execute('SELECT config_json, result_json FROM candidate_configs WHERE id=? AND experiment_id=?',
                               (related, experiment['id'])).fetchone()
        source_config = pipeline_config(json.loads(reference['config_json'])) if reference else None
        compare_config = (source_config if reasoning.get('winner_id') else
                          {**base_config, **(reasoning.get('inherited_parameters') or {})})
        reference_result = json.loads(reference['result_json']) if reference else {}
        compare_run = (reference_result.get('evaluation_run_id') if source_config is not None and compare_config is not None
                       and same_base(source_config, compare_config)
                       and identity and reference_result.get('evaluation_identity') == identity else None)
        compare_id = related if compare_run else None
        if compare_config is None:
            return []
    changes = parameter_diff(json.loads(candidate['config_json']), compare_config)
    run_id = result.get('evaluation_run_id')

    from . import verdict
    use_final = verdict.current(json.loads(experiment['result_json'])) and not historical
    def cases(rid):
        if not rid:
            return {}
        rows = [{'question_id': r['question_id'], **json.loads(r['result_json'])} for r in db.execute(
            'SELECT question_id, result_json FROM evaluation_case_results WHERE run_id=?', (rid,))]
        return {c['question_id']: c for c in verdict.final_cases(None, rid, connection=db, use_final=use_final, cases=rows)}

    baseline_cases = cases(base_id) if use_final else None
    bad_cases = ({key for key, case in baseline_cases.items() if saved_passed(case) is False} if use_final else
                 {r[0] for r in db.execute('SELECT question_id FROM bad_cases WHERE run_id=?', (base_id,))})
    before = baseline_cases if use_final and compare_run == base_id else cases(compare_run)
    comparable = identity and result.get('evaluation_identity') == identity
    if use_final:
        comparable = comparable and verdict.current(result)
    after = cases(run_id) if comparable else {}
    source = {'experiment_id': experiment['id'], 'candidate_id': candidate['id'],
              'round': 'D' if reasoning.get('candidate_label') == 'D' else reasoning.get('round'),
              'baseline_run_id': base_id, 'base_id': compare_id, 'base_run_id': compare_run, 'base_config': compare_config,
              'base_reference_candidate_id': related, 'candidate_run_id': run_id}
    return effect_entries(changes, source, questions, bad_cases, before, after, historical=historical)
