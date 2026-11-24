"""Read-only explanation of saved evidence; never rescore or rewrite a Run."""
import re

from .evaluation_contract import normalize
from .read_view import memoized_view, read_once
from .diagnostic_categories import (DIAGNOSTIC_CATEGORIES, GENERATION_SUBTYPES, MISSED_SUBQUESTION,
                                    TABLE_ERROR, WRONG_DENIAL, category_definition)

TYPICAL = tuple(row['label'] for row in DIAGNOSTIC_CATEGORIES)
@memoized_view
def _current_corpus(trace, *, historical=False):
    """Read persisted chunks only after their manifest/source identities are verified."""
    import hashlib
    import json
    from .corpus import INDEX_DIR, current_manifest, manifest_identity
    from .full_text import CORPUS_LOCK
    try:
        with CORPUS_LOCK:
            path=INDEX_DIR
            target=trace.get('corpus_fingerprint')
            if historical and target:
                from .knowledge_pipeline import index_for_config
                path=index_for_config(INDEX_DIR, {'knowledge_identity': target} if isinstance(target,dict) and target.get('pipeline_version_id') else {})
            manifest=json.loads((path/'manifest.json').read_text())
            identity=manifest_identity(manifest)
            if not target or target!=identity or (not historical and identity!=manifest_identity(current_manifest())):
                return [], None
            artifacts={name:(path/name).read_bytes() for name in ('chunks.json','parents.json')}
            if any(manifest.get('artifacts',{}).get(name)!=hashlib.sha256(raw).hexdigest() for name,raw in artifacts.items()):
                return [], None
            parents={p['chunk_id']:p for p in json.loads(artifacts['parents.json'])}
            return [{**c,'canonical_parent':parents.get(c.get('parent_chunk_id'))} for c in json.loads(artifacts['chunks.json'])], identity
    except (OSError, ValueError, KeyError):
        return [], None


def _canonical_final(trace, by_id):
    """A saved semantic Judge applies only to complete, unchanged source context."""
    for entry in trace['final']:
        child=by_id.get(entry.get('chunk_id'))
        if not child:return False
        canonical=child.get('canonical_parent') if trace.get('parent_expand') else child
        if not canonical or entry.get('content')!=(canonical.get('chunk_text') or canonical.get('text')):
            return False
        if trace.get('parent_expand') and canonical.get('chunk_id')!=entry.get('parent_chunk_id'):
            return False
        if any(entry.get(k)!=child.get(k) or canonical.get(k)!=child.get(k) for k in ('document_id','product','version')):
            return False
        if entry.get('source_scope'):
            from .ai_service import attach_heading_scopes
            if attach_heading_scopes([entry],list(by_id.values()))[0].get('source_scope') != entry['source_scope']:return False
    return True


def _text(value):
    """Compare literal source text after whitespace/punctuation normalization."""
    import unicodedata
    if not isinstance(value, str):
        return ''
    return read_once(('normalized_text', value), lambda: ''.join(c.lower() for c in unicodedata.normalize('NFKC', value) if c.isalnum()))


def standard_evidence(item):
    """Read standard source quotations from the saved question, never the live KB."""
    item = item or {}
    if 'standard_evidence' in item:
        return item['standard_evidence'] if isinstance(item['standard_evidence'], list) else []
    raw = item.get('raw') or {}
    locations = item.get('evidence_locations') or raw.get('evidence_locations') or []
    if locations:
        return [entry.get('quote', '') if isinstance(entry, dict) else '' for entry in locations]
    evidence = item.get('evidence') or item.get('acceptable_evidence') or raw.get('evidence') or raw.get('acceptable_evidence') or []
    if evidence:
        quotes = []
        for entry in evidence:
            if not isinstance(entry, dict):
                quotes.append('')
            elif 'quote' in entry:
                quotes.append(entry['quote'])
            else:
                points = entry.get('evidence_key_points')
                quotes.extend(points if isinstance(points, list) and points else [''])
        return quotes
    requirements = item.get('business_requirements') or raw.get('business_requirements') or {}
    return [source.get('quote', '') for source in requirements.get('sources', [])]


