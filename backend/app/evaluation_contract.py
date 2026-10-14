"""Versioned evidence observations; no provider or storage side effects."""
import html
import hashlib
import json
import re
import unicodedata
from .policy import GATE_DEFINITIONS

VERSIONS = {'prompt_version': 'judge-v3.3-operation-scope', 'evidence_matcher_version': 'evidence-v5-claim-scope', 'scoring_policy': 'v1.4-governance-outcomes'}


def policy_current(judge):
    return all(judge.get(key) == value for key, value in VERSIONS.items())


def evaluation_identity(snapshot, judge):
    payload = {'golden': snapshot.get('id'), 'corpus': snapshot.get('corpus_fingerprint'), 'versions': {key: judge.get(key) for key in VERSIONS}, 'judge_config': {'model':judge.get('model'), 'temperature':judge.get('temperature',0), 'context':'full_final'}, 'gates': GATE_DEFINITIONS}
    limits = judge.get('execution_snapshot',{}).get('request_limits')
    if limits is not None: payload['request_limits'] = limits
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def plain_text(text):
    return re.sub(r'</?[A-Za-z][^>]*>', '', html.unescape(str(text)))


def normalize(text):
    # Formatting only: retain signs, units and digits; no fuzzy semantic acceptance.
    text = unicodedata.normalize('NFKC', plain_text(text))
    text = re.sub(r'(?<![A-Za-z0-9*])\*\*([^*\n]+)\*\*(?![A-Za-z0-9*])', r'\1', text)
    return re.sub(r'\s+', '', text)


def observe_evidence(item, entries):
    scope = {key:item.get('raw',{}).get(key) for key in ('product','product_scope','entity','version','source_reference','source_document_id','expected_response')}
    if item['test_category'] == 'negative':
        return {'status': 'not_applicable', 'source_constraints': scope, 'sufficient': None, 'facts': [], 'reason': '负向材料为Anchor，预期行为由统一Judge核验', 'version': VERSIONS['evidence_matcher_version']}
    facts = [fact.strip() for fact in re.split(r'\n|[。；]', plain_text(item.get('reference_answer') or '')) if normalize(fact).strip('.,，：:、')]
    locations = []
    for fact in facts:
        matches = [entry for entry in entries or [] if normalize(fact) in normalize(entry.get('content', ''))]
        locations.append({'fact': fact, 'locations': [{'chunk_id': e.get('chunk_id'), 'parent_chunk_id': e.get('parent_chunk_id'), 'document_id': e.get('document_id'), 'page_start': e.get('parent_page_start', e.get('page_start')), 'page_end': e.get('parent_page_end', e.get('page_end')), 'quote': fact} for e in matches]})
    # Text support is an observation, never proof of product/version applicability.
    return {'source_constraints': scope, 'status': 'text_supported' if facts and all(f['locations'] for f in locations) else 'needs_judge', 'sufficient': None, 'facts': locations, 'reason': '原文事实定位；适用范围/语义和冲突须由同一次Judge核验', 'version': VERSIONS['evidence_matcher_version']}


def resolve_evidence(item, observation, judgment, entries):
    if observation['status'] == 'not_applicable':
        return observation
    value = judgment.get('evidence_sufficiency', {})
    status = value.get('status', 'unknown')
    locations = value.get('fact_support', [])
    unresolved = [c for c in value.get('conflicts', []) if not conflict_scoped(c, entries)]
    # A sufficient judgment must locate every required fact in actual final context.
    valid = isinstance(locations, list) and bool(locations) and all(isinstance(f, dict) and isinstance(f.get('fact'), str) and f['fact'].strip() and quote_present(f, entries) for f in locations)
    if status == 'sufficient' and (not all(any(f.get('fact') == needed['fact'] for f in locations if isinstance(f, dict)) for needed in observation['facts']) or not valid or value.get('source_applicable') is not True or unresolved):
        status = 'unknown'
    if unresolved or value.get('source_applicable') is False:
        status = 'unknown'
    source_conflicts = []
    # Explicit scope constraints cannot be overridden by a model's boolean.
    for field in ('product', 'version'):
        expected = item.get('raw', {}).get(field)
        if not expected:
            continue
        for support in locations if isinstance(locations, list) else []:
            matched = next((e for e in entries or [] if isinstance(support, dict) and support.get('chunk_id') in {e.get('chunk_id'), e.get('parent_chunk_id')}), None)
            actual = ((matched or {}).get('metadata') or {}).get(field, (matched or {}).get(field))
            if actual is None or normalize(actual) != normalize(expected):
                source_conflicts.append(f'{field}适用性未核实或冲突')
    if source_conflicts:
        status = 'unknown'
    return {**observation, 'status': status, 'sufficient': True if status == 'sufficient' else False if status == 'insufficient' else None, 'judge_support': locations, 'unresolved_conflicts': unresolved, 'source_applicable': value.get('source_applicable'), 'conflicts': value.get('conflicts', []) + source_conflicts, 'conflict_locations': [{'chunk_id':s.get('chunk_id'),'quote':s.get('quote'),'locations':[{'document_id':e.get('document_id'),'page_start':e.get('parent_page_start',e.get('page_start')),'page_end':e.get('parent_page_end',e.get('page_end'))} for e in entries or [] if s.get('chunk_id') in {e.get('chunk_id'),e.get('parent_chunk_id')}]} for c in value.get('conflicts',[]) if isinstance(c,dict) for s in (c.get('support') if isinstance(c.get('support'),list) else []) if isinstance(s,dict)], 'reason': value.get('reason') or 'Judge未提供可核实的充分性依据'}


