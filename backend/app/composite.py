"""D facts from frozen results and validation of refinement on a confirmed Winner."""
import json
from itertools import combinations

from .agent_inputs import evidence_positions, new_failure_ids
from .policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, GATE_DEFINITIONS, validate_candidate_config


def pipeline_config(config):
    result = {k:config.get(k, DEFAULT_PIPELINE_CONFIG[k]) for k in ALLOWED_SEARCH_SPACE}
    for key,value in result.items():
        result[key] = next((v for v in ALLOWED_SEARCH_SPACE[key] if v==value and (type(v) is type(value) or type(v) in (int,float) and type(value) in (int,float))),value)
    return result


def parameter_diff(config, base):
    return {k:v for k,v in pipeline_config(config).items() if type(v) is not type(base.get(k)) or v != base.get(k)}


def build_d_facts(store, baseline, winner, history):
    """Read saved single-pass cases/trace only; never call retrieval or a model."""
    questions = {q['id']:q for q in json.loads(baseline['dataset_snapshot_json']).get('questions', [])}
    base = pipeline_config(baseline['config'])
    baseline_cases = {c['question_id']:c for c in store.evaluation_case_results(baseline['id'])}
    cases = {c['id']:{r['question_id']:r for r in store.evaluation_case_results(c['result'].get('evaluation_run_id'))} for c in history}
    win_cases = cases.get(winner['id'], {})

    def positions(cid, qid):
        case = baseline_cases.get(qid, {}) if cid == baseline['id'] else cases.get(cid, {}).get(qid, {})
        return evidence_positions(questions.get(qid, {}), (case.get('programmatic_metrics') or {}).get('retrieval_trace') or {})

    def failed_gates(result):
        return [g for g in result.get('gates', {}).get('gates', []) if g.get('passed') is False]

    def metric(result, name):
        return result.get('metrics', {}).get(name, result.get(name))

    def delta(a, b):
        return round(a-b, 6) if type(a) in (int,float) and type(b) in (int,float) else None

    history = [c for c in history if c['status']=='evaluated' and c['reasoning'].get('candidate_label')!='D']
    remaining = sorted(q for q,c in win_cases.items() if c.get('passed') is False)
    protected = sorted(q for q,c in win_cases.items() if c.get('passed') is True)
    records = []
    for c in history:
        result = c['result']; p99 = metric(result, 'latency_p99_seconds')
        changes = parameter_diff(c['config'], base)
        fixed = sorted(q for q,r in cases[c['id']].items() if r.get('passed') is True and baseline_cases.get(q, {}).get('passed') is False)
        new = sorted(q for q,r in cases[c['id']].items() if r.get('passed') is False and baseline_cases.get(q, {}).get('passed') is True)
        records.append({'candidate_id':c['id'], 'evaluation_run_id':result.get('evaluation_run_id'),
            'config':pipeline_config(c['config']), 'parameter_diff':changes,
            'qualified':result.get('qualification', {}).get('qualified') is True,
            'fixed_question_ids':fixed, 'new_failure_question_ids':new,
            'saved_fixed_question_ids':result.get('all_fixed_question_ids', []), 'saved_new_failure_question_ids':new_failure_ids(result),
            'failed_gates':failed_gates(result),
            'gate_drops':[{'metric':g['metric'], 'baseline':metric(baseline['result'],g['metric']), 'actual':metric(result,g['metric']), 'delta':delta(metric(result,g['metric']),metric(baseline['result'],g['metric']))}
                          for g in GATE_DEFINITIONS if (delta(metric(result,g['metric']),metric(baseline['result'],g['metric'])) or 0) * (1 if g['operator']=='>=' else -1) < 0],
            'p99_seconds':p99, 'p99_change_from_baseline':delta(p99,metric(baseline['result'],'latency_p99_seconds')),
            'p99_change_from_winner':delta(p99,metric(winner['result'],'latency_p99_seconds')),
            'attribution':'多个改动混在一起，无法单独归因' if len(changes)>1 else '单参数对照，结果为伴随出现，不证明因果',
            'observation_label':'伴随出现'})
    contrasts = []
    reference = {'candidate_id':baseline['id'], 'config':base, 'fixed_question_ids':[], 'new_failure_question_ids':[], 'failed_gates':failed_gates(baseline['result']), 'p99_seconds':metric(baseline['result'],'latency_p99_seconds')}
    for a,b in combinations([reference,*records],2):
        changes = parameter_diff(a['config'], b['config'])
        if len(changes)!=1:continue
        parameter = next(iter(changes))
        contrasts.append({'id':f"{a['candidate_id']}|{b['candidate_id']}|{parameter}", 'parameter':parameter,
            'candidate_ids':[a['candidate_id'],b['candidate_id']], 'values':[a['config'][parameter],b['config'][parameter]],
            'results':[{k:r[k] for k in ('candidate_id','fixed_question_ids','new_failure_question_ids','failed_gates','p99_seconds')} for r in (a,b)],
            'evidence_positions':[{ 'question_id':q, 'positions':{r['candidate_id']:positions(r['candidate_id'],q) for r in (a,b)}} for q in sorted(set(remaining) | set(a['fixed_question_ids']) | set(b['fixed_question_ids']) | set(a['new_failure_question_ids']) | set(b['new_failure_question_ids']))],
            'note':'只有该参数不同的保存结果对照；伴随出现，不证明因果'})
    profiles = {key:[{'value':v, 'used_in':[r['candidate_id'] for r in records if type(r['config'][key]) is type(v) and r['config'][key]==v],
                        'observations':[ {k:r[k] for k in ('candidate_id','parameter_diff','fixed_question_ids','new_failure_question_ids','failed_gates','gate_drops','p99_seconds','p99_change_from_baseline','p99_change_from_winner','attribution','observation_label')} for r in records if type(r['config'][key]) is type(v) and r['config'][key]==v],
                        'contrast_ids':[c['id'] for c in contrasts if c['parameter']==key and any(type(x) is type(v) and x==v for x in c['values'])]}
                       for v in allowed] for key,allowed in ALLOWED_SEARCH_SPACE.items()}
    return {'version':'winner-refinement-1', 'winner_id':winner['id'], 'winner_config':pipeline_config(winner['config']),
        'winner_preserved_diff':parameter_diff(winner['config'],base), 'qualified_candidate_ids':[r['candidate_id'] for r in records if r['qualified']],
        'remaining_failures':[{'question_id':q, 'evidence_positions':positions(winner['id'],q),
            'historical_fixes':[{**r,'evidence_positions':positions(r['candidate_id'],q)} for r in records if cases.get(r['candidate_id'],{}).get(q,{}).get('passed') is True]} for q in remaining],
        'protected_questions':[{'question_id':q, 'winner_fixed':baseline_cases.get(q,{}).get('passed') is False,
            'historical_flips':[r['candidate_id'] for r in records if q in r['new_failure_question_ids']], 'evidence_positions':positions(winner['id'],q)} for q in protected],
        'parameter_profiles':profiles, 'history':records, 'contrasts':contrasts,
        'gate_margins':[{**g, 'actual':metric(winner['result'],g['metric']),
                         'margin':delta(metric(winner['result'],g['metric']),g['threshold']) if g['operator']=='>=' else delta(g['threshold'],metric(winner['result'],g['metric'])),
                         'unit':'秒' if 'latency' in g['metric'] else '百分点'} for g in GATE_DEFINITIONS],
        'missing_winner_cases':sorted(set(questions)-set(win_cases)), 'note':'仅保存结果；缺记录为未知，伴随出现不等于导致。'}


