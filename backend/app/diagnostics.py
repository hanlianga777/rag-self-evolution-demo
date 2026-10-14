"""Read-only explanation of saved evidence; never rescore or rewrite a Run."""
from .evaluation_contract import diagnosis, normalize, quote_present

TYPICAL = ('检索失败', '检索噪声', '模型过度拒答', '安全边界误伤', '延迟黑洞')
TAG_NAMES = {'Retrieval Failure':'检索失败','Ranking Failure':'排序失败','Query Failure':'查询表达偏差',
    'Evidence Miss':'证据未命中','Retrieval Noise':'检索噪声','Hallucination':'无依据生成',
    'Generation Failure':'回答质量不足','Incomplete Answer':'回答不完整','Over Refusal':'模型过度拒答',
    'Metadata / Entity Failure':'产品/版本混淆','Unsafe Answer':'安全边界失守','Safety Failure':'安全边界失守',
    'Safety False Positive':'安全边界误伤','Performance Failure':'延迟黑洞',
    'Evidence Pending Review':'证据/评测待核实','Evidence / Citation Failure':'证据或引用不足',
    'Citation Failure':'引用不足','Unsupported Claim':'无依据主张','HALLUCINATION':'无依据生成'}


def diagnostic_view(case):
    metrics=case.get('programmatic_metrics') or {}
    audit=diagnosis(case);coverage=metrics.get('evidence_coverage') or {}
    trace=metrics.get('retrieval_trace') or {};sufficiency=metrics.get('evidence_sufficiency') or {}
    phenomena={};detection={name:'not_collected' for name in TYPICAL}
    def add(name,basis,status='recorded'):
        phenomena.setdefault(name,{'name':name,'status':status,'basis':[]})['basis'].append(basis)
        if name in detection:detection[name]='observed'
    required=set(coverage.get('required_chunk_ids') or [])
    candidates={i for r in trace.get('candidates') or [] for i in r.get('matched_child_ids',[r.get('chunk_id')])}
    # Stored failure signals keep their original confidence; a label is not a new root cause.
    quote=audit.get('answer_quote')
    located=isinstance(quote,str) and bool(normalize(quote)) and normalize(quote) in normalize(case.get('model_answer',''))
    noise_supported=any(isinstance(f,dict) and isinstance(f.get('claim'),str) and normalize(f['claim']) and normalize(f['claim']) in normalize(case.get('model_answer','')) and any(quote_present(q,trace.get('final',[])) for q in f.get('support',[])) for f in audit.get('findings',[]) if isinstance(f,dict))
    for tag in case.get('failure_tags') or []:
        name=TAG_NAMES.get(tag,tag)
        if tag=='Retrieval Failure' and not (required and required<=candidates):
            add('检索失败信号待核实','failure_tags / required_chunk_ids / candidates');continue
        if tag=='Performance Failure' and not isinstance(metrics.get('latency_ms'),(int,float)):
            add('延迟信号待核实','failure_tags / latency_ms');continue
        if tag in {'Over Refusal','Safety False Positive'}:
            if sufficiency.get('sufficient') is not True or not located:
                add('拒答归因待核实','failure_tags / evidence_sufficiency / answer_quote');continue
        if tag=='Retrieval Noise' and not noise_supported:
            add('噪声归因待核实','failure_tags / diagnosis.findings');continue
        add(name,'failure_tags.'+tag)
    if required and required<=candidates:
        detection['检索失败']='not_observed'
        if coverage.get('final_context',{}).get('all_hit') is False and sufficiency.get('sufficient') is not True:
            add('检索失败','evidence_coverage.required_chunk_ids + retrieval_trace.candidates + final_context','observed')
    confirmed=(metrics.get('claim_assessment') or {}).get('confirmed') or []
    if any(r.get('kind')=='unsupported_instruction' and r.get('changes_operation') is True for r in confirmed):
        add('无依据技术操作','claim_assessment.confirmed','observed')
    if case.get('negative_subtype')=='prompt_injection' and (metrics.get('behavior_contract') or {}).get('effective_pass') is False:
        add('提示词注入失败','behavior_contract.effective_pass','observed')
    conflicts=sufficiency.get('unresolved_conflicts') or []
    pending=(metrics.get('claim_assessment') or {}).get('pending') or []
    governance=[]
    if conflicts:
        add('来源冲突','evidence_sufficiency.unresolved_conflicts','observed')
        governance.append({'type':'source_conflict','evidence':conflicts})
    if pending:
        add('评测分类/定位待核实','claim_assessment.pending','observed')
        governance.append({'type':'claim_verification','evidence':pending})
    if audit.get('disputes'):governance.extend(audit['disputes'])
    stages=metrics.get('stages') or []
    measured=[s for s in stages if not s.get('parent') and isinstance(s.get('duration_ms'),(int,float))]
    latency={'question_ms':metrics.get('latency_ms'),'ttft_ms':metrics.get('ttft_ms'),
             'question_stages':stages,'judge_stages':metrics.get('judge_stages'),
             'bottleneck':max(measured,key=lambda s:s['duration_ms']) if measured else None}
    if isinstance(latency['question_ms'],(int,float)) and detection['延迟黑洞']!='observed':
        detection['延迟黑洞']='not_observed' # No new latency threshold; use saved Performance Failure.
    observations=[]
    if isinstance(trace.get('candidates'),list) and isinstance(trace.get('final'),list):
        final_ids={i for row in trace['final'] for i in row.get('matched_child_ids',[row.get('chunk_id')])}
        if required and required-candidates and sufficiency.get('sufficient') is not True:observations.append('recall_missing')
        if required & candidates-final_ids and sufficiency.get('sufficient') is not True:observations.append('ranking_omission')
        if sufficiency.get('sufficient') is True:observations.append('final_sufficient')
        if audit.get('findings') or (metrics.get('claim_assessment') or {}).get('confirmed'):observations.append('confirmed_claim')
        if case.get('primary_root_cause')=='Safety' and audit.get('status')=='confirmed':
            observations.append('safety_failure')
        if noise_supported and 'Retrieval Noise' in (case.get('failure_tags') or []):observations.append('retrieval_noise')
        if any(s.get('stage_name') and isinstance(s.get('duration_ms'),(int,float)) for s in measured) and 'Performance Failure' in (case.get('failure_tags') or []):observations.append('measured_latency')
    root=case.get('primary_root_cause') or case.get('root_cause',{}).get('primary') or 'Unknown'
    return {'view_version':'diagnosis-view-v1','phenomena':list(phenomena.values()),'primary_root_cause':root,
            'secondary_root_causes':case.get('secondary_root_causes') or case.get('root_cause',{}).get('secondary') or [],
            'confidence':audit['status'],'root_cause_evidence':audit,'governance':governance,
            'target_eligible':audit['status']=='confirmed' and root in {'Retrieval','Generation','Safety','Performance'},
            'typical_detection':detection,'latency':latency,'trace_observations':observations}
