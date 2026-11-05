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