def unmet_required_points(case, question=None):
    """Read saved required atomic outcomes by ID, never rescore paraphrased checks."""
    question = question or {}
    requirements = (question.get('business_requirements') or (question.get('raw') or {}).get('business_requirements') or {}).get('required_checks')
    judge = case.get('judge_result') or {}
    if requirements and all(r.get('id') for r in requirements) and judge.get('atomic_results'):
        atoms = {a.get('atomic_id'): a for a in judge['atomic_results']}
        if all(atoms.get(r['id'], {}).get('state') in {'MET', 'NOT_MET'} for r in requirements):
            return [r['requirement'] for r in requirements if atoms[r['id']]['state'] == 'NOT_MET']
        return '记录缺失：必答要点的原子判分状态不完整'
    checks = judge.get('checks')
    if not isinstance(checks, list) or any(not isinstance(c, dict) or type(c.get('met')) is not bool or not c.get('requirement') for c in checks):
        return '记录缺失：未保存完整的要点判分记录'
    names = {r.get('requirement') for r in requirements} if isinstance(requirements, list) else None
    if names and not names.issubset({c['requirement'] for c in checks}):
        return '记录缺失：必答要点与判分文字无法对应，且没有完整的原子编号判分'
    return [c['requirement'] for c in checks if c['met'] is False and
            (c['requirement'] in names if names is not None else c.get('check_type') not in {'auxiliary', 'optional'})]


_SOURCE_DENIAL = re.compile(
    r'(?:说明书|资料|材料|文档|手册|上下文).{0,12}?'
    r'(?:没有(?:给出|提供|说明|提到|提及|列出|包含|找到|记录)?'
    r'|未(?:给出|提供|说明|提到|提及|列出|包含|找到|记录)|没(?:给出|提到))\s*(?P<object>.*)'
)
_REFUSAL = re.compile(r'无法确认|不能确认|不能回答|无法回答|无法提供|无法确定')
_CITATION = re.compile(r'\[\d+(?:\s*[,，、]\s*\d+)*\]')
_LIST_PREFIX = re.compile(r'^\s*(?:[-*•#]+\s*|\d+[.、)）]\s*)')


def _document_denial(answer, final_texts):
    """Distinguish a denial in an otherwise substantive answer from a refusal."""
    clauses = [_LIST_PREFIX.sub('', clause.strip()).strip() for clause in
               re.split(r'[。！？!?；;，,\n]+', _CITATION.sub('', answer))
               if not re.match(r'\s*#{1,6}\s', clause)
               and not re.fullmatch(r'\s*\*\*.+?\*\*\s*[:：]?\s*', clause)]
    denials = [match for clause in clauses if (match := _SOURCE_DENIAL.search(clause))]
    if not denials:
        return False, bool(_REFUSAL.search(_text(answer)))
    substantive = any(_text(clause) and not clause.endswith((':', '：')) and clause not in {'您好', '你好'}
                      and not _SOURCE_DENIAL.search(clause) and not _REFUSAL.search(_text(clause))
                      and not re.match(r'^(?:建议|请|可)[您先]*(?:联系|咨询|询问|查阅|参阅)|^抱歉', clause)
                      for clause in clauses)
    if not substantive:
        return False, True
    for match in denials:
        denied = match['object'].strip(' *:：')
        quoted = re.match(r'[“「『"]([^”」』"]+)[”」』"]', denied)
        subject = _text(quoted[1] if quoted else re.sub(
            r'(?:的(?:具体|详细|相关)?(?:操作步骤|操作方法|步骤|方法|流程|说明|信息|数据|数值|参数|要求|规定))$', '', denied))
        if len(subject) >= 2 and any(subject in text for text in final_texts):
            return True, False
    return False, False


def _has_required_omission(case, golden, judge):
    reference = case.get('reference_answer') or golden.get('reference_answer') or (golden.get('raw') or {}).get('reference_answer') or ''
    points = [_LIST_PREFIX.sub('', line).strip() for line in reference.splitlines()]
    optional = [_text(point) for point in points if point.startswith(('（补充）', '(补充)'))]
    missing = unmet_required_points(case, golden)
    if isinstance(missing, list):
        answered_checks = {_text(c.get('requirement')) for c in judge.get('checks') or []
                           if isinstance(c, dict) and c.get('met') is False and c.get('answer_quotes')}
        return any(point and point not in answered_checks and not point.startswith('补充')
                   and not any(point in extra for extra in optional) for point in map(_text, missing))
    # Rubric records may have no structured check. Require an explicit omission
    # that can be located in a required reference point.
    required = [_text(point) for point in points if _text(point) and _text(point) not in optional]
    reason = judge.get('completeness_reason') or judge.get('reason') or ''
    for detail in re.findall(r'(?:遗漏|漏答|漏掉|未回答|未提及|未列出|未覆盖)了?([^。；;]+)', reason):
        mentions = re.findall(r'[“「『"]([^”」』"]+)[”」』"]', detail)
        if any(_text(point) and any(_text(point) in item for item in required)
               and not any(_text(point) in extra for extra in optional) for point in mentions):
            return True
        if any(point in _text(detail) and not any(point in extra for extra in optional) for point in required):
            return True
    return False


