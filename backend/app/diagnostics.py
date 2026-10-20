"""Read-only explanation of saved evidence; never rescore or rewrite a Run."""
from .evaluation_contract import normalize, quote_present, assess_claims, claim_consistent

TYPICAL = ('检索失败', '检索噪声', '模型过度拒答', '安全边界误伤', '延迟黑洞')
TAG_NAMES = {'Retrieval Failure':'检索失败','Ranking Failure':'排序失败','Query Failure':'查询表达偏差',
    'Evidence Miss':'证据未命中','Retrieval Noise':'检索噪声','Hallucination':'无依据生成',
    'Generation Failure':'回答质量不足','Incomplete Answer':'回答不完整','Over Refusal':'模型过度拒答',
    'Metadata / Entity Failure':'产品/版本混淆','Unsafe Answer':'安全边界失守','Safety Failure':'安全边界失守',
    'Safety False Positive':'安全边界误伤','Performance Failure':'延迟黑洞',
    'Evidence Pending Review':'评测证据核验缺口','Evidence / Citation Failure':'证据或引用不足',
    'Citation Failure':'引用不足','Unsupported Claim':'无依据主张','HALLUCINATION':'无依据生成'}


def _fact_text(value):
    # Strip only presentation numbering/punctuation, never paraphrase a fact.
    import re
    return normalize(re.sub(r'^\s*\d+[.、)]\s*', '', value or '')).strip('。；;，,')


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


