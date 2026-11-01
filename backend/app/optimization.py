"""Manually started, bounded A/B/C Optimization Agent for V1.3."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from collections import Counter

from .providers import ProviderRequestError, provider_error_details
from .diagnostics import diagnostic_view
from .agent_inputs import prepare_baseline_rows, retrieval_facts
from .paid_run import provider_task
from .telemetry import collect_usage, measure, cost_fields
from .policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS, search_space_contract, validate_candidate_config


INTERVENTIONS = {
    'query_expansion': ({'query_rewrite','multi_query','hyde','alias_mapping','query_decompose'}, {'recall_missing'}),
    'candidate_recall': ({'candidate_k','hybrid_search','hybrid_alpha'}, {'recall_missing'}),
    'context_selection': ({'top_k','rerank','min_score','retrieval_max_tokens'}, {'ranking_omission','retrieval_noise'}),
    'source_filter': ({'metadata_filter'}, {'retrieval_noise'}),
    'grounded_generation': ({'prompt_strategy','generation_thinking'}, {'final_sufficient','confirmed_claim','safety_failure'}),
    'stage_performance': (set(search_space_contract()), {'measured_latency'}),
}


PRIORITY_PARAMETERS = {
    '检索失败': ['query_rewrite','hyde','multi_query','candidate_k','hybrid_search','hybrid_alpha','alias_mapping','query_decompose'],
    '检索噪声': ['rerank','top_k','min_score','metadata_filter','retrieval_max_tokens'],
    '回答问题 / 过度拒答': ['prompt_strategy','generation_thinking'],
    '速度门槛不过': ['generation_thinking','hyde','multi_query','query_rewrite','query_decompose','candidate_k','top_k','rerank'],
}

PARAMETER_ACTIONS = {
    'candidate_k':'调整候选池','top_k':'调整TopK','min_score':'调整最低分数线',
    'hybrid_search':'调整混合检索','hybrid_alpha':'调整混合比例','rerank':'调整重排',
    'query_rewrite':'调整查询改写','multi_query':'调整多路查询','hyde':'调整HyDE',
    'metadata_filter':'调整元数据过滤','alias_mapping':'调整别名映射',
    'prompt_strategy':'调整回答策略','generation_thinking':'调整思考档位',
    'query_decompose':'调整查询拆解','retrieval_max_tokens':'调整检索长度上限',
}


def validate_intervention(candidate, targets, baseline):
    """Priority directions are advice; validate actual changes and saved targets only."""
    diff=candidate.get('config_diff')
    if not isinstance(diff,dict) or not diff or any(value==baseline.get(key) for key,value in diff.items()):
        raise ValueError('Config Diff必须包含实际参数改动')
    config={**baseline,**diff}
    if config.get('hybrid_search') is False and 'hybrid_alpha' not in diff:
        config.pop('hybrid_alpha',None)
    check=validate_candidate_config(config)
    if not check['valid']:raise ValueError('非法参数：'+'；'.join(check['errors']))
    references=candidate.get('target_bad_cases')
    if not isinstance(references,list) or not references:
        raise ValueError('方案必须有目标错题')
    for reference in references:
        if reference not in targets:raise ValueError('目标不是本次运行保存的错题')
        if not diagnostic_view(targets[reference])['target_eligible']:
            raise ValueError('目标记录缺失，先补齐记录')
    for field in ('hypothesis','why','expected_improvement','risk'):
        if not isinstance(candidate.get(field),str) or not candidate[field].strip():
            raise ValueError('缺少方案思路、理由、预期改善或风险')


def build_agent_prompt(bad_cases, base_config, prior_candidates, failed_gates, labels):
    """Build the exact Agent request without a Provider or persistence side effect."""
    system = ('你是RAG优化Agent。根据保存的错题诊断提出优化方案。'
              '一个方案=一个思路+必要的几个参数，可以跨环节联动。对照表表示优先尝试，不限制其他参数。'
              '只返回JSON，格式：{"candidates":[{"id":"A","action_name":"中文动作短语",'
              '"hypothesis":"一个优化思路","why":"对应错题及理由","target_bad_cases":["题号或错题ID"],'
              '"config_diff":{},"expected_improvement":"预期改善","risk":"可能退化"}]}。')
    rows=[]
    for row in bad_cases:
        view=row.get('diagnostic_view') or diagnostic_view(row['result'])
        rows.append({'id':row['id'],'question_id':row['question_id'],
                     'question':row['result'].get('question'),
                     'diagnosis_category':view.get('diagnosis_category',view['primary_root_cause']),
                     'reason':view['analysis_reason'],
                     'retrieval_facts':row.get('retrieval_facts') or retrieval_facts(row['result'])})
    prompt={
        'goal':{'objective':'通过11项门槛、错题总数少于Baseline、至少修好1道目标错题，安全关键题和提示注入题无新错。普通新错留给方案D处理。',
                'failed_gates':failed_gates,'candidate_labels':labels,'baseline_configuration':base_config},
        'bad_cases':rows,
        'priority_parameters':PRIORITY_PARAMETERS,
        'allowed_parameter_values':search_space_contract(),
        'prior_sandbox_results':[{'id':c['id'],'action_name':c.get('reasoning',{}).get('action_name'),
            'hypothesis':c.get('reasoning',{}).get('hypothesis'),'configuration':c['config'],'status':c['status'],
            'result':{key:c.get('result',{}).get(key) for key in ('qualification','bad_case_count','all_fixed_question_ids','new_failure_question_ids','regression','gates')}} for c in prior_candidates],
    }
    return system,prompt


def strategy_case(row):
    """All business failures enter processing; execution eligibility stays separate."""
    case=row.get('result',{})
    view=row.get('diagnostic_view') or diagnostic_view(case)
    return {'id':row.get('id'),'question_id':row.get('question_id'),'category':view['primary_root_cause'],
            'result':{key:case.get(key) for key in ('question','reference_answer','model_answer','test_category','negative_subtype')} | {'primary_root_cause':view['primary_root_cause']},
            'retrieval_trace':(case.get('programmatic_metrics') or {}).get('retrieval_trace'),
            'golden_evidence':{key:(case.get('programmatic_metrics') or {}).get('evidence_sufficiency',{}).get(key) for key in ('source_constraints','facts')},
            'diagnostic_view':{key:view.get(key) for key in ('diagnosis_category','priority','retrieval_metrics','analysis_category','analysis_reason','primary_root_cause','target_eligible','is_technical_bad_case','evidence_checks','optimization_directions','trace_observations','retrieval_failure_stage','context_selection_options','optimization_blockers','diagnostic_gaps','diagnosis_complete','experiment_plan')}}


def strategy_candidate(candidate):
    return {key:candidate.get(key) for key in ('id','config','status')} | {
        'reasoning':{key:value for key,value in candidate.get('reasoning',{}).items() if key!='target_diagnosis'},
        'result':{key:value for key,value in candidate.get('result',{}).items() if key not in {'checkpoints','all_bad_case_audit'}}}


def unique_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Agent JSON存在重复键：'+key)
        result[key]=value
    return result


def reject_constant(value):
    raise ValueError('Agent JSON包含非有限数值：'+value)


def finite_float(value):
    result=float(value)
    if not math.isfinite(result):raise ValueError('Agent JSON包含非有限数值')
    return result


def prepare_response(content,base_config,bad_cases,prior_candidates,completed,round_number,labels,trigger_id,monitoring_target_event_ids,audit):
    """One offline validation path for fresh and already-paid responses; no semantic repairs."""
    prior=[base_config]+[item['config'] for item in prior_candidates]
    target_reference_map={key:{'bad_case_id':item['id']} for item in bad_cases for key in (item['id'],item['question_id'])}
    audit["validation_stage"] = "json_parse"
    result = json.loads(content, object_pairs_hook=unique_keys, parse_constant=reject_constant, parse_float=finite_float)
    audit["parsed_json"] = result
    audit["validation_stage"] = "schema"
    if not isinstance(result, dict) or not isinstance(result.get("candidates"), list):
        audit.update(failed_field="candidates", actual_value=result.get("candidates") if isinstance(result, dict) else result, expected_type="array", allowed_values=None)
        raise ValueError("Agent 输出必须包含 candidates 数组")
    candidates = result.get("candidates", [])
    audit["parsed_candidates"] = candidates
    audit.update(response_contract_version='agent-response-2',rejected_candidates=[],response_warnings=[])
    if len(candidates)<len(labels) and not isinstance(result.get('insufficient_evidence'),str):
        audit['response_warnings'].append({'field':'insufficient_evidence','reason':'model_did_not_provide_explanation'})
    counts=Counter(c.get('id') for c in candidates if isinstance(c,dict) and isinstance(c.get('id'),str))
    staged = []
    for index,candidate in enumerate(candidates):
        try:
            audit["validation_stage"] = "schema"
            audit.update(failed_candidate_id=candidate.get('id') if isinstance(candidate,dict) else None,
                         failed_field=None,actual_value=None,expected_type=None,allowed_values=None,validation_issues=[])
            if not isinstance(candidate,dict) or candidate.get('id') not in labels or counts.get(candidate.get('id'))!=1:
                audit['failed_field']='id'
                raise ValueError('Candidate必须为对象且标签唯一、属于本轮允许标签')
            candidate = dict(candidate)  # Preserve the parsed Provider reply in the audit.
            for field in ("hypothesis", "why", "risk", "expected_improvement", "target_bad_cases", "config_diff"):
                value = candidate.get(field)
                if field in ("hypothesis", "why", "risk", "expected_improvement"):
                    expected = "non-empty string"
                    valid = isinstance(value, str) and bool(value.strip())
                elif field == "target_bad_cases":
                    expected = "array of non-empty strings"
                    valid = isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)
                else:
                    expected = "object"
                    valid = isinstance(value, dict)
                if not valid:
                    audit.update(failed_field=field, actual_value=value, expected_type=expected, allowed_values=None)
                    raise ValueError(f"Agent Candidate {candidate['id']} 缺少有效 {field}")
            unknown_targets = [value for value in candidate["target_bad_cases"] if value not in target_reference_map]
            if unknown_targets:
                audit.update(failed_field="target_bad_cases", actual_value=candidate["target_bad_cases"], expected_type="identifiers from current persisted evidence", allowed_values=sorted(target_reference_map))
                raise ValueError(f"Agent Candidate {candidate['id']} target_bad_cases 引用了不存在的当前证据：" + ", ".join(unknown_targets))
            canonical=[target_reference_map[r]['bad_case_id'] for r in candidate['target_bad_cases']]
            if len(canonical)!=len(set(canonical)):
                audit['failed_field']='target_bad_cases'
                raise ValueError('同一目标被重复引用（含题号与Case别名）')
            selected=[item for item in bad_cases if item['id'] in candidate['target_bad_cases'] or item['question_id'] in candidate['target_bad_cases']]
            roots={item['question_id']:item['diagnostic_view']['primary_root_cause'] for item in selected}
            candidate['target_root_causes']=roots
            candidate['root_cause']=next(iter(set(roots.values()))) if len(set(roots.values()))==1 else 'Mixed'
            candidate['root_cause_evidence']=candidate['target_bad_cases']
            candidate.setdefault('action_name',' + '.join(PARAMETER_ACTIONS.get(key,key) for key in candidate['config_diff']))
            if not isinstance(candidate['action_name'],str) or not candidate['action_name'].strip():
                raise ValueError('动作名称不能为空')
            if candidate["hypothesis"].strip() in {item.get("reasoning", {}).get("hypothesis", "").strip() for item in prior_candidates}:
                audit.update(failed_field="hypothesis", actual_value=candidate["hypothesis"], expected_type="new hypothesis", allowed_values=None)
                raise ValueError("下一轮必须提出新的 Hypothesis")
            diff = candidate["config_diff"]
            config = {**base_config, **diff}
            if config.get("hybrid_search") is False and "hybrid_alpha" not in diff:
                config.pop("hybrid_alpha", None)
            audit["validation_stage"] = "search_space"
            check = validate_candidate_config(config, prior_configs=prior, completed_evals=completed)
            if not check["valid"]:
                audit["validation_issues"] = check["issues"]
                if check["issues"]:
                    issue = check["issues"][0]
                    audit.update(failed_field=issue["field"], actual_value=issue["actual"], expected_type=issue["expected_type"], allowed_values=issue["allowed_values"])
                raise ValueError("Agent Candidate Config 不符合冻结 Search Space：" + "; ".join(check["errors"]))
            audit['validation_stage']='intervention'
            target_cases={reference:item['result'] for item in bad_cases for reference in (item['id'],item['question_id'])}
            validate_intervention(candidate,target_cases,base_config)
            candidate['intervention_direction']=candidate.get('intervention_direction') or next((name for name,(keys,_) in INTERVENTIONS.items() if name!='stage_performance' and set(diff)<=keys),'combined')
            prior.append(config)
            staged.append((candidate, config))
        except (ValueError,TypeError,KeyError) as error:
            audit['rejected_candidates'].append({'index':index,'id':candidate.get('id') if isinstance(candidate,dict) else None,
                'stage':audit['validation_stage'],'field':audit.get('failed_field'),'reason':str(error),
                'validation_issues':audit.get('validation_issues',[]),
                'actual_value':audit.get('actual_value'),'expected_type':audit.get('expected_type'),'allowed_values':audit.get('allowed_values')})
    audit["validation_stage"] = "completed"
    audit["failed_candidate_id"] = None
    batch = []
    for candidate, config in staged:
        batch.append((f"R{round_number}-{candidate['id']}", config, {
            "intervention_direction":candidate['intervention_direction'], "supporting_directions":candidate.get('supporting_directions',[]), "action_name":candidate["action_name"], "intervention_contract_version":"agent-closure-4", "experiment_kind":candidate.get("experiment_kind","confirmed"), "falsification":candidate.get("falsification"), "parameter_dependencies":candidate.get('parameter_dependencies',[]), "evidence_assertions":candidate.get('evidence_assertions',[]), "performance_stage":candidate.get('performance_stage'),
            "target_root_causes": candidate.get("target_root_causes"), "provenance": candidate.get("provenance"), "target_group": candidate.get("target_group") if isinstance(candidate.get("target_group"),str) else None, "root_cause": candidate["root_cause"], "root_cause_evidence": candidate["root_cause_evidence"], "expected_improvement": candidate["expected_improvement"], "target_diagnosis": [strategy_case(item) for item in bad_cases if item["id"] in candidate["target_bad_cases"] or item["question_id"] in candidate["target_bad_cases"]], "root_cause_cluster": result.get("root_cause_cluster"), "observed_evidence": candidate["target_bad_cases"], "hypothesis": candidate["hypothesis"], "proposal": candidate["why"], "risk": candidate["risk"],
            "changed_parameters": {key: value for key, value in config.items() if value != base_config.get(key)}, "source_trigger_id": trigger_id, "monitoring_target_event_ids": monitoring_target_event_ids, "round": round_number, "candidate_label": candidate["id"],
        }))
    audit.update(generated_candidate_count=len(batch),returned_candidate_count=len(candidates),requested_candidate_count=len(labels),
                 response_status='partial' if batch and audit['rejected_candidates'] else 'accepted' if batch else 'rejected' if candidates else 'empty')
    if candidates and not batch:
        first=audit['rejected_candidates'][0]
        audit.update(validation_stage=first['stage'],failed_candidate_id=first['id'],failed_field=first['field'],actual_value=first['actual_value'],
                     expected_type=first['expected_type'],allowed_values=first['allowed_values'],validation_issues=first['validation_issues'])
        raise ValueError('没有合法Candidate：'+'；'.join(r['reason'] for r in audit['rejected_candidates']))
    return result,batch


class OptimizationAgent:
    def __init__(self, store, provider):
        self.store = store
        self.provider = provider

    @provider_task('agent')
    def generate(self, baseline_run_id: str, trigger_id: str | None = None, experiment_id: str | None = None):
        # Check identity before budget reads; the short claim serializes duplicate starts.
        self.store.require_current_baseline(baseline_run_id)
        # Real model requests must share the current foundation before claiming work.
        settings = getattr(self.provider, 'settings', None)
        if isinstance(getattr(settings, 'model', None), str):
            from types import SimpleNamespace
            from .ai_service import generation_contract
            from .evaluation import EvaluationRunner
            runtime = SimpleNamespace(generation_contract=generation_contract(), model=settings.model)
            EvaluationRunner(self.store, runtime)._require_generation_contract(self.store.evaluation_run(baseline_run_id)['judge'])
        baseline = self.store.evaluation_run(baseline_run_id)
        bad_cases = [item for item in self.store.bad_case_rows(baseline_run_id) if item["run_id"] == baseline_run_id]
        audited_cases = prepare_baseline_rows(baseline, bad_cases)
        audited_cases = [{**item, 'category':item['diagnostic_view']['primary_root_cause']} for item in audited_cases]
        from .evaluation_contract import business_verdict
        bad_cases = [item for item in audited_cases if business_verdict(item['result'])=='FAIL' or (item['result'].get('evaluation_outcome') or {}).get('contract_version')!='business-vnext-1' and item['result'].get('passed') is False]
        diagnostic_tasks=[]
        for item in bad_cases:
            view=item['diagnostic_view'];plan=view.get('experiment_plan',{})
            ready=view['target_eligible'] and view.get('diagnosis_complete',True)
            diagnostic_tasks.append({'question_id':item['question_id'],'case_id':item['id'],
                'status':'ready_for_experiment' if ready else plan.get('status','capability_gap'),
                'next_action':'sandbox_full_snapshot' if ready else plan.get('next_action','repair_sources_or_trace'),
                'experiment_plan':plan,'gaps':view.get('diagnostic_gaps',[]),'blockers':plan.get('blockers',[])})
        trigger = self.store.optimization_trigger(trigger_id) if trigger_id else None
        existing_id = experiment_id or (trigger or {}).get("optimization_run_id") or self.store.current_baseline_identity()["current_experiment_id"]
        existing = self.store.experiment(existing_id) if existing_id else None
        confirmed_context = (existing or {}).get("result", {})
        trigger = trigger or self.store.optimization_trigger(confirmed_context.get("trigger_id"))
        event = None
        if existing and existing["baseline_run_id"] == baseline_run_id and trigger and trigger["status"] == "human_confirmed" and trigger["optimization_run_id"] == existing_id:
            event = next((item for item in self.store.monitoring_events() if item["id"] == trigger["event_id"] and item["bad_case"] and item["determinable"]), None)
        baseline = self.store.evaluation_run(baseline_run_id)
        base_config = {**DEFAULT_PIPELINE_CONFIG, **baseline["config"]}
        base_config.pop("run_target", None)
        base_config.pop("knowledge_identity", None)
        experiment_id, prior_candidates, round_number, completed, generation_token = self.store.claim_agent_generation(baseline_run_id, trigger_id, existing_id)
        if not bad_cases:
            reason='暂无足够依据生成合格优化假设：没有具备实际证据与Trace的可验证Baseline目标；Monitoring事件须先补齐同等证据'
            self.store.save_agent_round(experiment_id, [], {'generation_status':'insufficient_evidence','insufficient_evidence':reason,'generated_candidate_count':0,'round':round_number,'provider_called':False,'all_bad_case_audit':[{k:v for k,v in row.items() if k!='result_json'} for row in audited_cases]}, generation_token=generation_token)
            return self.store.experiment(experiment_id)
        failed_questions={row['question_id'] for row in bad_cases}
        verified=[c for c in prior_candidates if c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified')]
        best=max(verified,key=lambda c:len(set(c['result'].get('all_fixed_question_ids',[])) & failed_questions),default=None)
        fixed=failed_questions & set(best['result'].get('all_fixed_question_ids',[])) if best else set()
        processing_progress={'baseline_failed_question_ids':sorted(failed_questions),'verified_configuration_id':best['id'] if best else None,
            'fixed_question_ids':sorted(fixed),'remaining_question_ids':sorted(failed_questions-fixed),'status':'unfinished' if failed_questions-fixed else 'verified_complete'}
        context = self.store.experiment(experiment_id)["result"]
        trigger_id = trigger_id or context.get("trigger_id")
        monitoring_context = {"trigger": self.store.optimization_trigger(trigger_id), "event": event or context.get("monitoring_event"), "confirmed_baseline_id": context.get("baseline_id"), "golden_id": context.get("golden_id"), "corpus_fingerprint": context.get("corpus_fingerprint")} if trigger_id else None
        monitoring_target_event_ids = [event["id"]] if event else []
        target_reference_map = {}
        for item in bad_cases:
            reference = {"source": "baseline_bad_case", "baseline_id": baseline_run_id, "bad_case_id": item["id"], "question_id": item["question_id"], "primary_root_cause": item["diagnostic_view"]["primary_root_cause"], "analysis_category": item["diagnostic_view"]["analysis_category"], "root_cause_evidence": item["diagnostic_view"]["evidence_checks"], "diagnostic_view":strategy_case(item)["diagnostic_view"]}
            target_reference_map[item["id"]] = reference
            target_reference_map[item["question_id"]] = reference
        if event:
            target_reference_map[event["id"]] = {"source": "monitoring_event", "event_id": event["id"], "trigger_id": trigger_id}
        evaluation_budget = {"used": completed, "max": MAX_EVALS, "reserved_for_d": 1}
        gate_results = baseline["result"].get("gates")
        persisted_gates = (gate_results or {}).get("gates")
        failed_gates = [gate for gate in persisted_gates if gate.get("passed") is False] if isinstance(persisted_gates, list) else None
        labels = ['A', 'B', 'C'][:min(3, MAX_EVALS - 1 - completed)]
        audit = {"optimization_run_id": experiment_id, "baseline_id": baseline_run_id, "timestamp": datetime.now(timezone.utc).isoformat(), "provider_raw_text": None, "parsed_json": None, "parsed_candidates": None, "validation_stage": "provider", "failed_candidate_id": None, "failed_field": None, "actual_value": None, "expected_type": None, "allowed_values": None, "validation_issues": [], "diagnostic_tasks":diagnostic_tasks, "processing_progress":processing_progress, "all_bad_case_audit": [{k:v for k,v in row.items() if k!='result_json'} for row in audited_cases], "root_cause_counts": dict(Counter(item['diagnostic_view']['primary_root_cause'] for item in bad_cases)), "source_bad_case_ids": [item["id"] for item in bad_cases], "monitoring_context": monitoring_context, "monitoring_target_event_ids": monitoring_target_event_ids, "target_reference_map": target_reference_map, "evaluation_budget": evaluation_budget, "baseline_gate_results": gate_results, "failed_gates": failed_gates}
        system,prompt=build_agent_prompt(bad_cases,base_config,prior_candidates,failed_gates,labels)
        try:
            stages = []
            with collect_usage() as usage, measure(stages, 'optimization_agent'):
                try:
                    user=json.dumps(prompt,ensure_ascii=False)
                    audit['validation_stage']='request_validation'
                    if callable(getattr(self.provider,'request_summary',None)):
                        audit['request_summary']=self.provider.request_summary(system,user,json_mode=True)
                    audit['validation_stage']='provider'
                    previous = confirmed_context
                    request_hash = audit.get('request_summary', {}).get('request_sha256')
                    if (request_hash and previous.get('validation_stage') == 'persistence'
                            and previous.get('baseline_id') == baseline_run_id
                            and previous.get('request_summary', {}).get('request_sha256') == request_hash
                            and isinstance(previous.get('provider_raw_text'), str)
                            and any(item.get('status') == 'ok' for item in previous.get('token_usage', []))):
                        content = previous['provider_raw_text']
                        audit['response_reuse'] = {'request_sha256': request_hash, 'source_timestamp': previous['timestamp'], 'new_provider_call': False}
                    else:
                        content=self.provider.complete(system,user,json_mode=True)
                finally:
                    if audit.get('response_reuse'):
                        audit.update({k:previous.get(k) for k in ('token_usage','cost_estimation','estimated_cost')})
                        audit.update(stages=previous.get('stages',[]),revalidation_stages=stages,new_provider_calls=0)
                    else:
                        audit.update(token_usage=usage, stages=stages, **cost_fields(getattr(getattr(self.provider, 'settings', None), 'model', None), usage))
            audit["provider_raw_text"] = content
            result,batch=prepare_response(content,base_config,bad_cases,prior_candidates,completed,round_number,labels,trigger_id,monitoring_target_event_ids,audit)
            audit["validation_stage"] = "persistence"
            self.store.save_agent_round(experiment_id, batch, {**result, **audit, "generation_status":"partial" if audit["rejected_candidates"] else "completed" if batch else "no_candidates", "requested_candidate_count":len(labels), "generated_candidate_count":len(batch), "validation_stage": "completed", "round": round_number, "evaluation_budget": evaluation_budget}, generation_token=generation_token)
            return self.store.experiment(experiment_id)
        except Exception as error:
            if isinstance(error,ProviderRequestError):audit['validation_stage']='request_validation'
            audit['generation_status']='failed'
            audit['provider_error']=provider_error_details(error,audit['validation_stage'])
            message=f"{error}；失败阶段：{audit['validation_stage']}；可重试：{'是' if audit['provider_error']['retryable'] else '否'}"
            audit["validation_error"] = message
            self.store.save_agent_trace(experiment_id, "failed", audit, message, generation_token=generation_token)
            raise ValueError(message) from error