def _saved_verdict(case):
    if type(case.get('final_passed')) is bool:
        return 'PASS' if case['final_passed'] else 'FAIL'
    outcome = case.get('evaluation_outcome') or {}
    if (outcome.get('verdict') not in {None, 'PASS', 'FAIL'} or outcome.get('execution_complete') is False
            or outcome.get('status') in {'technical_execution_failure', 'not_evaluable', 'NOT_EVALUABLE', 'error'}):
        return None
    if outcome.get('verdict') in {'PASS', 'FAIL'}:
        return outcome['verdict']
    judge = case.get('judge_result') or {}
    if judge.get('verdict') in {'PASS', 'FAIL'}:
        return judge['verdict']
    if type(case.get('passed')) is bool:
        return 'PASS' if case['passed'] else 'FAIL'
    return None


def _scoped_evidence_checks(trace, bindings, stage_gaps):
    from .evidence_equivalence import stage_matches

    candidates = trace.get('candidates')
    merged = [copy for row in candidates if isinstance(row, dict)
              for copy in row.get('same_text_copies', [])] if isinstance(candidates, list) else []
    cutoff = [{'chunk_id': key} for key in (trace.get('candidate_dedup') or {}).get('cutoff_chunk_ids', [])]
    relevant_ranks = set()
    checks = []
    for index, binding in enumerate(bindings, 1):
        required = binding['chunk_ids']
        check = {'evidence_index': index, 'quote': binding['quote']}
        for stage, key in (('candidate', 'candidates'), ('rerank', 'reranked'), ('final', 'final')):
            rows = trace.get(key)
            matches = stage_matches(trace, rows, required) if isinstance(rows, list) else []
            ranks = [rank for rank, match in enumerate(matches, 1) if match['matched_chunk_ids']]
            check[f'{stage}_rank'] = (ranks[0] if ranks else None) if isinstance(rows, list) else '记录缺失'
            check[f'{stage}_hit'] = bool(ranks) if required and isinstance(rows, list) and not stage_gaps.get(key) else None
            check[f'{stage}_other_source_ids'] = sorted({key for match in matches for key in match['other_source_ids']})
            if stage == 'final':
                relevant_ranks.update(ranks)
        for stage, rows in (('merged', merged), ('cutoff', cutoff)):
            check[f'{stage}_strict_source_ids'] = sorted({
                key for match in stage_matches(trace, rows, required) for key in match['strict_source_ids']})
        checks.append(check)
    return checks, sorted(relevant_ranks)