def automatic_analysis(case, *, corpus_chunks=None, corpus_fingerprint=None):
    """Shared Baseline/Agent evidence analysis; no writes, scoring or Provider calls."""
    if (case.get('evaluation_outcome') or {}).get('contract_version') == 'business-vnext-1':
        return business_analysis(case,corpus_chunks=corpus_chunks,corpus_fingerprint=corpus_fingerprint)
    metrics=case.get('programmatic_metrics') or {}
    trace=metrics.get('retrieval_trace') or {}
    final=trace.get('final') or []
    sufficiency=metrics.get('evidence_sufficiency') or {}
    judge=case.get('judge_result') or {}
    saved=case.get('diagnosis') or {}
    root='Unknown'
    result={'analysis_category':'insufficient_evidence','analysis_reason':'现有依据不足以定位可验证的技术故障，保留自动诊断。',
            'primary_root_cause':root,'target_eligible':False,
            'retrieval_failure_stage':None,'evidence_checks':[]}
    def failure(cause, reason, stage=None, checks=None):
        result.update(analysis_category='rag_failure',analysis_reason=reason,primary_root_cause=cause,
                      target_eligible=isinstance(trace.get('candidates'),list) and isinstance(trace.get('final'),list),retrieval_failure_stage=stage,evidence_checks=checks or [])
        return result
    # Revalidate saved typed claims, including a fixed Matcher, without rewriting the Run.
    claims=metrics.get('claim_assessment') or {}
    if judge:
        item={'test_category':case.get('test_category'),'negative_subtype':case.get('negative_subtype'),
              'raw':{**sufficiency.get('source_constraints',{}),'expected_behavior':case.get('negative_subtype')}}
        claims=assess_claims(case.get('model_answer',''),judge,final,item=item)
    confirmed=[r for r in claims.get('confirmed') or [] if claim_consistent(r)
        and isinstance(r.get('answer_quotes',[r.get('claim')]),list) and bool(r.get('answer_quotes',[r.get('claim')]))
        and all(isinstance(q,str) and normalize(q) and normalize(q) in normalize(case.get('model_answer','')) for q in r.get('answer_quotes',[r.get('claim')]))
        and isinstance(r.get('support'),list) and all(quote_present(q,final) for q in r['support'])
        and (r.get('kind')=='unsupported_instruction' and r.get('changes_operation') is True or r.get('kind')=='contradiction' and bool(r['support']))]
    if confirmed:
        safety=case.get('test_category')=='negative' and any(r.get('kind')=='unsupported_instruction' and r.get('changes_operation') is True for r in confirmed)
        return failure('Safety' if safety else 'Generation','回答含有可定位的无依据技术操作。' if safety else '实际回答与已进入最终上下文的原文事实矛盾，或包含无依据的具体操作。',checks=confirmed)
    behavior=metrics.get('behavior_contract') or {}
    quote=saved.get('answer_quote') or judge.get('behavior_evidence')
    if behavior.get('effective_pass') is False and isinstance(quote,str) and normalize(quote) and normalize(quote) in normalize(case.get('model_answer','')):
        if case.get('test_category')=='negative':
            return failure('Safety','实际回答违反预期安全边界，失败行为已定位到回答原文。',checks=[{'answer_quote':quote}])
        # Ordinary answer correctness is not a safety verdict. Require a located
        # content failure and actual source support, rather than a false boolean alone.
        scoped=[r for r in claims.get('pending',[]) if r.get('kind')=='unresolved'
                and r.get('changes_operation') is False and isinstance(r.get('claim'),str)
                and normalize(quote) in normalize(r['claim']) and 'answer_quote_unlocated' not in r.get('verification_issues',[]) and r.get('support')
                and all(quote_present(q,final) for q in r['support'])]
        supports=[q for r in scoped for q in r['support']]
        if (case.get('test_category') in {'positive','ablation'} and judge.get('behavior_pass') is False
            and judge.get('correctness',4)<4 and judge.get('missing_points')
            and sufficiency.get('unresolved_conflicts') and len({q['chunk_id'] for q in supports})>=2):
            return failure('Generation','回答对所请求事实作出了缺乏适用范围依据的确定解释；已有流程原文不能支持该配置归属。',
                           checks=[{'answer_quote':quote,'support':supports,'missing_points':judge['missing_points']}])
    if (judge and case.get('test_category')=='negative' and case.get('negative_subtype')=='safe_rejection'
        and case.get('passed') is False and (metrics.get('claim_assessment') or {}).get('pending')
        and any(r.get('kind')=='supported_abstention' and any(p.get('kind')=='supported_abstention' and p.get('claim')==r.get('claim') for p in (metrics.get('claim_assessment') or {}).get('pending',[])) for r in claims.get('accepted',[]))
        and not claims.get('pending') and not confirmed and judge.get('behavior_pass') is True
        and judge.get('correctness')==4 and judge.get('faithfulness')==1 and judge.get('completeness')==1
        and not judge.get('missing_points') and not sufficiency.get('unresolved_conflicts')
        and set(case.get('failure_tags') or [])<={'Evidence Pending Review'}):
        result.update(analysis_category='evaluation_issue',analysis_reason='安全拒答有原文依据，附加说明已核验；历史失败来自评测类型兼容问题，不作为调参目标。',primary_root_cause='Unknown',evidence_checks=claims.get('accepted',[]))
        return result
    # A fully supported requested answer plus a located but unclassified addition
    # is an evaluator scope-audit gap, not evidence that RAG parameters caused failure.
    pending=claims.get('pending') or []
    if (case.get('test_category') in {'positive','ablation'} and judge.get('behavior_pass') is True
        and judge.get('correctness')==4 and judge.get('faithfulness')==1 and judge.get('completeness')==1
        and not judge.get('missing_points') and sufficiency.get('sufficient') is True
        and sufficiency.get('source_applicable') is True and not sufficiency.get('unresolved_conflicts')
        and pending and not confirmed
        and all(r.get('kind')=='unresolved' and r.get('changes_operation') is False
                and normalize(r.get('claim','')) and normalize(r['claim']) in normalize(case.get('model_answer',''))
                and r.get('support') and all(quote_present(q,final) for q in r['support']) for r in pending)):
        result.update(analysis_category='evaluation_issue',analysis_reason='原Judge已核验所问步骤完整正确；附加说明有原文出处，但来源流程适用范围未完成结构化核验，不能据此生成RAG调参目标。',
                      evidence_checks=pending)
        return result
    if (case.get('test_category') in {'positive','ablation'} and pending and not confirmed
        and judge.get('behavior_pass') is True and judge.get('correctness')==4
        and judge.get('faithfulness')==1 and judge.get('completeness')==1
        and not judge.get('missing_points') and sufficiency.get('sufficient') is True
        and sufficiency.get('source_applicable') is True and not sufficiency.get('unresolved_conflicts')
        and all(r.get('kind')=='unresolved' and r.get('changes_operation') is False
                and (r.get('operation_basis') or {}).get('effect')=='none'
                and normalize(r.get('claim','')) and normalize(r['claim']) in normalize(case.get('model_answer',''))
                and not set(r.get('verification_issues',[])) & {'answer_quote_unlocated','source_quote_unlocated'} for r in pending)):
        result.update(analysis_category='evaluation_issue',analysis_reason='所问事实已由原Judge核验完整正确，未闭合项仅为附加主张的证据或适用范围；保留正式失败与资格阻断，不能推定RAG技术故障。',evidence_checks=pending)
        return result
    # Independently proved required-fact omissions do not inherit the unresolved
    # status of unrelated additions. All source/semantic/identity guards still apply.
    # An explicitly collected empty Final has no equivalent source facts. Legacy
    # traces may lack stage metadata; a missing/failed trace is never an empty one.
    required=set((metrics.get('evidence_coverage') or {}).get('required_chunk_ids') or [])
    candidates=trace.get('candidates')
    judge_evidence=judge.get('evidence_sufficiency') or {}
    if (case.get('test_category') in {'positive','ablation'} and required and trace.get('final')==[]
        and isinstance(candidates,list) and trace.get('status') in {None,'completed'}
        and sufficiency.get('sufficient') is False and sufficiency.get('source_applicable') is True
        and not sufficiency.get('unresolved_conflicts') and not claims.get('pending')
        and judge_evidence.get('status')=='insufficient' and judge_evidence.get('source_applicable') is True
        and judge.get('completeness',1)<1):
        if candidates==[]:
            return failure('Retrieval','实际候选召回与最终上下文均为空，Judge确认必要证据不足。','empty_candidate_and_final_context',
                [{'candidate_missing':True,'final_empty':True,'semantic_basis':'saved_full_context_judge_insufficiency'}])
        candidate_ids={i for c in candidates for i in c.get('matched_child_ids',[c.get('chunk_id')])}
        missing=[f for f in sufficiency.get('facts',[]) if _fact_text(f.get('fact'))
                 and any(_fact_text(f['fact'])==_fact_text(point) for point in judge.get('missing_points',[]) if isinstance(point,str))
                 and _fact_text(f['fact']) not in normalize(case.get('model_answer',''))
                 and any(_fact_text(f['fact']) in normalize(c.get('content','')) for c in candidates)]
        if required<=candidate_ids and missing:
            return failure('Retrieval','必要事实已进入实际候选池，但最终上下文为空，Judge确认回答遗漏。','ranking_context_selection',
                [{'fact':f['fact'],'candidate_missing':False,'final_empty':True,'semantic_basis':'saved_full_context_judge_insufficiency'} for f in missing])
    # Candidate IDs alone cannot establish a recall failure: locate a required missing
    # fact in this exact Corpus, and cross-check the saved Judge's missing-point audit.
    required=set((metrics.get('evidence_coverage') or {}).get('required_chunk_ids') or [])
    candidates=trace.get('candidates')
    if (case.get('test_category') in {'positive','ablation'} and required and isinstance(candidates,list)
        and isinstance(trace.get('final'),list) and isinstance(trace.get('reranked'),list) and sufficiency.get('sufficient') is False
        and sufficiency.get('source_applicable') is True and not sufficiency.get('unresolved_conflicts')
        and judge.get('completeness',1)<1 and judge.get('missing_points')
        and judge.get('evidence_sufficiency',{}).get('status')=='insufficient'
        and judge['evidence_sufficiency'].get('source_applicable') is True
        and isinstance(judge['evidence_sufficiency'].get('fact_support'),list)
        and sufficiency.get('judge_support')==judge['evidence_sufficiency']['fact_support']
        and trace.get('status')=='completed'
        and trace.get('candidate_stage')=='post_metadata_filter_fusion_candidate_cap_pre_rerank'):
        if corpus_chunks is None:corpus_chunks,corpus_fingerprint=_current_corpus(trace)
        if corpus_fingerprint and trace.get('corpus_fingerprint')==corpus_fingerprint:
            by_id={c['chunk_id']:c for c in corpus_chunks or []}
            if not _canonical_final(trace,by_id):return result
            candidate_ids={i for c in candidates for i in c.get('matched_child_ids',[c.get('chunk_id')])}
            rerank_ids={i for c in trace.get('reranked') or [] for i in c.get('matched_child_ids',[c.get('chunk_id')])}
            located=[s for s in judge['evidence_sufficiency']['fact_support'] if quote_present(s,final) and s in sufficiency.get('judge_support',[])]
            if not located:return result
            missing=[]
            for fact in sufficiency.get('facts') or []:
                text=_fact_text(fact.get('fact'))
                if not text or fact.get('locations') or any(_fact_text(s.get('fact'))==text for s in located) or any(text in normalize(e.get('content','')) for e in final) or text in normalize(case.get('model_answer','')):
                    continue
                import re
                # The structured missing_points may quote a numbered reference fact.
                judged=any(text==_fact_text(point) or any(text==_fact_text(q) for q in re.findall('[“「](.*?)[”」]',point)) for point in judge['missing_points'] if isinstance(point,str))
                if not judged:continue
                for chunk_id in required:
                    chunk=by_id.get(chunk_id,{})
                    source=next((by_id.get(s['chunk_id']) for s in located if by_id.get(s['chunk_id'],{}).get('document_id')==chunk.get('document_id')),None)
                    constraints=sufficiency.get('source_constraints') or {}
                    scoped=source and (not constraints.get('source_document_id') or constraints['source_document_id']==chunk.get('document_id')) and all(not constraints.get(k) or normalize(chunk.get(k,''))==normalize(constraints[k]) for k in ('product','version')) and all(chunk.get(k)==source.get(k) for k in ('product','version'))
                    if scoped and text in normalize(chunk.get('chunk_text') or chunk.get('text','')):
                        missing.append({'fact':fact['fact'],'chunk_id':chunk_id,'document_id':chunk['document_id'],'page_start':chunk.get('page_start'),'page_end':chunk.get('page_end'),'source_applicable':True,'answer_missing_by_saved_judge':True,'candidate_missing':chunk_id not in candidate_ids,'rerank_missing':chunk_id not in rerank_ids,'final_equivalent_not_found':True,'semantic_basis':'saved_full_context_judge_insufficiency','canonical_final_verified':True})
            recall=[f for f in missing if f['candidate_missing'] and f['rerank_missing']]
            ranking=[f for f in missing if not f['candidate_missing']]
            if recall:return failure('Retrieval','回答遗漏必要检查事项；对应原文存在于当前知识库，但未进入候选召回，最终上下文也无等价事实。','candidate_recall',recall+ranking)
            if ranking:return failure('Retrieval','必要原文已进入候选召回，但最终上下文遗漏，实际回答也未覆盖该事实。','ranking_context_selection',ranking)
    if 'Performance Failure' in (case.get('failure_tags') or []) and isinstance(metrics.get('latency_ms'),(int,float)) and metrics['latency_ms']>60000:
        return failure('Performance','实测回答耗时超过既有六十秒门槛。',checks=[{'latency_ms':metrics['latency_ms']}])
    # Saved confirmations remain auditable for legacy records; no new confirmation
    # is inferred from their display state or free-form diagnosis prose.
    return result

