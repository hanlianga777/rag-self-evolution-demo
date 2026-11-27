"""126b claim coverage over frozen annotations and the saved retrieval trace."""
import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from . import rules, verdict
from .diagnostic_categories import category_definition
from .diagnostics import _has_required_omission, _saved_verdict

VERSION = '126b'
ANNOTATIONS = Path(__file__).resolve().parents[2] / '指挥/报告/126b-证据角色表.csv'
NECESSARY = {'required', 'condition', 'equivalent'}
NOT_PRESENT = '未进入'
UNKNOWN = '待确认'
NEGATIVE_TYPES = {'insufficient_evidence': '资料不足', 'clarify': '需追问',
                  'safety_critical': '安全关键', 'prompt_injection': '提示注入'}


def literal(value):
    """Ignore layout and column delimiters while preserving numeric signs and units."""
    normalized = unicodedata.normalize('NFKC', value).lower().translate(
        str.maketrans({'–': '-', '−': '-', '—': '-'}))
    return ''.join(c for c in normalized if c.isalnum() or c in '+-.%<>±')


def question_fingerprint(question):
    values = [question.get(field) for field in ('id', 'question', 'reference_answer', 'expected_behavior',
              'test_category', 'question_subtype', 'negative_subtype', 'evidence', 'negative_basis')]
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@lru_cache(maxsize=1)
def annotations():
    groups = defaultdict(lambda: defaultdict(list))
    if ANNOTATIONS.is_file():
        with ANNOTATIONS.open(encoding='utf-8-sig', newline='') as source:
            for row in csv.DictReader(source):
                if row['diagnosis_version'] == VERSION:
                    groups[row['dataset_id']][row['question_id']].append(row)
    return groups


def version_for(baseline, requested=None):
    if requested:
        return requested
    return VERSION if baseline and baseline.get('dataset_version_id') in annotations() else '122f'


def stage_entries(trace, stage):
    rows = trace.get(stage)
    if not isinstance(rows, list) or trace.get('status') not in (None, 'completed'):
        return None
    entries = []
    for row in rows:
        if not isinstance(row, dict):
            entries.append((set(), None, ''))
            continue
        source = row.get('chunk_id') or row.get('parent_chunk_id')
        scope = {source, row.get('parent_chunk_id'), *(row.get('matched_child_ids') or [])} - {None, ''}
        # The saved Final content is the delivered parent or truncated excerpt.
        # Its child_content and matched IDs only describe the retrieval match.
        body = row.get('content') or row.get('chunk_text') or row.get('text')
        entries.append((scope, source, literal(body) if isinstance(body, str) else ''))
    return entries


def locate(sources, entries):
    if entries is None or not sources:
        return UNKNOWN, None
    incomplete = False
    for index, (scope, chunk, body) in enumerate(entries, 1):
        for expected_scope, match in sources:
            if scope and scope.isdisjoint(expected_scope):
                continue
            if not scope or not body:
                incomplete = True
            elif match in body:
                return index, chunk
    return (UNKNOWN if incomplete else NOT_PRESENT), None


def claim_coverage(rows, trace):
    claims = defaultdict(list)
    for row in rows:
        if row['role'] in NECESSARY:
            claims[row['claim_id']].append(row)
    stages = {stage: stage_entries(trace, stage) for stage in ('candidates', 'reranked', 'final')}
    coverage = []
    for claim_id, bindings in claims.items():
        sources = [row for row in bindings if row['chunk_id'] and row['match_text']]
        if len(bindings) > 1 and not all(row['role'] == 'equivalent' and row['equivalent_group'] == claim_id for row in bindings):
            sources = []
        matches = [({row['chunk_id'], row.get('parent_chunk_id')} - {None, ''}, literal(row['match_text']))
                   for row in sources]
        claim = {'claim_id': claim_id, 'claim': bindings[0]['claim'],
                 'source_chunk_ids': list(dict.fromkeys(row['chunk_id'] for row in sources))}
        for stage, entries in stages.items():
            position, chunk_id = locate(matches, entries)
            claim.update({stage: position, f'{stage}_chunk_id': chunk_id})
        coverage.append(claim)
    return coverage


def describe(claim):
    ids = '、'.join(claim['source_chunk_ids'])
    return f'“{claim["claim"]}”' + (f'（{ids}）' if ids else '')


def generation_subtype(case, question, judge, issues):
    if (judge.get('over_refusal') is True or question.get('test_category') != 'negative'
            and judge.get('answer_behavior') in {'refusal', 'abstention'}):
        return 'over_refuse', '过度拒答'
    reason = ' '.join(judge.get(key) or '' for key in ('reason', 'correctness_reason', 'completeness_reason', 'behavior_reason'))
    if question.get('negative_subtype') == 'clarify' and (
            any(i.get('failure_kind') in {'clarification_missing', 'missing_clarification'} for i in issues)
            or re.search(r'未(?:先|能)?(?:追问|澄清|询问)|应(?:先)?(?:追问|澄清|询问)', reason)):
        return 'generation', '该追问没追问'
    if (question.get('question_subtype') == '表格统计' or any('表格' in (i.get('reason') or '') for i in issues)):
        if re.search(r'计数|归类|第[一二三四五六七八九十\d]+列|表格.{0,12}(?:错误|错读|误读)', reason) or any(
                i.get('failure_kind') in {'contradiction', 'unsupported', 'table_error'} for i in issues):
            return 'generation', '表格理解错'
    if (any(i.get('failure_kind') == 'omission' for i in issues)
            or _has_required_omission(case, question, judge)
            or re.search(r'漏答|漏掉|遗漏|未覆盖|未提及|未答出|未回答', judge.get('completeness_reason') or '')):
        return 'generation', '漏要点'
    return 'generation', UNKNOWN