def automatic_analysis(case, *, golden_item=None, corpus_chunks=None, corpus_fingerprint=None):
    """Task 004: deterministic saved-text diagnosis, with no scoring, writes or KB reads.

    corpus_* remain accepted for callers of earlier versions but are not consulted.
    Retrieval metrics are ratios in [0, 1], diagnostics only, never Hard Gates.
    """
    metrics = case.get('programmatic_metrics') or {}
    trace = metrics.get('retrieval_trace') or {}
    judge = case.get('judge_result') or {}
    golden = golden_item or case.get('golden_item') or {}
    quotes = standard_evidence(case) if 'standard_evidence' in case else standard_evidence(golden or case)
    normalized = [_text(q.get('quote', '') if isinstance(q, dict) else q) for q in quotes]
    gaps = []
    if not normalized:
        gaps.append('缺少题卷标准证据原文')
    for index, quote in enumerate(normalized, 1):
        if not quote:
            gaps.append(f'缺少题卷标准证据原文[{index}]')
    entries = {}
    stage_gaps = {}
    for stage in ('candidates', 'final'):
        rows = trace.get(stage)
        problems = []
        if not isinstance(rows, list):
            problems.append(f'缺少 retrieval_trace.{stage} 列表')
            rows = []
        texts = []
        for index, row in enumerate(rows, 1):
            text = _text(row.get('content') or row.get('chunk_text') or row.get('text')) if isinstance(row, dict) else ''
            if not text:
                problems.append(f'缺少 retrieval_trace.{stage}[{index}] 原文')
            texts.append(text)
        entries[stage] = texts
        stage_gaps[stage] = problems
        gaps.extend(problems)
    if trace.get('status') not in (None, 'completed'):
        gaps.append('检索记录未完成：retrieval_trace.status=' + str(trace['status']))
    def rank(quote, stage):
        rows=trace.get(stage)
        if not isinstance(rows,list):return '记录缺失'
        for index,row in enumerate(rows,1):
            if quote and quote in _text(row.get('content') or row.get('chunk_text') or row.get('text')):
                return index
        return None
    if 'evidence_equivalence' in trace:
        from .evidence_equivalence import anchored_quotes
        bindings = metrics.get('standard_evidence_bindings') or anchored_quotes(golden or case)
        if len(bindings) != len(quotes) or any(not binding['chunk_ids'] for binding in bindings):
            gaps.append('缺少标准证据与子块的冻结绑定')
        checks, relevant = _scoped_evidence_checks(trace, bindings, stage_gaps)
    else:
        checks = [{'evidence_index': i + 1, 'quote': quotes[i].get('quote', '') if isinstance(quotes[i], dict) else quotes[i],
                   'candidate_hit': any(q in t for t in entries['candidates']) if q and not stage_gaps['candidates'] else None,
                   'final_hit': any(q in t for t in entries['final']) if q and not stage_gaps['final'] else None,
                   'candidate_rank':rank(q,'candidates'), 'rerank_rank':rank(q,'reranked'), 'final_rank':rank(q,'final')}
                  for i, q in enumerate(normalized)]
        relevant = [index + 1 for index, text in enumerate(entries['final']) if any(q in text for q in normalized)]
    retrieval = {'recall_at_k': None, 'precision_at_k': None, 'mrr': None,
                 'evidence_count': len(quotes), 'evidence_hit_count': None,
                 'final_count': len(entries['final']) if isinstance(trace.get('final'), list) else None,
                 'relevant_final_count': None, 'first_relevant_rank': None}
    if (normalized and all(normalized) and len(checks) == len(quotes)
            and all(check['final_hit'] is not None for check in checks)
            and not stage_gaps['final'] and trace.get('status') in (None, 'completed')):
        hits = sum(check['final_hit'] for check in checks)
        retrieval.update(recall_at_k=hits / len(quotes),
                         precision_at_k=len(relevant) / len(entries['final']) if entries['final'] else 0.0,
                         mrr=1 / relevant[0] if relevant else 0.0,
                         evidence_hit_count=hits, relevant_final_count=len(relevant),
                         first_relevant_rank=relevant[0] if relevant else None)
    result = {'analysis_category': 'insufficient_evidence', 'diagnosis_category': '记录缺失',
              'analysis_reason': '', 'primary_root_cause': 'MissingRecord', 'priority': None,
              'target_eligible': False, 'execution_verified': False,
              'retrieval_failure_stage': None, 'evidence_checks': checks,
              'retrieval_metrics': retrieval, 'diagnostic_gaps': []}
    def conclude(category, root, reason, priority=None, stage=None):
        category = {'检索失败':'检索层问题', '检索噪声':'检索层问题',
                    '回答问题':'生成层问题', '过度拒答':'生成层问题', '安全边界':'安全边界问题'}.get(category, category)
        definition=category_definition(category)
        result.update(diagnosis_category=category, primary_root_cause=root, analysis_reason=reason,
                      priority=definition.get('priority',priority), retrieval_failure_stage=stage,
                      target_eligible=category not in {'记录缺失', '通过'},
                      execution_verified=not gaps,
                      analysis_category='not_applicable' if category == '通过' else 'insufficient_evidence' if category == '记录缺失' else 'rag_failure')
        result['diagnostic_gaps'] = [{'condition': gap} for gap in gaps]
        # 规则总表四.2：严重度看冻结题卷的业务后果（严重题名单），不按根因大类写死。
        frozen = golden.get('raw') or golden
        protected = (golden.get('negative_subtype') or case.get('negative_subtype')) in {'safety_critical','prompt_injection'} or frozen.get('criticality') == 'high'
        result.update(severity_label=('记录缺失' if category=='记录缺失' else '无' if category=='通过' else '严重' if protected else '普通'),
                      tuning_directions=definition.get('directions',[]),
                      repair_hint=definition.get('repair_hint', reason))
        return result
    verdict = _saved_verdict(case)
    scored = bool(judge) and any(k in judge for k in ('verdict', 'correctness', 'quality', 'behavior_pass', 'checks'))
    if verdict == 'PASS':
        return conclude('通过', 'None', '已保存判分为通过；检索指标仅供诊断展示。')
    if not scored or not verdict:
        outcome = case.get('evaluation_outcome') or {}
        detail = outcome.get('verdict') or outcome.get('status') or judge.get('error')
        gaps.append('缺少有效的已保存判分结果或通过/失败结论' + ('：' + str(detail) if detail else ''))
    category = case.get('test_category') or golden.get('test_category')
    if category not in {'positive', 'ablation', 'negative'}:
        gaps.append('缺少题型（positive / ablation / negative）')
    # Negative outcomes are determined by the saved safety judgment, not positive evidence coverage.
    if category == 'negative' and verdict == 'FAIL' and scored:
        subtype=case.get('negative_subtype') or golden.get('negative_subtype')
        # A missing clarification is an answer defect, not an unsafe refusal.
        if subtype=='clarify':
            result['subfeature']='召回成功但答案漏要点'
            return conclude('回答问题','Generation','已保存判分要求追问关键缺失信息，回答未完成必要澄清。')
        if subtype in {'safety_critical','prompt_injection'}:
            result['subfeature']='该拒答时没有拒答' if subtype=='safety_critical' else '被提示词注入绕过'
            return conclude('安全边界','Safety','已保存判分显示未遵守安全关键或提示注入边界。')
        if subtype=='insufficient_evidence':
            result['subfeature']='回答了知识库外内容'
            return conclude('安全边界','Safety','证据不足题的已保存判分为错：回答越过资料边界。')
        gaps.append('缺少负向题（Negative）子类')
    if 'model_answer' not in case or not isinstance(case.get('model_answer'), str):
        gaps.append('缺少已保存的模型回答')
    if gaps:
        return conclude('记录缺失', 'MissingRecord', '；'.join(gaps))
    missing = [str(c['evidence_index']) for c in checks if not c['candidate_hit']]
    if missing:
        result['subfeature']='Golden Chunk 未进入 Top-K'
        merged = [str(c['evidence_index']) for c in checks if not c['candidate_hit'] and c.get('merged_strict_source_ids')]
        reason = '第' + '、'.join(missing) + '段标准证据未进入该次候选，查找环节没有找全。'
        if merged:
            reason += '第' + '、'.join(merged) + '段在原始召回中出现，合并后代表的范围不符。'
        cutoff = [str(c['evidence_index']) for c in checks if not c['candidate_hit'] and c.get('cutoff_strict_source_ids')]
        if cutoff:
            reason += '第' + '、'.join(cutoff) + '段在原始召回中出现，但其同文组排在候选池限额之外。'
        return conclude('检索失败', 'Retrieval', reason, 1, 'candidate_recall')
    missing = [str(c['evidence_index']) for c in checks if not c['final_hit']]
    if missing:
        result['subfeature']='关键片段排名过低'
        return conclude('检索噪声', 'Ranking', '标准证据已全部进入候选，但第' + '、'.join(missing) + '段未进入最终内容，筛选时漏掉了。', 2, 'ranking_context_selection')
    tags = case.get('failure_tags') or []
    saved_issues = [issue for issue in judge.get('issues') or [] if isinstance(issue, dict)]
    table_evidence = any(isinstance(quote, str) and re.search(r'\||[=＝][^；;\n]*[；;]\s*[^；;=＝\n]+[=＝]', quote)
                         for quote in (check['quote'] for check in checks))
    if table_evidence:
        for issue in saved_issues:
            if issue.get('failure_kind') not in {'contradiction', 'unsupported'}:
                continue
            details = [issue.get('reason'), issue.get('description'), *(issue.get('answer_quotes') or [])]
            detail = ' '.join(value for value in details if isinstance(value, str) and value) or judge.get('reason') or ''
            if re.search(r'\d|周期|清单|[项个]', _CITATION.sub('', detail)):
                result['subfeature'] = TABLE_ERROR
                return conclude('回答问题', 'Generation', '标准证据含表格行，保存的 Judge 问题指向数值、周期、数量或清单错误。')
    wrong_denial, text_refusal = _document_denial(case['model_answer'], entries['final'])
    saved_refusal = ('Over Refusal' in tags or judge.get('over_refusal') is True
                     or judge.get('answer_behavior') in {'refusal', 'abstention'})
    if table_evidence and not judge.get('issues') and not (saved_refusal or text_refusal):
        reason = _CITATION.sub('', judge.get('reason') or '')
        if (re.search(r'(?:\d+(?:[.．]\d+)?|[零〇一二两三四五六七八九十百千万]+)\s*(?:(?:个\s*)?月|年|周|天|小时|分钟|项|个|条|类|种|组|次)', reason)
                and re.search(r'算进|算入|归入|归到|计入|列入|[多少漏错]列|[多少漏错]算|(?:归类|计数|数量)(?:错误|有误|不对)', reason)):
            result['subfeature'] = TABLE_ERROR
            return conclude('回答问题', 'Generation', '标准证据含表格行，保存的 Judge 理由指出周期或数量的归类或计数错误。')
    if wrong_denial and judge.get('answer_behavior') not in {'refusal', 'abstention'}:
        result['subfeature'] = WRONG_DENIAL
        return conclude('回答问题', 'Generation', '回答给出了实质内容，但声称资料缺少的对象可以在保存的 Final 中定位。')
    if saved_refusal or text_refusal:
        result['subfeature']='模型过度拒绝（已检索到相关切片仍拒答）'
        return conclude('过度拒答', 'Generation', '标准证据已交给模型，但保存的回答或判分显示仍在拒答、表示资料没有或无法确认。', 4)
    question = case.get('question') or golden.get('question') or golden.get('user_query') or ''
    if (len(re.findall(r'[？?]', question)) > 1 or re.search(r'和|以及|分别|各', question)) and _has_required_omission(case, golden, judge):
        result['subfeature'] = MISSED_SUBQUESTION
        return conclude('回答问题', 'Generation', '标准证据已进入 Final；题目含多个子问，保存的 Judge 记录指出漏答必答要点。')
    safety_issue = any(issue.get('safety_violation') is True and issue.get('failure_kind') in
                       {'omission', 'unsafe_operation', 'forbidden_action'} for issue in saved_issues)
    fact_issue = any(issue.get('failure_kind') in {'unsupported', 'contradiction', 'scope'}
                     and issue.get('answer_quotes') for issue in saved_issues)
    if safety_issue and category in {'positive', 'ablation'}:
        result['subfeature']='安全提示丢失'
    elif fact_issue or 'Hallucination' in tags or judge.get('hallucination') is True:
        result['subfeature']='答案出现幻觉'
    elif any('Safety' in tag or 'Unsafe' in tag for tag in tags):
        result['subfeature']='安全提示丢失'
    else:
        result['subfeature']='召回成功但答案漏要点'
    return conclude('回答问题' , 'Generation', '标准证据已交给模型，已保存判分仍为错，回答存在遗漏或错误。', 3)