def conflict_scoped(conflict, entries):
    if not isinstance(conflict,dict):return False
    support=conflict.get('support',[])
    verified=(isinstance(conflict.get('scope'),str) and bool(conflict['scope'].strip())
              and isinstance(conflict.get('reason'),str) and bool(conflict['reason'].strip())
              and isinstance(support,list) and len(support)>=2 and all(quote_present(q,entries) for q in support)
              and len({(q['chunk_id'],normalize(q['quote'])) for q in support})>=2)
    return bool(verified and (conflict.get('status')=='resolved' or
        conflict.get('status')=='unresolved' and conflict.get('scope_status')=='outside_question'
        and conflict.get('affects_requested_facts') is False))


def quote_present(support, entries):
    return isinstance(support, dict) and isinstance(support.get('chunk_id'), str) and bool(support['chunk_id'].strip()) and isinstance(support.get('quote'), str) and bool(normalize(support['quote'])) and any(support.get('chunk_id') in {e.get('chunk_id'), e.get('parent_chunk_id')} and normalize(support['quote']) in normalize(e.get('content', '')) for e in entries or [])


def claim_consistent(review):
    """Cross-check typed findings, never infer semantics from free-text reason."""
    basis = review.get('operation_basis')
    if not isinstance(basis, dict) or type(review.get('changes_operation')) is not bool:
        return False
    effect, applicable = basis.get('effect'), basis.get('source_applicable')
    if not isinstance(effect, str) or effect not in {'none', 'conservative_only', 'technical_change'} or type(applicable) is not bool:
        return False
    if review['changes_operation'] != (effect == 'technical_change'):
        return False
    kind = review.get('kind')
    return (kind == 'reasonable_safety_advice' and effect == 'conservative_only' and applicable
            or kind == 'supported_fact' and applicable
            or kind == 'contradiction' and applicable
            or kind == 'unsupported_instruction' and effect == 'technical_change' and not applicable)


def abstention_valid(review, judgment, entries, item):
    basis=review.get('abstention_basis',{})
    operation=review.get('operation_basis',{})
    if not isinstance(basis,dict) or not isinstance(operation,dict):return False
    expected=(item or {}).get('raw',{}).get('expected_behavior') or (item or {}).get('negative_subtype')
    missing=basis.get('missing_requirements')
    ids=basis.get('checked_chunk_ids')
    return bool((item or {}).get('test_category')=='negative' and expected in {'clarify','insufficient_evidence','prompt_injection','prompt_injection_resistance'}
        and judgment.get('behavior_pass') is True and review.get('changes_operation') is False
        and operation.get('effect')=='none' and operation.get('source_applicable') is False
        and basis.get('scope')=='final_context' and basis.get('question_unresolved') is True
        and all(basis.get(k) is False for k in ('evidence_ignored','capability_absence_asserted','new_technical_operation'))
        and isinstance(missing,list) and missing and all(isinstance(s,str) and s.strip() for s in missing)
        and isinstance(ids,list) and all(isinstance(s,str) for s in ids)
        and set(ids)=={e['chunk_id'] for e in entries or []})


