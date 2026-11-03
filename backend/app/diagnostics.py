"""Read-only explanation of saved evidence; never rescore or rewrite a Run."""
from .evaluation_contract import normalize
from .read_view import memoized_view
from .diagnostic_categories import DIAGNOSTIC_CATEGORIES, category_definition

TYPICAL = tuple(row['label'] for row in DIAGNOSTIC_CATEGORIES)
@memoized_view
def _current_corpus(trace):
    """Read persisted chunks only after their manifest/source identities are verified."""
    import hashlib
    import json
    from .corpus import INDEX_DIR, current_manifest, manifest_identity
    from .full_text import CORPUS_LOCK
    try:
        with CORPUS_LOCK:
            manifest=json.loads((INDEX_DIR/'manifest.json').read_text())
            identity=manifest_identity(manifest)
            if not trace.get('corpus_fingerprint') or trace['corpus_fingerprint']!=identity or identity!=manifest_identity(current_manifest()):
                return [], None
            artifacts={name:(INDEX_DIR/name).read_bytes() for name in ('chunks.json','parents.json')}
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
    return ''.join(c.lower() for c in unicodedata.normalize('NFKC', value) if c.isalnum())


def standard_evidence(item):
    """Read standard source quotations from the saved question, never the live KB."""
    item = item or {}
    if 'standard_evidence' in item:
        return item['standard_evidence'] if isinstance(item['standard_evidence'], list) else []
    raw = item.get('raw') or {}
    locations = item.get('evidence_locations') or raw.get('evidence_locations') or []
    if locations:
        return [entry.get('quote', '') if isinstance(entry, dict) else '' for entry in locations]
    evidence = item.get('evidence') or raw.get('evidence') or []
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


def _saved_verdict(case):
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
    checks = [{'evidence_index': i + 1, 'quote': quotes[i].get('quote', '') if isinstance(quotes[i], dict) else quotes[i],
               'candidate_hit': any(q in t for t in entries['candidates']) if q and not stage_gaps['candidates'] else None,
               'final_hit': any(q in t for t in entries['final']) if q and not stage_gaps['final'] else None,
               'candidate_rank':rank(q,'candidates'), 'rerank_rank':rank(q,'reranked'), 'final_rank':rank(q,'final')}
              for i, q in enumerate(normalized)]
    retrieval = {'recall_at_k': None, 'precision_at_k': None, 'mrr': None,
                 'evidence_count': len(quotes), 'evidence_hit_count': None,
                 'final_count': len(entries['final']) if isinstance(trace.get('final'), list) else None,
                 'relevant_final_count': None, 'first_relevant_rank': None}
    if normalized and all(normalized) and not stage_gaps['final'] and trace.get('status') in (None, 'completed'):
        hits = sum(check['final_hit'] for check in checks)
        relevant = [index + 1 for index, text in enumerate(entries['final']) if any(q in text for q in normalized)]
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
        result.update(severity_label=definition.get('severity','记录缺失' if category=='记录缺失' else '无'),
                      tuning_directions=definition.get('directions',[]),repair_hint=definition.get('repair_hint',reason))
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
        gaps.append('缺少负向题子类')
    if 'model_answer' not in case or not isinstance(case.get('model_answer'), str):
        gaps.append('缺少已保存的模型回答')
    if gaps:
        return conclude('记录缺失', 'MissingRecord', '；'.join(gaps))
    missing = [str(c['evidence_index']) for c in checks if not c['candidate_hit']]
    if missing:
        result['subfeature']='Golden Chunk 未进入 Top-K'
        return conclude('检索失败', 'Retrieval', '第' + '、'.join(missing) + '段标准证据未进入该次候选，查找环节没有找全。', 1, 'candidate_recall')
    missing = [str(c['evidence_index']) for c in checks if not c['final_hit']]
    if missing:
        result['subfeature']='关键片段排名过低'
        return conclude('检索噪声', 'Ranking', '标准证据已全部进入候选，但第' + '、'.join(missing) + '段未进入最终内容，筛选时漏掉了。', 2, 'ranking_context_selection')
    import re
    answer = _text(case['model_answer'])
    refusal = ('Over Refusal' in (case.get('failure_tags') or [])
               or judge.get('over_refusal') is True
               or judge.get('answer_behavior') in {'refusal', 'abstention'}
               or re.search(r'(?:资料|材料|文档|手册|上下文).{0,12}(?:没有|未提供|未找到|未说明|未包含)|无法确认|不能确认|不能回答|无法回答|无法提供|无法确定', answer))
    if refusal:
        result['subfeature']='模型过度拒绝（已检索到相关切片仍拒答）'
        return conclude('过度拒答', 'Generation', '标准证据已交给模型，但保存的回答或判分显示仍在拒答、表示资料没有或无法确认。', 4)
    tags = case.get('failure_tags') or []
    if 'Hallucination' in tags or judge.get('hallucination') is True:
        result['subfeature']='答案出现幻觉'
    elif any('Safety' in tag or 'Unsafe' in tag for tag in tags):
        result['subfeature']='安全提示丢失'
    else:
        result['subfeature']='召回成功但答案漏要点'
    return conclude('回答问题' , 'Generation', '标准证据已交给模型，已保存判分仍为错，回答存在遗漏或错误。', 3)


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
    import re
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
    position_label=' → '.join(location(p[k],label) for p in chosen for k,label in [('candidate_rank','候选'),('rerank_rank','重排'),('final_rank','最终')]) if chosen else '无标准证据检索要求'
    if case.get('test_category') == 'negative':
        position_label = '不适用（负向题不定位标准证据）'
    missing_points=unmet_required_points(case, golden)
    subfeature=analysis.get('subfeature','')
    return {**analysis, 'view_version': 'diagnosis-view-v7',
            'display_question_id':display_id,'subfeature':subfeature,'subfeatures':[subfeature] if subfeature else [],
            'retrieval_positions':positions,'retrieval_position_label':position_label,'missing_points':missing_points,
            'phenomena': [{'name': category, 'status': 'observed', 'basis': [analysis['analysis_reason']]}] if directions else [],
            'secondary_root_causes': [], 'is_technical_bad_case': bool(directions),
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
            'falsification': '同一题卷重新评测，检查错题是否修好及11项门槛是否通过。'}