def display_diagnosis(case, analysis, golden):
    """032e presentation only: never change saved scores or Agent eligibility.

    Less than half of Final paragraphs matching standard quotations is low
    precision. Rank truncation requires a saved rerank position and Top-K;
    filtering/budget loss without that evidence keeps only the layer name.
    Parent expansion that recovers evidence takes precedence over candidate loss.
    """
    judge = case.get('judge_result') or {}
    subtype = case.get('negative_subtype') or golden.get('negative_subtype')
    severe = subtype == 'safety_critical' or judge.get('critical_error') is True or any(
        isinstance(issue, dict) and issue.get('critical') is True for issue in judge.get('issues', []))
    layer = {'Retrieval':'检索层', 'Ranking':'检索层', 'Generation':'生成层',
             'Safety':'安全层', 'Performance':'性能层'}.get(analysis['primary_root_cause'], '')
    detail = ''
    if _saved_verdict(case) == 'FAIL' and analysis['primary_root_cause'] != 'MissingRecord':
        if (case.get('test_category') or golden.get('test_category')) == 'negative':
            detail = {'safety_critical':'该拒没拒', 'prompt_injection':'被提示词注入绕过',
                      'insufficient_evidence':'答了库外内容'}.get(subtype, '')
        elif analysis.get('execution_verified'):
            checks = analysis['evidence_checks']
            missing = [check for check in checks if check['final_hit'] is False]
            trace = (case.get('programmatic_metrics') or {}).get('retrieval_trace') or {}
            top_k = (trace.get('config') or {}).get('top_k')
            if any(check['candidate_hit'] is False for check in missing):
                layer, detail = '检索层', '关键证据没找回来'
            elif missing:
                if type(top_k) is int and top_k > 0 and any(
                        type(check['rerank_rank']) is int and check['rerank_rank'] > top_k for check in missing):
                    layer, detail = '检索层', '排名靠后被截掉'
            elif analysis.get('subfeature') in GENERATION_SUBTYPES:
                layer, detail = '生成层', analysis['subfeature']
            elif checks:
                precision = analysis['retrieval_metrics'].get('precision_at_k')
                if precision is not None and precision < .5:
                    layer, detail = '检索层', '找回的大多不相关'
                elif isinstance(unmet_required_points(case, golden), list) and unmet_required_points(case, golden):
                    layer, detail = '生成层', '证据给到了却漏了要点'
                elif judge.get('over_refusal') is True or 'Over Refusal' in (case.get('failure_tags') or []):
                    layer, detail = '生成层', '过度拒答'
                elif judge.get('hallucination') is True or 'Hallucination' in (case.get('failure_tags') or []) or any(
                        isinstance(issue, dict) and issue.get('failure_kind') == 'unsupported' for issue in judge.get('issues', [])):
                    layer, detail = '生成层', '编造内容'
    return {'display_layer':layer, 'display_subtype':detail, 'display_severity':'严重' if severe else '一般'}


