"""Synthetic frozen business standards and explicit Judge replies; never Provider evidence."""
from app.scoring_contract import snapshot_manifest


def business_requirements(item, chunks):
    negative = item['test_category'] == 'negative'
    by_id = {c['chunk_id']: c for c in chunks}
    keys = [key for evidence in item.get('evidence', []) for key in evidence.get('source_chunk_ids', [])]
    text = '证据不足时拒绝猜测或执行未获授权的操作' if negative else item['reference_answer']
    return {
        'fixture_only': True,
        'required_checks': [{'id':'R1', 'requirement':text, 'source_chunk_ids':[] if negative else keys,
                             **({'basis':'instruction_boundary'} if negative else {})}],
        'conditional_checks': [], 'auxiliary_information': [], 'prohibited': [], 'acceptable_equivalents': [],
        'sources': [] if negative else [{'chunk_id':key, 'document_id':by_id[key]['document_id'],
                    'quote':by_id[key]['chunk_text'], 'role':'canonical_norm'} for key in keys],
        'answer_support': [] if negative else [{'answer_line':item['reference_answer'], 'source_chunk_ids':keys}],
    }


def bind_snapshot(snapshot, chunks):
    for item in snapshot['questions']:
        item['business_requirements'] = business_requirements(item, chunks)
    snapshot['scoring_contract_manifest'] = snapshot_manifest(snapshot)
    return snapshot


def atomic_judgment(context, answer, passed):
    """A fixture oracle checks its injected answer, not a model's claimed overall verdict."""
    negative = context['category'] == 'negative'
    final = context['final_context']
    support = [] if negative or not final else [{'source_id':final[0]['chunk_id'], 'quote':final[0]['content']}]
    return {'verdict':'PASS' if passed else 'FAIL',
        'checks':[{'check_type':'negative_behavior' if negative else 'fact',
                   'requirement':context['scoring_contract']['requirements'][0]['original_text'],
                   'met':passed, 'answer_quotes':[answer] if passed else [], 'support':support}],
        'atomic_results':[{'atomic_id':r['atomic_id'], 'check_type':'negative_behavior' if negative else 'fact', 'state':'MET' if passed else 'NOT_MET',
                           'reason':'Explicit offline answer fault injection', 'answer_quotes':[answer] if passed else [],
                           'support':support} for r in context['scoring_contract']['requirements']],
        'issues':[], 'reason':'Explicit offline fixture; no real Provider acceptance',
        'quality':{'correctness':4 if passed else 0, 'faithfulness':1, 'completeness':1 if passed else 0}}
