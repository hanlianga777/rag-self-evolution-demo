"""Eligibility for a fresh formal Baseline, reusing generation only, never verdicts."""
import json
from .diagnostic_evidence import digest
from .evaluation_contract import evaluation_identity,VERSIONS


def source_digest(run,cases):
    return digest({'snapshot':run['dataset_snapshot_json'],'config':run['config'],'judge':run['judge'],'result':run['result'],
        'status':run['status'],'mode':run['run_mode'],'data_source':run['data_source'],'cases':cases})


def saved_selection_error(trace,chunks):
    """Replay only the deterministic saved Rerank→threshold→Parent/TopK step."""
    import math
    from .knowledge_pipeline import expand_parents
    config=trace.get('config') or {};hits=trace.get('reranked')
    top_k=config.get('top_k');minimum=config.get('min_score',0)
    if type(top_k) is not int or top_k<=0 or type(minimum) not in (int,float) or not math.isfinite(minimum):return 'saved_selection_configuration_unverified'
    if not isinstance(hits,list) or any(not isinstance(e,dict) or type(e.get('score')) not in (int,float) or not math.isfinite(e['score']) for e in hits):return 'saved_rerank_scores_unverified'
    if any(e['score']<minimum for e in hits):return 'saved_rerank_threshold_contradiction'
    try:
        if trace.get('parent_expand'):
            parents={c['canonical_parent']['chunk_id']:c['canonical_parent'] for c in chunks if c.get('canonical_parent')}
            selected=expand_parents(hits,list(parents.values()),top_k)
        else:selected=hits[:top_k]
    except (ValueError,KeyError):return 'saved_parent_expansion_unverified'
    def signature(entries):
        return [{k:e.get(k) for k in ('chunk_id','parent_chunk_id','content','matched_child_ids','document_id','product','version')} for e in entries]
    if signature(selected)!=signature(trace.get('final') or []):return 'final_not_derived_from_saved_rerank_threshold_parent_topk'
    return None