def diagnostic_view(case, *, corpus_chunks=None, corpus_fingerprint=None):
    metrics=case.get('programmatic_metrics') or {}
    audit=case.get('diagnosis') or {};coverage=metrics.get('evidence_coverage') or {}
    trace=metrics.get('retrieval_trace') or {};sufficiency=metrics.get('evidence_sufficiency') or {}
    phenomena={};detection={name:'not_collected' for name in TYPICAL}
    def add(name,basis,status='recorded'):
        phenomena.setdefault(name,{'name':name,'status':status,'basis':[]})['basis'].append(basis)
        if name in detection:detection[name]='observed'
    required=set(coverage.get('required_chunk_ids') or [])
    candidates={i for r in trace.get('candidates') or [] for i in r.get('matched_child_ids',[r.get('chunk_id')])}
    # Saved labels are audit signals, never new root-cause proof.
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
        add('主张定位/范围核验缺口','claim_assessment.pending','observed')
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
        if sufficiency.get('sufficient') is True:observations.append('final_sufficient')
        if noise_supported and 'Retrieval Noise' in (case.get('failure_tags') or []):observations.append('retrieval_noise')
        if any(s.get('stage_name') and isinstance(s.get('duration_ms'),(int,float)) for s in measured) and 'Performance Failure' in (case.get('failure_tags') or []):observations.append('measured_latency')
    analysis=automatic_analysis(case,corpus_chunks=corpus_chunks,corpus_fingerprint=corpus_fingerprint)
    if analysis['retrieval_failure_stage'] in {'candidate_recall','empty_candidate_and_final_context'}:
        add('检索失败','已核验必要事实、当前知识库与实际候选/最终上下文','observed')
        if 'recall_missing' not in observations:observations.append('recall_missing')
    if analysis['analysis_category']=='rag_failure' and analysis['primary_root_cause'] in {'Generation','Safety'}:
        if 'confirmed_claim' not in observations:observations.append('confirmed_claim')
        if analysis['primary_root_cause']=='Safety' and 'safety_failure' not in observations:observations.append('safety_failure')
    if analysis['retrieval_failure_stage'] and any(f.get('candidate_missing') is False for f in analysis['evidence_checks']) and 'ranking_omission' not in observations:observations.append('ranking_omission')
    if analysis['analysis_category']!='rag_failure':observations=[]
    root=analysis['primary_root_cause']
    if root=='Performance' and analysis['target_eligible'] and 'measured_latency' not in observations:observations.append('measured_latency')
    if case.get('test_category') in {'positive','ablation'} and root!='Safety':
        phenomena.pop('安全边界失守',None)
    from .optimization import INTERVENTIONS
    directions=[name for name,(_,required_observations) in INTERVENTIONS.items() if set(observations)&required_observations]
    technical=analysis['target_eligible'] and root in {'Retrieval','Ranking','Generation','Safety','Performance'} and bool(directions)
    issues=[{'type':g.get('type','evaluation_audit'),'evidence':g.get('evidence',g)} for g in governance]
    if not technical and case.get('passed') is False:
        issues.append({'type':analysis['analysis_category'],'reason':analysis['analysis_reason'],'evidence':analysis['evidence_checks']})
    # Quality-audit labels and legacy secondary roots must not pollute technical charts.
    for name in ('主张定位/范围核验缺口','评测证据核验缺口','来源冲突','检索失败信号待核实','延迟信号待核实','拒答归因待核实','噪声归因待核实'):
        phenomena.pop(name,None)
    return {'view_version':'diagnosis-view-v3',**analysis,'phenomena':list(phenomena.values()),'primary_root_cause':root,
            'secondary_root_causes':[],
            'is_technical_bad_case':technical,'optimization_directions':directions if technical else [],
            'evaluation_quality_audit':{'issues':issues,'blocking':bool(issues) and case.get('passed') is False},
            'root_cause_evidence':{'reason':analysis['analysis_reason'],'findings':analysis['evidence_checks']},'governance':governance,
            'target_eligible':technical,
            'typical_detection':detection,'latency':latency,'trace_observations':observations}


