"""Frozen normative sources; never claim these are retrieved Final evidence."""
from .evaluation_contract import normalize_display


def full_norms(question,chunks):
    evidence=question.get('evidence',question.get('acceptable_evidence',[]))
    by_id={c['chunk_id']:c for c in chunks}
    result=[]
    for original in evidence:
        for key in original.get('source_chunk_ids',[]):
            source=by_id.get(key)
            if not source:raise ValueError('frozen_source_missing: '+key)
            for field in ('product','version'):
                if question.get(field) and question[field]!=source.get(field):raise ValueError('frozen_source_scope_conflict: '+field)
            if question.get('source_document_id') and question['source_document_id']!=source.get('document_id'):raise ValueError('frozen_source_document_conflict')
            text=source.get('chunk_text') or source.get('text') or source.get('content')
            if not isinstance(text,str) or not normalize_display(text):raise ValueError('empty_canonical_norm: '+key)
            result.append({**{k:source.get(k) for k in ('chunk_id','document_id','product','version','section_path','page_start','page_end')},
                'content':text,'frozen_summary':original.get('evidence_key_points',[]),'role':'material_anchor_only' if question.get('test_category')=='negative' else 'normative_requirement_only'})
    return result


def optimization_preflight(question,chunks):
    """Material/capability contract, not a prediction of answer correctness."""
    from .policy import search_space_contract
    errors=[]
    try:norms=full_norms(question,chunks)
    except ValueError as error:norms=[];errors.append(str(error))
    negative=question.get('test_category')=='negative'
    if not negative and not norms:errors.append('必要规范缺失：先经现有资料/Revision流程补齐，禁止评分后删题')
    if not negative and not question.get('reference_answer'):errors.append('必要回答要求未提供')
    if negative and question.get('expected_behavior') not in {'safe_rejection','insufficient_evidence','clarify','prompt_injection_resistance'}:
        errors.append('负向题预期拒答/澄清/安全边界未确认')
    return {'ready':not errors,'blocking_errors':errors,'source_roles':sorted({n['role'] for n in norms}),
        'optimization_parameters':list(search_space_contract()),'diagnostic_capture':['candidates','reranked','final','answer','stages'],
        'semantic_scope_review':'existing_probe_qc_and_business_audit_required',
        'runtime_gap_action':'resolve_saved_execution_then_validate_candidate','predicts_model_success':False}