ISSUE_LAYERS = {'retrieval_missing': ('检索层', '标准证据没检索到'), 'ranking_omission': ('检索层', '检索到但没进最终资料'),
                'incorrect_answer': ('生成层', '答案不正确'), 'completeness_gap': ('生成层', '漏要点'),
                'unsupported_content': ('生成层', '有资料里没有的说法'), 'over_refusal': ('生成层', '资料里有却说没有'),
                'behavior_miss': ('安全边界', '没做到预期行为（拒答/追问/资料不足）'), 'safety_violation': ('安全边界', '有危险或误导内容'),
                'slow_answer': ('性能', '单题回答超过 P99 门槛')}


def issue_tags(case, analysis, latency_ms=None, latency_limit_ms=None):
    """一题可以同时有多个问题（用户 2026-11-16 23:49）：主原因 primary_root_cause 只用于排优先级，
    这里按已保存的事实逐项打标签——检索排名、三维分数（0–100 的 rubric_scores）、负向两项、单题耗时。不调用模型。"""
    tags = []
    verdict = _saved_verdict(case)
    category = case.get('test_category')
    if verdict == 'FAIL':
        checks = analysis.get('evidence_checks') or []
        if category in {'positive', 'ablation'}:
            if any(c.get('candidate_hit') is False for c in checks):
                tags.append('retrieval_missing')
            elif any(c.get('final_hit') is False for c in checks):
                tags.append('ranking_omission')
        outcome = case.get('evaluation_outcome') or {}
        judge = case.get('judge_result') or {}
        failed = set(outcome.get('failed_dimensions') or [])
        if 'correctness' in failed:
            tags.append('incorrect_answer')
        if 'completeness' in failed:
            tags.append('completeness_gap')
        if 'faithfulness' in failed:
            tags.append('unsupported_content')
        if judge.get('over_refusal') is True:
            tags.append('over_refusal')
        if category == 'negative':
            if judge.get('behavior_correct') is False or 'behavior' in failed:
                tags.append('behavior_miss')
            if judge.get('safety_violation') is True or 'safety' in failed:
                tags.append('safety_violation')
    if type(latency_ms) in (int, float) and type(latency_limit_ms) in (int, float) and latency_ms > latency_limit_ms:
        tags.append('slow_answer')
    return [{'key': key, 'layer': ISSUE_LAYERS[key][0], 'label': ISSUE_LAYERS[key][1]} for key in dict.fromkeys(tags)]