def diagnose(case, question, rows, gates):
    """Classify a saved failure independently of Golden scoring and old diagnoses."""
    question = question or {}
    negative = question.get('negative_subtype')
    subtype = question.get('question_subtype')
    question_type = ('负向 · ' + NEGATIVE_TYPES.get(negative, negative) if negative else subtype) or UNKNOWN
    result = {'diagnosis_version': VERSION, 'question_type': question_type, 'claim_coverage': []}

    def conclude(code, detail, reason):
        layer, severity = rules.BAD_CASE_TYPES.get(code, (None, '未知'))
        label = {'retrieval': '检索层问题', 'generation': '生成层问题',
                 'safety': '安全边界问题', 'performance': '性能问题'}.get(layer)
        return {**result, 'code': code, 'layer': layer, 'stage': detail, 'subtype': detail,
                'severity': severity, 'reason': reason,
                'repair_hint': category_definition(label).get('repair_hint')}

    judge = case.get('judge_result') or {}
    if (case.get('technical_error') or case.get('final_failure_reason') == verdict.JUDGE_TECHNICAL_FAILURE
            or _saved_verdict(case) != 'FAIL'):
        return conclude('unknown', UNKNOWN, '没有有效的保存判错记录。')
    fingerprint = question_fingerprint(question)
    if not rows or any(row['question_sha256'] != fingerprint for row in rows):
        return conclude('unknown', UNKNOWN, '没有与该冻结题目匹配的 126b 证据角色标注。')
    issues = [issue for issue in judge.get('issues') or [] if isinstance(issue, dict)]
    reason = judge.get('reason') or judge.get('behavior_reason') or judge.get('correctness_reason') or ''
    answer = case.get('model_answer')
    if not isinstance(answer, str) or not answer.strip() or not judge:
        return conclude('unknown', UNKNOWN, '缺少保存的回答或 Judge 记录。')
    trace = (case.get('programmatic_metrics') or {}).get('retrieval_trace') or {}
    coverage = claim_coverage(rows, trace)
    result['claim_coverage'] = coverage
    if verdict.has_safety_violation(judge) or any(i.get('safety_violation') is True for i in issues):
        return conclude('safety_violation', '安全越界', '保存的 Judge 记录标出了安全越界。' + reason)

    undelivered = [claim for claim in coverage if type(claim['final']) is not int]
    recall = [claim for claim in undelivered if claim['candidates'] == claim['final'] == NOT_PRESENT]
    if recall:
        return conclude('recall', '没检索到', '候选池和 Final 均缺少' + '、'.join(map(describe, recall)) + '的证据。')
    if any(UNKNOWN in (claim['candidates'], claim['final']) for claim in undelivered):
        missing = [claim for claim in undelivered if UNKNOWN in (claim['candidates'], claim['final'])]
        return conclude('unknown', UNKNOWN, '保存记录不足以定位' + '、'.join(map(describe, missing)) + '的证据。')
    if undelivered:
        locations = []
        for claim in undelivered:
            location = f"{describe(claim)}在候选第 {claim['candidates']} 位"
            if type(claim['reranked']) is int:
                location += f"、重排第 {claim['reranked']} 位"
            elif claim['reranked'] == NOT_PRESENT:
                location += '，重排记录里无此证据'
            locations.append(location + '，未进入 Final。')
        return conclude('ranking', '找到但没交给模型', ''.join(locations))

    limit = next((g.get('threshold') for g in gates if g.get('metric') == 'latency_p99_seconds'), None)
    latency = (case.get('programmatic_metrics') or {}).get('latency_ms')
    if (any(i.get('failure_kind') in {'latency', 'timeout'} for i in issues)
            and type(latency) in (int, float) and type(limit) in (int, float) and latency > limit * 1000):
        return conclude('performance', '慢', f'保存的耗时为 {latency / 1000:g} 秒，超过 {limit:g} 秒门槛。')

    code, detail = generation_subtype(case, question, judge, issues)
    if not coverage and (not negative or detail == UNKNOWN):
        return conclude('unknown', UNKNOWN, '缺少可用于确认根因的证据或明确的行为判分。')
    delivered = '、'.join(f"{describe(claim)}在 Final 第 {claim['final']} 位" for claim in coverage)
    basis = delivered + '。' if delivered else '该题的保存记录只支持核对回答行为。'
    judge_reason = reason or judge.get('completeness_reason')
    return conclude(code, detail, basis + (f'保存判分指出：{judge_reason}' if judge_reason else '保存判分仍为错。'))


def faults(baseline, cases, question_ids):
    snapshot = json.loads((baseline or {}).get('dataset_snapshot_json') or '{}')
    questions = {q['id']: q for q in snapshot.get('questions', [])}
    roles = annotations().get((baseline or {}).get('dataset_version_id'), {})
    gates = ((baseline or {}).get('result', {}).get('gates') or {}).get('gates') or []
    return {case['question_id']: diagnose(case, questions.get(case['question_id']), roles.get(case['question_id']), gates)
            for case in cases if case['question_id'] in question_ids}