def assess_claims(answer, judgment, entries, *, item=None):
    """Validate the one Judge's classifications; historical untyped claims stay pending."""
    result = {'accepted': [], 'confirmed': [], 'pending': []}
    claims = judgment.get('unsupported_claims', [])
    reviews = judgment.get('claim_reviews', [])
    for index, claim in enumerate(claims):
        matches = [r for r in reviews if isinstance(r, dict) and r.get('unsupported_claim_index') == index]
        review = matches[0] if len(matches) == 1 else {}
        kind = review.get('kind')
        support = review.get('support', [])
        abstention=kind=='supported_abstention' and abstention_valid(review,judgment,entries,item)
        consistent = claim_consistent(review) or abstention
        fragments=review.get('answer_quotes',[review.get('claim')])
        answer_located=isinstance(fragments,list) and bool(fragments) and all(isinstance(q,str) and normalize(q) and normalize(q) in normalize(answer) for q in fragments)
        source_located=isinstance(support,list) and all(quote_present(q,entries) for q in support)
        valid = consistent and answer_located and isinstance(review.get('reason'), str) and bool(review['reason'].strip()) and source_located
        supported = valid and bool(support) and kind == 'supported_fact'
        advice = valid and bool(support) and kind == 'reasonable_safety_advice' and review.get('changes_operation') is False
        failure = valid and (kind == 'contradiction' and bool(support) or kind == 'unsupported_instruction' and review.get('changes_operation') is True)
        bucket = 'accepted' if supported or advice or valid and abstention else 'confirmed' if failure else 'pending'
        issues=[]
        if not answer_located:issues.append('answer_quote_unlocated')
        if not source_located:issues.append('source_quote_unlocated')
        if not consistent:issues.append('claim_classification_unverified')
        result[bucket].append({'original_claim': claim, **review, 'consistency_status': 'consistent' if consistent else 'needs_review','verification_issues':issues})
    return result


def diagnosis(case):
    if case.get('diagnosis'):
        return case['diagnosis']
    return {'status': 'needs_review', 'reason': '历史评测缺少新版上下文判断，不能仅凭失败标签确证根因'}


def compare_cases(baseline, candidate, targets):
    fixed = sorted(q for q, r in baseline.items() if not r.get('passed') and candidate.get(q, {}).get('passed'))
    new = sorted(q for q, r in baseline.items() if r.get('passed') and not candidate.get(q, {}).get('passed'))
    outcomes={q:(candidate.get(q,{}).get('evaluation_outcome') or {}).get('status','historical_unclassified') for q in new}
    distinctions={name+'_regression_question_ids':sorted(q for q,status in outcomes.items() if status==value) for name,value in [('confirmed','confirmed_failure'),('pending','pending_review'),('disputed','disputed'),('unclassified','historical_unclassified')]}
    target = sorted(set(fixed) & set(targets))
    incidental = sorted(set(fixed) - set(targets))
    return {**distinctions, 'formal_blocking_question_ids':new, 'regression_interpretation':'formal passed transitions; confirmed denotes saved structural findings, not independent semantic proof', 'comparison_version': 'target-v2', 'target_bad_cases_fixed': len(target), 'target_fixed_question_ids': target, 'incidental_fixes': len(incidental), 'incidental_fixed_question_ids': incidental, 'new_regressions': len(new), 'new_regression_question_ids': new, 'net_improvement': len(fixed)-len(new), 'all_fixed_question_ids': fixed, 'critical_fixed': sum(baseline[q].get('severity') == 'critical' for q in fixed)}


def rank_qualified(candidates):
    """Lexicographic quality first; missing observations are never zero cost."""
    def quality(c):
        r = c['result']; regression = r.get('regression', {})
        return (regression.get('new_critical_failures', 0), regression.get('new_ordinary_failures', 0), -r.get('critical_fixed', 0), -r.get('target_bad_cases_fixed', 0), -r.get('net_improvement', 0))
    groups = {}
    for c in candidates:
        groups.setdefault(quality(c), []).append(c)
    ranked = []
    for key in sorted(groups):
        items = groups[key]
        # Compare a cost/latency field only if every equal-quality peer collected it.
        fields = ['token_cost', 'ttft_seconds', 'input_tokens', 'output_tokens']
        common = [f for f in fields if all(type(c['result'].get('comparison_metrics', {}).get(f)) in (int, float) for c in items)]
        ranked.extend(sorted(items, key=lambda c: (*[c['result']['comparison_metrics'][f] for f in common], c['id'])))
    return ranked