def validate_d_refinement(suggestion, winner, history, baseline_config, facts):
    diff = suggestion.get('proposed_config_diff')
    if not isinstance(diff,dict) or set(diff)-set(ALLOWED_SEARCH_SPACE):raise ValueError('非法Pipeline参数')
    base = pipeline_config(baseline_config)
    winner_config = pipeline_config(winner['config'])
    config = pipeline_config({**winner_config, **diff})
    effective_config = {k:v for k,v in config.items() if k!='hybrid_alpha' or config['hybrid_search'] is not False}
    if ('hybrid_alpha' in diff and config['hybrid_search'] is False) or not validate_candidate_config(effective_config)['valid']:
        raise ValueError('取值不在Pipeline ALLOWED_SEARCH_SPACE选项里，hybrid_alpha仅在混合检索开启时可选')
    changes = parameter_diff(config,winner_config)
    if len(changes)>2:raise ValueError('相对Winner最多改2个参数')
    if any(k not in effective_config or effective_config[k]!=v or type(effective_config[k]) is not type(v) for k,v in parameter_diff(winner_config,base).items()):
        raise ValueError('不得撤销或改变Winner自己的改动')
    if not changes:raise ValueError('D必须不同于Winner')
    rows = suggestion.get('changes')
    if not isinstance(rows,list) or len(rows)!=len(changes) or any(not isinstance(r,dict) for r in rows) or {r.get('parameter') for r in rows}!=set(changes):
        raise ValueError('每个改动须给changes来源标签和副作用检查')
    sources = {c['id']:c for c in history if c['status']=='evaluated' and c['result'].get('evaluation_identity')==winner['result'].get('evaluation_identity')}
    remaining = {r['question_id'] for r in facts['remaining_failures']}
    protected = {r['question_id'] for r in facts['protected_questions']}
    records=[]
    for row in rows:
        key=row['parameter'];value=config[key]
        kind={'已验证':'verified','部分取用':'partial','新尝试':'new_attempt'}.get(row.get('source_type'),row.get('source_type'))
        if kind not in {'verified','partial','new_attempt'}:raise ValueError('改动来源标签须为已验证/部分取用/新尝试')
        targets=row.get('target_question_ids')
        if not isinstance(targets,list) or not targets or not set(targets)<=remaining:raise ValueError('改动必须针对Winner剩余错题')
        if any(not isinstance(row.get(k),str) or not row[k].strip() for k in ('evidence_basis','reason')):raise ValueError('改动须说明事实表证据位置和理由')
        side=row.get('side_effect_check')
        if (not isinstance(side,dict) or any(not isinstance(side.get(k),str) or not side[k].strip() for k in ('historical_effects','winner_fixed_risk','gate_risk','mitigation'))
            or not isinstance(side.get('protected_overlap'),list)):raise ValueError('改动缺副作用检查：历史伴随现象、保护题重叠、赢家修好题、门槛及规避措施必填')
        if any(type(row.get(k)) is not int or row[k]<0 for k in ('expected_fixed_count','possible_broken_count')):raise ValueError('预期修好/可能弄坏几道须为非负整数')
        profile=next(p for p in facts['parameter_profiles'][key] if type(p['value']) is type(value) and p['value']==value)
        overlap={q for p in profile['observations'] for q in p['new_failure_question_ids']} & protected
        if not overlap<=set(side['protected_overlap']) or not set(side['protected_overlap'])<=protected:raise ValueError('副作用检查须覆盖事实表中与受保护题的重叠')
        selected=row.get('source_candidates',[])
        if not isinstance(selected,list):raise ValueError('来源须为列表')
        if kind=='new_attempt':
            if profile['used_in']:raise ValueError('新尝试必须是本实验未用过的参数取值')
            if not isinstance(row.get('why_not_verified'),str) or not row['why_not_verified'].strip():raise ValueError('新尝试须说明为什么不用已验证参数')
        else:
            if not selected or any(cid not in sources for cid in selected):raise ValueError('D来源不属于本实验同身份的保存结果')
            contrast_ids=row.get('contrast_ids',[])
            valid_contrasts=[c for c in facts['contrasts'] if c['id'] in contrast_ids and c['parameter']==key and any(type(v) is type(value) and v==value for v in c['values'])]
            if kind=='partial' and not valid_contrasts:raise ValueError('部分取用必须有真实拆分对照证据 contrast_ids')
            for cid in selected:
                source=sources[cid];source_config=pipeline_config(source['config'])
                if type(source_config[key]) is not type(value) or source_config[key]!=value:raise ValueError('来源取值与D不一致')
                record=next(r for r in facts['history'] if r['candidate_id']==cid)
                if not set(record['fixed_question_ids']) & set(targets):raise ValueError('已验证来源须曾修好针对的剩余错题')
                bundle=parameter_diff(source_config,base)
                whole=all(config[k]==v and type(config[k]) is type(v) for k,v in bundle.items())
                if not whole and (kind!='partial' or not valid_contrasts):raise ValueError('多参数来源必须整组取用；部分取用必须引用拆分对照证据')
        records.append({**row,'source_type':kind})
    return effective_config,records