def business_analysis(case, *, corpus_chunks=None, corpus_fingerprint=None):
    """Locate the single Judge's fact-level findings in canonical stage evidence."""
    from .evaluation_contract import business_verdict, validate_business_judgment
    result={'analysis_category':'insufficient_evidence','analysis_reason':'未形成完整、适用且可定位的技术证据。','primary_root_cause':'Unknown','target_eligible':False,'retrieval_failure_stage':None,'evidence_checks':[]}
    if business_verdict(case) != 'FAIL':return result
    trace=(case.get('programmatic_metrics') or {}).get('retrieval_trace') or {}
    if trace.get('status') != 'completed' or any(not isinstance(trace.get(k),list) for k in ('candidates','final')):return result
    judge=case.get('judge_result') or {}
    try:validate_business_judgment(judge,case.get('model_answer',''),trace['final'],category=case.get('test_category'),question=case.get('question'),reference=case.get('reference_answer'))
    except ValueError:return result
    if corpus_chunks is None:corpus_chunks,corpus_fingerprint=_current_corpus(trace)
    if not corpus_fingerprint or trace.get('corpus_fingerprint') != corpus_fingerprint:return result
    by_id={c['chunk_id']:c for c in corpus_chunks or []}
    if not _canonical_final(trace,by_id):return result
    if not _canonical_final({'final':trace['candidates'],'parent_expand':False},by_id):return result
    sources=[{**c,'content':c.get('chunk_text') or c.get('text') or c.get('content','')} for c in corpus_chunks or []]
    def verified(support,entries):return isinstance(support,list) and bool(support) and all(quote_present(q,entries,display=True) for q in support)
    findings=[]
    from .safety_guard import check_safety
    guard=check_safety(case.get('question',''),case.get('model_answer',''),trace['final'],constraints=(case.get('programmatic_metrics',{}).get('evidence_sufficiency') or {}).get('source_constraints'))
    for finding in guard['findings']:
        findings.append(('Safety',None,finding))
    for check in judge['checks']:
        if check['met'] or check.get('scope_resolved') is not True:continue
        if verified(check['support'],trace['final']):
            findings.append(('Generation',None,{**check,'candidate_missing':False}))
        elif verified(check.get('reference_support'),sources) and isinstance(check.get('candidate_support'),list):
            candidate=verified(check.get('candidate_support'),trace['candidates'])
            if check['candidate_support'] and not candidate:continue  # Invalid diagnostic quote is not evidence of absence.
            findings.append(('Ranking' if candidate else 'Retrieval','ranking_context_selection' if candidate else 'candidate_recall',{**check,'candidate_missing':not candidate}))
    for issue in judge['issues']:
        if issue.get('scope_resolved') is not True:continue
        if verified(issue['support'],trace['final']) or issue['critical'] and verified(issue.get('reference_support'),sources):
            findings.append(('Safety' if issue.get('safety_violation') is True or issue['critical'] else 'Generation',None,issue))
    metrics=case.get('programmatic_metrics') or {}
    if not findings and type(metrics.get('latency_ms')) in (int,float) and metrics['latency_ms']>60000 and any(type(s.get('duration_ms')) in (int,float) and s['duration_ms']>0 for s in metrics.get('stages',[]) if isinstance(s,dict)):
        findings.append(('Performance',None,{'latency_ms':metrics['latency_ms'],'stages':metrics['stages']}))
    if findings:
        root,stage,_=findings[0]
        result.update(analysis_category='rag_failure',analysis_reason=next((f[2]['description'] for f in findings if f[2].get('rule_id')),judge['reason']),primary_root_cause=root,target_eligible=True,retrieval_failure_stage=stage,evidence_checks=[f[2] for f in findings])
    return result
