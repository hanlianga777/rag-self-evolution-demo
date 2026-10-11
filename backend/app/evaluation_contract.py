"""Versioned evidence observations; no provider or storage side effects."""
import hashlib
import json
import re
import unicodedata
from .policy import GATE_DEFINITIONS

VERSIONS = {'prompt_version': 'judge-v2-context', 'evidence_matcher_version': 'evidence-v2-parent', 'scoring_policy': 'v1.1-evidence-gates'}


def policy_current(judge):
    return all(judge.get(key) == value for key, value in VERSIONS.items())


def evaluation_identity(snapshot, judge):
    payload = {'golden': snapshot.get('id'), 'corpus': snapshot.get('corpus_fingerprint'), 'versions': {key: judge.get(key) for key in VERSIONS}, 'judge_config': {'model':judge.get('model'), 'temperature':judge.get('temperature',0), 'context':'full_final'}, 'gates': GATE_DEFINITIONS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def normalize(text):
    # Formatting only: retain signs, units and digits; no fuzzy semantic acceptance.
    text = re.sub(r'</?[A-Za-z][^>]*>', '', unicodedata.normalize('NFKC', str(text)))
    return re.sub(r'\s+', '', text)


def observe_evidence(item, entries):
    scope = {key:item.get('raw',{}).get(key) for key in ('product','product_scope','entity','version','source_reference','source_document_id','expected_response')}
    if item['test_category'] == 'negative':
        return {'status': 'not_applicable', 'source_constraints': scope, 'sufficient': None, 'facts': [], 'reason': '负向材料为Anchor，预期行为由统一Judge核验', 'version': VERSIONS['evidence_matcher_version']}
    facts = [fact.strip() for fact in re.split(r'\n|[。；]', item.get('reference_answer') or '') if fact.strip()]
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
    # A sufficient judgment must locate every required fact in actual final context.
    valid = isinstance(locations, list) and bool(locations) and all(isinstance(f, dict) and isinstance(f.get('fact'), str) and f['fact'].strip() and isinstance(f.get('quote'), str) and normalize(f['quote']) and any(normalize(f['quote']) in normalize(e.get('content', '')) and f.get('chunk_id') in {e.get('chunk_id'), e.get('parent_chunk_id')} for e in entries or []) for f in locations)
    if status == 'sufficient' and (not all(any(f.get('fact') == needed['fact'] for f in locations if isinstance(f, dict)) for needed in observation['facts']) or not valid or value.get('source_applicable') is not True or value.get('conflicts')):
        status = 'unknown'
    if value.get('conflicts') or value.get('source_applicable') is False:
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
    return {**observation, 'status': status, 'sufficient': True if status == 'sufficient' else False if status == 'insufficient' else None, 'judge_support': locations, 'source_applicable': value.get('source_applicable'), 'conflicts': value.get('conflicts', []) + source_conflicts, 'reason': value.get('reason') or 'Judge未提供可核实的充分性依据'}


def diagnosis(case):
    if case.get('diagnosis'):
        return case['diagnosis']
    return {'status': 'needs_review', 'reason': '历史评测缺少新版上下文判断，不能仅凭失败标签确证根因'}


def compare_cases(baseline, candidate, targets):
    fixed = sorted(q for q, r in baseline.items() if not r.get('passed') and candidate.get(q, {}).get('passed'))
    new = sorted(q for q, r in baseline.items() if r.get('passed') and not candidate.get(q, {}).get('passed'))
    target = sorted(set(fixed) & set(targets))
    incidental = sorted(set(fixed) - set(targets))
    return {'comparison_version': 'target-v2', 'target_bad_cases_fixed': len(target), 'target_fixed_question_ids': target, 'incidental_fixes': len(incidental), 'incidental_fixed_question_ids': incidental, 'new_regressions': len(new), 'new_regression_question_ids': new, 'net_improvement': len(fixed)-len(new), 'all_fixed_question_ids': fixed, 'critical_fixed': sum(baseline[q].get('severity') == 'critical' for q in fixed)}


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
