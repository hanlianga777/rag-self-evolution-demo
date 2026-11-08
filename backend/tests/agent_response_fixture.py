"""Explicit Agent review data for offline providers; never repairs production output."""
import json


def with_review(value, prompt):
    previous=prompt.get('prior_sandbox_results',[])
    value['prior_round_review']={'plans':[{
        'candidate_id':p['id'],'changes':json.dumps(p['changed_parameters']),
        'fixed_question_ids':p['result'].get('all_fixed_question_ids',[]),
        'new_failure_question_ids':p['result'].get('new_failure_question_ids',[]),
        'evidence_reason':'offline saved Sandbox result','conclusion':'retain each saved configuration result',
    } for p in previous], 'baseline_remaining_assessment':'offline Baseline failures remain',
        'conclusions':[{'id':'L1','conclusion':'use saved Baseline and prior round facts'}]}
    for candidate in value['candidates']:
        candidate['review_conclusion_ids']=['L1']
    return value


def with_refinement(value, prompt):
    """Bring old offline D replies up to the saved Winner-refinement contract."""
    facts = prompt['d_facts']
    remaining = {row['question_id'] for row in facts['remaining_failures']}
    changes = []
    for key, target in value.get('proposed_config_diff', {}).items():
        sources = [row for row in facts['history'] if row['config'].get(key) == target and remaining.intersection(row['fixed_question_ids'])]
        if not sources:
            value.update(should_generate_d=False, proposed_config_diff={}, changes=[], explanation='没有保存的参数能修好 Winner 剩余题，保留 Winner。')
            return value
        source = sources[0]
        changes.append({'parameter': key, 'source_type': 'verified', 'source_candidates': [source['candidate_id']],
            'reason': '沿用离线已保存修复结果', 'target_question_ids': sorted(remaining.intersection(source['fixed_question_ids'])),
            'evidence_basis': 'd_facts.history 与 remaining_failures 中的保存记录',
            'side_effect_check': {'historical_effects': '沿用保存的新增失败与门槛记录',
                'protected_overlap': [row['question_id'] for row in facts['protected_questions']],
                'winner_fixed_risk': '完整题卷验证 Winner 已修好的题', 'gate_risk': '独立核对全部 Hard Gate',
                'mitigation': '完整离线 Sandbox 后再判断资格', 'same_premise_evidence': '没有前提相同的独立对照',
                'different_premise_evidence': '来源参数与 Winner 不同，不能单独归因', 'risk_checklist': '核对保护题、新增失败与全部 Hard Gate'},
            'expected_fixed_count': len(remaining.intersection(source['fixed_question_ids'])), 'possible_broken_count': len(facts['protected_questions'])})
    value['changes'] = changes
    return value