def replay_eligibility(source,cases,snapshot,config,judge,chunks,fingerprint):
    from .diagnostics import _canonical_final
    from .canonical_evidence import full_norms
    from .ai_service import GENERATION_PROMPT_VERSION,GENERATION_BOUNDARY
    import hashlib
    frozen=json.loads(source['dataset_snapshot_json']);checks=[];executions={};rows={c['question_id']:c for c in cases}
    shared=[]
    if source.get('run_mode')!='real' or source.get('data_source')!='real' or source.get('status') not in {'partial','failed','completed'}:shared.append('source_not_inactive_real_execution')
    if frozen!=snapshot:shared.append('frozen_snapshot_changed')
    if source['config']!=config or config.get('run_target')!='baseline':shared.append('pipeline_or_generation_config_changed')
    if snapshot['corpus_fingerprint']!=fingerprint or source['config'].get('knowledge_identity')!=config.get('knowledge_identity'):shared.append('corpus_or_pipeline_identity_changed')
    original=source['judge']
    if original.get('generation_prompt_version')!=GENERATION_PROMPT_VERSION or original.get('generation_boundary_sha256')!=hashlib.sha256(GENERATION_BOUNDARY.encode()).hexdigest():shared.append('generation_contract_changed')
    if original.get('baseline_version')!=judge.get('baseline_version') or any(original.get('execution_snapshot',{}).get(k)!=judge.get('execution_snapshot',{}).get(k) for k in ('embedding_model','vector_index','generation_model','temperature')):shared.append('generation_model_embedding_or_configuration_changed')
    if original.get('evaluation_identity')==evaluation_identity(snapshot,judge):shared.append('new_evaluation_identity_required; use_same_identity_resume_instead')
    if original.get('model')!=judge.get('execution_snapshot',{}).get('generation_model'):shared.append('generation_model_not_verified')
    if len(rows)!=len(cases) or not set(rows)<=set(snapshot['question_ids']):shared.append('source_case_ids_invalid')
    by_id={c['chunk_id']:c for c in chunks}
    for question in snapshot['questions']:
        key=question['id'];reasons=list(shared);case=rows.get(key);cp=source['result'].get('checkpoints',{}).get(key,{})
        if case:
            metrics=case.get('programmatic_metrics') or {}
            execution={k:v for k,v in metrics.items() if not k.startswith('judge_') and k not in {'behavior_contract','evidence_sufficiency','safety_guard','evidence_coverage','retrieval_hit','retrieval_precision','retrieval_rank'}}
            execution.update(answer=case.get('model_answer'),retrieval=case.get('retrieved_chunks'))
            if any(case.get(k)!=question.get(k) for k in ('question','test_category','negative_subtype')) or case.get('reference_answer')!=(question.get('reference_answer') or question.get('expected_behavior','拒答或澄清')):reasons.append('saved_question_or_reference_changed')
            origin='scored_case_generation'
        else:execution=cp.get('execution') or {};origin='generation_checkpoint'
        trace=execution.get('retrieval_trace') or {}
        if not isinstance(trace,dict):trace={};reasons.append('retrieval_trace_not_an_object')
        if not isinstance(execution.get('answer'),str) or not execution.get('answer','').strip():reasons.append('complete_generated_answer_missing')
        if trace.get('status')!='completed' or trace.get('artifact_schema_version')!=3:reasons.append('complete_trace_schema_missing')
        if trace.get('question')!=question['question'] or trace.get('config')!=source['config'] or trace.get('corpus_fingerprint')!=fingerprint:reasons.append('trace_question_config_or_corpus_mismatch')
        for stage in ('candidates','reranked','final'):
            entries=trace.get(stage)
            if not isinstance(entries,list) or any(not isinstance(e,dict) or not isinstance(e.get('content'),str) for e in entries) or not _canonical_final({'final':entries,'parent_expand':trace.get('parent_expand') if stage=='final' else False},by_id):reasons.append(stage+': complete_canonical_source_unverified')
        # Full stage ancestry, not just counts or isolated Chunk IDs.
        candidate={e['chunk_id']:e for e in (trace.get('candidates') if isinstance(trace.get('candidates'),list) else []) if isinstance(e,dict)}
        if any(e.get('chunk_id') not in candidate or e.get('content')!=candidate[e['chunk_id']].get('content') for e in (trace.get('reranked') if isinstance(trace.get('reranked'),list) else []) if isinstance(e,dict)):reasons.append('rerank_not_derived_from_saved_candidates')
        if any(e.get('chunk_id') not in candidate for e in (trace.get('final') if isinstance(trace.get('final'),list) else []) if isinstance(e,dict)):reasons.append('final_not_bound_to_saved_candidate')
        selection_error=saved_selection_error(trace,chunks)
        if selection_error:reasons.append(selection_error)
        usage=(execution.get('token_usage') or {}).get('generation')
        if not isinstance(usage,dict) or usage.get('status')!='ok' or usage.get('provider')!='DeepSeek' or usage.get('requested_model')!=original.get('execution_snapshot',{}).get('generation_model') or not usage.get('request_sha256') or any(type(usage.get(k)) is not int for k in ('prompt_tokens','completion_tokens')):reasons.append('known_successful_generation_request_metadata_missing')
        if cp.get('unknown_execution',{}).get('generation') or cp.get('inflight')=='generation':reasons.append('unknown_generation_execution')
        try:norms=full_norms(question,chunks)
        except ValueError as error:reasons.append(str(error));norms=[]
        check={'question_id':key,'eligible':not reasons,'blockers':reasons,'origin':origin,'answer_sha256':digest(execution.get('answer')),
            'execution_sha256':digest(execution),'stage_sha256':{s:digest(trace.get(s)) for s in ('candidates','reranked','final')},
            'generation_request_sha256':usage.get('request_sha256') if isinstance(usage,dict) else None,
            'normative_sources':[{'source_id':n['chunk_id'],'full_characters':len(n['content']),'summary_characters':[len(s) for s in n['frozen_summary']]} for n in norms]}
        checks.append(check)
        if not reasons:executions[key]=execution
    ids=snapshot['question_ids']
    complete=len(checks)==len(ids) and {r['question_id'] for r in checks}==set(ids) and all(r['eligible'] for r in checks)
    return {'can_replay':complete,'source_run_id':source['id'],'source_sha256':source_digest(source,cases),
        'source_evaluation_identity':original.get('evaluation_identity'),'new_evaluation_identity':evaluation_identity(snapshot,judge),
        'new_versions':{k:judge[k] for k in VERSIONS},
        'total':len(ids),'reusable':len(executions),'eligibility':checks,'executions':executions,
        'generation_calls':0,'judge_calls':len(ids),'max_attempts_per_question':3,'max_judge_calls':len(ids)*3,
        'request_output_limit':32768,'timing_provenance':'historical_generation_not_current_latency','new_judge':judge}