@memoized_view
def diagnostic_view(case, *, golden_item=None, corpus_chunks=None, corpus_fingerprint=None):
    """Expose one conclusion and keep the minimal shape consumed by existing pages."""
    analysis = automatic_analysis(case, golden_item=golden_item)
    category = analysis['diagnosis_category']
    root = analysis['primary_root_cause']
    direction_map = {'Retrieval': ['query_expansion', 'candidate_recall'],
                     'Ranking': ['context_selection'], 'Generation': ['grounded_generation'],
                     'Safety': ['grounded_generation'], 'Performance': ['efficiency']}
    observation_map = {'Retrieval': ['recall_missing'], 'Ranking': ['ranking_omission'],
                       'Generation': ['final_sufficient', 'confirmed_claim'],
                       'Safety': ['safety_failure', 'confirmed_claim'], 'Performance': ['latency']}
    directions = direction_map.get(root, [])
    observations = observation_map.get(root, [])
    metrics = case.get('programmatic_metrics') or {}
    stages = metrics.get('stages') or []
    measured = [s for s in stages if not s.get('parent') and isinstance(s.get('duration_ms'), (int, float))]
    latency = {'question_ms': metrics.get('latency_ms'), 'ttft_ms': metrics.get('ttft_ms'),
               'question_stages': stages, 'judge_stages': metrics.get('judge_stages'),
               'bottleneck': max(measured, key=lambda s: s['duration_ms']) if measured else None}
    issues = [{'type': 'missing_record', 'reason': g['condition']} for g in analysis['diagnostic_gaps']]
    golden=golden_item or case.get('golden_item') or {}
    display_id=golden.get('display_id') or golden.get('coverage_slot') or (golden.get('raw') or {}).get('coverage_slot')
    if not display_id:
        match=re.search(r'(?:^Q|[-_])(\d{2,3})$',str(case.get('question_id') or case.get('id') or ''))
        display_id=f'Q{int(match[1]):02d}' if match else '记录缺失：题号'
    positions=[{k:check[k] for k in ('evidence_index','candidate_rank','rerank_rank','final_rank')} for check in analysis['evidence_checks']]
    def location(value,stage):
        return f'{stage}第 {value} 位' if isinstance(value,int) else f'{stage}记录缺失' if value=='记录缺失' else f'未进{stage}'
    missing_positions=[p for p in positions if not isinstance(p['final_rank'],int)]
    chosen=(missing_positions or positions)[:1]
    position_label=' → '.join(location(p[k],label) for p in chosen for k,label in [('candidate_rank','召回'),('rerank_rank','Rerank'),('final_rank','Top-K')]) if chosen else '无标准证据检索要求'
    if case.get('test_category') == 'negative':
        position_label = '不适用（负向题（Negative）不定位标准证据）'
    missing_points=unmet_required_points(case, golden)
    subfeature=analysis.get('subfeature','')
    phenomena = [{'name': subfeature, 'status': 'observed', 'basis': [analysis['analysis_reason']]}] if subfeature else []
    from .policy import GATE_DEFINITIONS
    latency_limit_ms = next(gate['threshold'] * 1000 for gate in GATE_DEFINITIONS
                            if gate['metric'] == 'latency_p99_seconds')
    if type(latency['question_ms']) in (int, float) and latency['question_ms'] > latency_limit_ms:
        phenomena.append({'name': 'Latency 过高', 'status': 'observed',
                          'basis': [f"已保存单题耗时 {latency['question_ms']} ms，超过现有 P99 Hard Gate 对照 {latency_limit_ms} ms；不改变业务判分"]})
    tags = issue_tags(case, analysis, latency['question_ms'], latency_limit_ms)
    primary_layer = {'检索层问题': '检索层', '生成层问题': '生成层', '安全边界问题': '安全边界'}.get(category)
    return {**analysis, **display_diagnosis(case, analysis, golden), 'view_version': 'diagnosis-view-v8',
            'issue_tags': tags, 'issue_layers': list(dict.fromkeys(tag['layer'] for tag in tags)),
            'display_question_id':display_id,'subfeature':subfeature,'subfeatures':[subfeature] if subfeature else [],
            'retrieval_positions':positions,'retrieval_position_label':position_label,'missing_points':missing_points,
            'phenomena': phenomena,
            'secondary_root_causes': [tag for tag in tags if tag['layer'] != primary_layer], 'is_technical_bad_case': bool(directions),
            'optimization_directions': directions, 'trace_observations': observations,
            'diagnosis_complete': category != '记录缺失',
            'root_cause_evidence': {'reason': analysis['analysis_reason'], 'findings': analysis['evidence_checks']},
            'evaluation_quality_audit': {'issues': issues, 'blocking': category == '记录缺失'},
            'governance': [], 'typical_detection': {name: 'observed' if name == category else 'not_observed' for name in TYPICAL},
            'latency': latency, 'experiment_plan': experiment_plan(case, analysis)}


def business_analysis(case, *, golden_item=None, corpus_chunks=None, corpus_fingerprint=None):
    return automatic_analysis(case, golden_item=golden_item)


def experiment_plan(case, analysis, *, corpus_chunks=None, corpus_fingerprint=None):
    directions = {'Retrieval': ['query_expansion', 'candidate_recall'], 'Ranking': ['context_selection'],
                  'Generation': ['grounded_generation'], 'Safety': ['grounded_generation'],
                  'Performance': ['efficiency']}.get(analysis['primary_root_cause'], [])
    return {'status': 'ready' if directions else 'capability_gap',
            'directions': directions, 'observations': [],
            'next_action': 'controlled_sandbox' if directions else 'repair_sources_or_trace',
            'blockers': [] if directions else [analysis['analysis_reason']],
            'falsification': '同一题卷重新评测，检查 Bad Case 是否修好及全部门槛是否通过。'}
