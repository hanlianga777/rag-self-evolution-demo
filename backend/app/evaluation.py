"""Snapshot-bound Evaluation runner and V1.0.1 metric aggregation."""

from __future__ import annotations

import json
import time
import math
from .telemetry import collect_usage
from .safety_guard import check_safety, adjudicate
from statistics import mean
from .evaluation_contract import VERSIONS, policy_current, evaluation_identity, observe_evidence, resolve_evidence, compare_cases, assess_claims, validate_business_judgment, business_check_roles, quote_present

from .policy import DEFAULT_PIPELINE_CONFIG, calculate_overall_score, evaluate_gates, evaluate_regression, qualify_candidate


ROOT_CAUSE_BY_TAG = {
    "Query Failure": "Query", "Retrieval Failure": "Retrieval", "Ranking Failure": "Ranking",
    "Metadata / Entity Failure": "Metadata / Entity", "Generation Failure": "Generation",
    "Evidence / Citation Failure": "Generation", "Hallucination": "Generation",
    "Unsafe Answer": "Safety", "Safety Failure": "Safety", "Performance Failure": "Performance",
}


def root_cause_layers(failure_tags: list[str], coverage: dict | None = None, test_category: str | None = None) -> tuple[str, list[str]]:
    """Preliminary diagnosis from observed pipeline evidence; legacy callers retain tag order."""
    layers = list(dict.fromkeys(ROOT_CAUSE_BY_TAG[tag] for tag in failure_tags if tag in ROOT_CAUSE_BY_TAG))
    if test_category is None:
        return (layers[0], layers[1:]) if layers else ("None", [])
    if not failure_tags:
        return "None", []
    if "Safety" in layers:
        primary = "Safety"
    elif test_category in {"positive", "ablation"} and any(layer in layers for layer in {"Generation", "Retrieval", "Ranking"}):
        candidate = (coverage or {}).get('candidate_recall', {}).get('all_hit')
        final = (coverage or {}).get('final_context', {}).get('all_hit')
        if not (coverage or {}).get('required_chunk_ids'):
            primary = "Unknown"
        elif candidate is False:
            primary = "Retrieval"
        elif candidate is True and final is False:
            primary = "Ranking"
        elif final is True:
            primary = "Generation"
        else:
            primary = "Unknown"
    else:
        primary = layers[0] if layers else "Unknown"
    return primary, [layer for layer in layers if layer != primary]


def _percentile(values: list[float], percentile: float):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * percentile))]


def _mean(values: list[float]):
    return round(mean(values), 2) if values else None


def policy_behavior(case):
    value=case.get('programmatic_metrics',{}).get('behavior_contract',{}).get('effective_pass',case.get('judge_result',{}).get('behavior_pass'))
    return value if type(value) is bool else None


def summarize_evaluation_cases(cases: list[dict], *, complete=True) -> dict:
    """Aggregate persisted case records without inventing absent group metrics."""
    groups = {"positive": [], "ablation": [], "negative": []}
    for case in cases:
        if case.get("test_category") in groups:
            groups[case["test_category"]].append(case)

    def quality(group: str, key: str):
        values = []
        for item in groups[group]:
            value = item.get("judge_result", {}).get(key)
            if isinstance(value, (int, float)):
                values.append(float(value) * (25 if key == "correctness" else 100))
        return _mean(values)

    metrics = {
        "positive_correctness": quality("positive", "correctness"),
        "positive_faithfulness": quality("positive", "faithfulness"),
        "positive_completeness": quality("positive", "completeness"),
        "ablation_correctness": quality("ablation", "correctness"),
        "ablation_faithfulness": quality("ablation", "faithfulness"),
        "ablation_completeness": quality("ablation", "completeness"),
    }

    negatives = groups["negative"]
    safe = lambda item: None if policy_behavior(item) is None else 100.0 if policy_behavior(item) else 0.0
    metrics.update({
        "safe_rejection_rate": _mean([safe(item) for item in negatives]) if all(policy_behavior(item) is not None for item in negatives) else None,
        "safety_critical_accuracy": _mean([safe(item) for item in negatives if item.get("severity") == "critical"]) if all(policy_behavior(item) is not None for item in negatives if item.get("severity") == "critical") else None,
        "prompt_injection_resistance": _mean([safe(item) for item in negatives if item.get("negative_subtype") == "prompt_injection"]) if all(policy_behavior(item) is not None for item in negatives if item.get("negative_subtype") == "prompt_injection") else None,
    })
    latency_seconds = [item["programmatic_metrics"]["latency_ms"] / 1000 for item in cases if isinstance(item.get("programmatic_metrics", {}).get("latency_ms"), (int, float))]
    metrics["latency_p50_seconds"] = _percentile(latency_seconds, .5)
    metrics["latency_p99_seconds"] = _percentile(latency_seconds, .99)
    hits = [item["programmatic_metrics"]["retrieval_hit"] for item in cases if item.get("programmatic_metrics", {}).get("retrieval_hit") is not None]
    precisions = [item["programmatic_metrics"]["retrieval_precision"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("retrieval_precision"), (int, float))]
    reciprocal_ranks = [1 / item["programmatic_metrics"]["retrieval_rank"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("retrieval_rank"), int) and item["programmatic_metrics"]["retrieval_rank"] > 0]
    ttfts = [item["programmatic_metrics"]["ttft_ms"] / 1000 for item in cases if isinstance(item.get("programmatic_metrics", {}).get("ttft_ms"), (int, float))]
    input_tokens = [item["programmatic_metrics"]["input_tokens"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("input_tokens"), (int, float))]
    output_tokens = [item["programmatic_metrics"]["output_tokens"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("output_tokens"), (int, float))]
    provider_costs = [item["programmatic_metrics"]["provider_cost"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("provider_cost"), (int, float))]
    overall = calculate_overall_score(metrics)
    result = {
        'safety_verification_complete':not any(c.get('evaluation_outcome',{}).get('safety_review_required') for c in cases),
        'safety_review_question_ids':[c.get('question_id') for c in cases if c.get('evaluation_outcome',{}).get('safety_review_required')],
        "completed": len(cases), "failed": sum(not item.get("passed", False) for item in cases),
        "group_metrics": {group: {key: metrics[f"{group}_{key}"] for key in ("correctness", "faithfulness", "completeness")} for group in ("positive", "ablation")},
        "safety_metrics": {key: metrics[key] for key in ("safe_rejection_rate", "safety_critical_accuracy", "prompt_injection_resistance")},
        "metrics": metrics, "gates": evaluate_gates(metrics), "overall_score": overall["score"], "overall_score_status": overall["status"],
        "comparison_metrics": {"ttft_seconds": _mean(ttfts), "ttft_target_status": "WARNING" if ttfts and _mean(ttfts) > 5 else "OK" if ttfts else "NOT_MEASURED", "input_tokens": sum(input_tokens) if input_tokens else None, "output_tokens": sum(output_tokens) if output_tokens else None, "token_cost": round(sum(provider_costs), 6) if provider_costs else None, "token_cost_status": "MEASURED" if provider_costs else "Token Usage / Provider Cost unavailable", "recall_at_k": round(100 * sum(bool(hit) for hit in hits) / len(hits), 2) if hits else None, "precision_at_k": _mean(precisions), "mrr": _mean(reciprocal_ranks)},
        "bad_case_count": sum(not item.get("passed", False) for item in cases),
    }
    if not complete:
        result.update(overall_score=None, overall_score_status='NOT_EVALUABLE', gates={**evaluate_gates({}), 'passed':None})
    return result


def gate_details(cases: list[dict], gates: list[dict]) -> list[dict]:
    """Explain stored gates from the same persisted case inputs used by aggregation."""
    details = []
    for gate in gates:
        metric = gate["metric"]
        selected = cases
        if metric.startswith("positive_") or metric.startswith("ablation_"):
            group, field = metric.split("_", 1)
            selected = [item for item in cases if item.get("test_category") == group]
            values = [(item, item.get("judge_result", {}).get(field)) for item in selected]
            contributions = [{"question_id": item.get("question_id"), "value": round(float(value) * (25 if field == "correctness" else 100), 2), "passed": item.get("passed")} for item, value in values if isinstance(value, (int, float))]
            formula = "算术平均；Correctness 原始 0–4 分乘以 25" if field == "correctness" else "逐题 0–1 分乘以 100 后算术平均"
        elif metric in {"safe_rejection_rate", "safety_critical_accuracy", "prompt_injection_resistance"}:
            selected = [item for item in cases if item.get("test_category") == "negative" and (metric != "safety_critical_accuracy" or item.get("severity") == "critical") and (metric != "prompt_injection_resistance" or item.get("negative_subtype") == "prompt_injection")]
            contributions = [{"question_id": item.get("question_id"), "value": None if policy_behavior(item) is None else 100.0 if policy_behavior(item) else 0.0, "passed": item.get("passed")} for item in selected]
            formula = "适用负向题政策行为通过比例；旧记录使用保存的 behavior_pass"
        else:
            contributions = [{"question_id": item.get("question_id"), "value": round(item["programmatic_metrics"]["latency_ms"] / 1000, 2), "passed": item.get("passed")} for item in cases if isinstance(item.get("programmatic_metrics", {}).get("latency_ms"), (int, float))]
            formula = "排序后取 floor((n-1)×p) 位；p=0.50" if metric == "latency_p50_seconds" else "排序后取 floor((n-1)×p) 位；p=0.99"
        failed = [item for item in contributions if item["value"] is not None and (item["value"] < gate["threshold"] if gate["operator"] == ">=" else item["value"] > gate["threshold"])]
        details.append({**gate, "formula": formula, "included_cases": len(contributions), "contributing_cases": contributions, "failed_cases": failed})
    return details


class EvaluationRunner:
    def __init__(self, store, runtime):
        self.store, self.runtime = store, runtime

    def snapshot_items(self, snapshot):
        frozen = {item['id']: item for item in snapshot.get('questions', [])}
        items = []
        for key in snapshot.get('question_ids', []):
            try:
                current = self.store.question(key)
            except KeyError:
                if key not in frozen or 'test_category' not in frozen[key]:
                    raise ValueError('历史Snapshot缺少完整题目/类别，不能按当前题目补造')
                current = {'id':key, **frozen[key], 'raw':frozen[key]}
            raw = frozen.get(key, current['raw'])
            items.append({**current, 'question': raw['question'], 'reference_answer': raw.get('reference_answer'), 'evidence': raw.get('evidence', raw.get('acceptable_evidence', [])), 'raw': raw, 'test_category': raw.get('test_category', current['test_category']), 'negative_subtype': raw.get('negative_subtype', current.get('negative_subtype'))})
        return items

    def baseline_inputs(self, resume_source_id=None):
        snapshots = self.store.dataset_snapshots()
        if not snapshots:
            raise ValueError("正式评测需要已批准（approved）且显式创建的 Golden Snapshot")
        snapshot = snapshots[0]["snapshot"]
        approved = self.snapshot_items(snapshot)
        categories = {item["test_category"] for item in approved}
        negative_subtypes = {item.get("negative_subtype") for item in approved if item["test_category"] == "negative"}
        if not {"positive", "ablation", "negative"}.issubset(categories) or not {"safety_critical", "prompt_injection"}.issubset(negative_subtypes):
            raise ValueError("正式评测需要完整 approved Golden：Positive、Ablation、Negative、Safety Critical 与 Prompt Injection")
        production = self.store.active_production() or {"config": {}}
        config = {**DEFAULT_PIPELINE_CONFIG, **production["config"], "run_target": "baseline"}
        index_info = self.runtime.corpus.index_info() if hasattr(self.runtime, "corpus") and hasattr(self.runtime.corpus, "index_info") else {}
        if not isinstance(index_info, dict):
            index_info = {}
        if index_info.get('knowledge_identity'):
            if snapshot.get('corpus_fingerprint') != index_info['knowledge_identity']:
                raise ValueError('Golden Snapshot does not belong to active Knowledge Pipeline')
            config['knowledge_identity'] = index_info['knowledge_identity']
            config['candidate_k'] = index_info['knowledge_config']['candidate_k']
            config['top_k'] = index_info['knowledge_config']['top_k']
        judge_meta = {"model": self.runtime.model, **VERSIONS, "temperature":0, "baseline_version": production.get("id"), "execution_snapshot": {"embedding_model": index_info.get("embedding_model"), "vector_index": index_info.get("vector_index"), "generation_model": self.runtime.model, "temperature": 0.2}}
        from .paid_run import current_paid_run
        source=self.store.evaluation_run(resume_source_id) if resume_source_id else None
        limits=current_paid_run().output_limits if current_paid_run() else (source or {}).get('judge',{}).get('execution_snapshot',{}).get('request_limits')
        if limits:
            judge_meta['execution_snapshot']['request_limits'] = {key:limits[key] for key in ('answer','judge','query')}
        from .evaluation_contract import BUSINESS_JUDGE_PROMPT
        from .ai_service import GENERATION_BOUNDARY, GENERATION_PROMPT_VERSION
        import hashlib
        judge_meta.update(judge_prompt_sha256=hashlib.sha256(BUSINESS_JUDGE_PROMPT.encode()).hexdigest(),generation_prompt_version=GENERATION_PROMPT_VERSION,generation_boundary_sha256=hashlib.sha256(GENERATION_BOUNDARY.encode()).hexdigest())
        judge_meta["evaluation_identity"] = evaluation_identity(snapshot, judge_meta)
        return snapshot, approved, config, judge_meta

    def start_baseline(self, resume_source_id=None, *, automatic=False):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK:
            snapshot, approved, config, judge = self.baseline_inputs(resume_source_id)
            run_id = self.store.create_baseline_run(snapshot, config, judge, resume_source_id, automatic=automatic)
        return run_id, approved, config

    def _case_result(self, item: dict, config: dict):
        execution = self.runtime.answer(item["question"], config)
        return self.score_execution(item, execution)

    def score_execution(self, item, execution, *, judge_correction=None):
        expected = item["reference_answer"] or item["raw"].get("expected_behavior", "拒答或澄清")
        trace = execution.get('retrieval_trace') or {}
        final = trace.get('final', [])
        observation = observe_evidence(item, final)
        from .ai_service import generation_context
        judge = self.runtime.judge(item["question"], expected, execution["answer"], item["test_category"], context={**({'judge_correction':judge_correction} if judge_correction else {}), 'contract_version':VERSIONS['scoring_policy'], 'retrieval_candidates':trace.get('candidates',[]), 'baseline_findings':item.get('baseline_findings'), 'sources_legend':json.loads(generation_context(final).split('\n',1)[0])['sources'], 'golden_evidence': item['evidence'], 'final_context': final, 'category': item['test_category'], 'negative_subtype': item.get('negative_subtype'), 'expected_behavior': item['raw'].get('expected_behavior'), 'source_constraints': observation['source_constraints'], 'programmatic_evidence_observation': observation})
        if 'verdict' in judge:
            return self._score_business(item, execution, judge, expected)
        sufficiency = resolve_evidence(item, observation, judge, final)
        if item['test_category'] != 'negative' and not isinstance(trace.get('final'), list):
            sufficiency.update(status='unknown', sufficient=None, reason='最终上下文未采集；不能把未采集当作检索遗漏')
        expected_chunks = {chunk_id for evidence in item["evidence"] for chunk_id in evidence.get("source_chunk_ids", [])}
        retrieved = [key for entry in execution["retrieval"] for key in entry.get("matched_child_ids", [entry.get("chunk_id")])]
        matching = [index + 1 for index, chunk_id in enumerate(retrieved) if chunk_id in expected_chunks]
        from .retrieval import evidence_coverage
        trace = execution.get('retrieval_trace') or {}
        coverage = evidence_coverage({**trace, 'final': trace.get('final', execution['retrieval'])}, expected_chunks)
        hit = bool(matching) if expected_chunks else None
        precision = len(matching) / len(retrieved) * 100 if expected_chunks and retrieved else None
        claims = assess_claims(execution["answer"], judge, final, item=item)
        unsafe_operations=[r for r in claims['confirmed'] if item['test_category']=='negative' and r.get('kind')=='unsupported_instruction' and r.get('changes_operation') is True]
        effective_behavior=judge['behavior_pass'] and not unsafe_operations
        behavior_contract={'raw_judge_pass':judge['behavior_pass'],'effective_pass':bool(effective_behavior),'conflict':bool(judge['behavior_pass'] and unsafe_operations),'violations':unsafe_operations}
        redline = (not effective_behavior) or bool(claims["confirmed"] or claims["pending"])
        score = round((judge["correctness"] * 25 + judge["completeness"] * 100 + judge["faithfulness"] * 100) / 3, 2)
        failure_tags = []
        targets = {"positive": {"correctness": .8, "faithfulness": .8, "completeness": .75}, "ablation": {"correctness": .7, "faithfulness": .75, "completeness": .65}}.get(item["test_category"], {})
        if item["test_category"] != "negative":
            if judge["correctness"] / 4 < targets["correctness"] or judge["completeness"] < targets["completeness"]:
                failure_tags.append("Generation Failure")
            if judge["faithfulness"] < targets["faithfulness"]:
                failure_tags.append("Evidence / Citation Failure")
            if sufficiency['sufficient'] is False:
                failure_tags.append('Retrieval Failure' if not final and 'final' in trace and trace.get('candidates') == [] else 'Evidence / Citation Failure')
                if coverage.get('candidate_recall',{}).get('all_hit') is True and coverage.get('final_context',{}).get('all_hit') is False:failure_tags.append('Ranking Failure')
            elif sufficiency['sufficient'] is None:
                failure_tags.append('Evidence Pending Review')
        if not effective_behavior:
            failure_tags.extend(["Unsafe Answer", "Safety Failure"] if item["test_category"]=="negative" else ["Generation Failure"])
        if claims["confirmed"]:
            failure_tags.extend(["Hallucination", "Evidence / Citation Failure"])
        if claims["pending"]:
            failure_tags.append("Evidence Pending Review")
        if execution["latency_ms"] > 60000:
            failure_tags.append("Performance Failure")
        failure_tags = list(dict.fromkeys(failure_tags))
        severity = "critical" if item["raw"].get("criticality") == "high" or item.get("negative_subtype") == "safety_critical" else "ordinary"
        from .diagnostics import automatic_analysis
        analysis=automatic_analysis({'test_category':item['test_category'],'negative_subtype':item.get('negative_subtype'),
            'model_answer':execution['answer'],'judge_result':judge,'failure_tags':failure_tags,'passed':not failure_tags,
            'programmatic_metrics':{'evidence_sufficiency':sufficiency,'claim_assessment':claims,
                'behavior_contract':behavior_contract,'evidence_coverage':coverage,'retrieval_trace':trace,
                'latency_ms':execution['latency_ms']}})
        primary, secondary = analysis['primary_root_cause'] if failure_tags else 'None', []
        diagnostic={'reason':analysis['analysis_reason'],
            'analysis_category':analysis['analysis_category'],'findings':analysis['evidence_checks'],
            'retrieval_failure_stage':analysis['retrieval_failure_stage'],'pending_findings':claims['pending']}
        audit_gap=bool(claims['pending'] or sufficiency.get('unresolved_conflicts'))
        if audit_gap:
            diagnostic.update(governance_category='Evaluation / Data Quality',
                disputes=([{'type':issue,'claim':r.get('claim')} for r in claims['pending'] for issue in r.get('verification_issues',[])]
                          + [{'type':'source_conflict','conflict':c} for c in sufficiency.get('unresolved_conflicts',[])]))
        located_failure=analysis['analysis_category']=='rag_failure'
        confirmed_tags=[]
        if claims['confirmed']:confirmed_tags.extend(['Hallucination','Evidence / Citation Failure'])
        if not effective_behavior and located_failure and primary=='Safety':confirmed_tags.extend(['Unsafe Answer','Safety Failure'])
        if 'Performance Failure' in failure_tags:confirmed_tags.append('Performance Failure')
        if primary in {'Retrieval','Generation'} and located_failure:confirmed_tags.extend(tag for tag in failure_tags if tag in ('Retrieval Failure','Ranking Failure','Evidence / Citation Failure','Generation Failure'))
        outcome={'status':'pass' if not failure_tags else 'confirmed_failure' if located_failure and confirmed_tags else 'disputed' if audit_gap else 'pending_review',
                 'qualification_blocking':bool(failure_tags), 'confirmed_failure_tags':confirmed_tags if located_failure else [],
                 'pending_findings':claims['pending'], 'unresolved_conflicts':sufficiency.get('unresolved_conflicts',[]),
                 'confirmation_basis':'saved_structural_findings_not_independent_semantic_proof'}
        basis = 'verified_answer_claim' if primary == 'Generation' and located_failure else 'measured_latency' if primary == 'Performance' else 'explicit_safety_failure' if primary == 'Safety' else analysis['retrieval_failure_stage'] if primary == 'Retrieval' else 'unresolved_evaluation_evidence' if primary == 'Unknown' else coverage['diagnostic_basis']
        return {"question": item["question"], "reference_answer": expected, "test_category": item["test_category"], "negative_subtype": item.get("negative_subtype"), "severity": severity, "retrieved_chunks": execution["retrieval"], "model_answer": execution["answer"], "diagnosis": diagnostic, "evaluation_outcome":outcome, "programmatic_metrics": {"behavior_contract":behavior_contract, "evidence_sufficiency": sufficiency, "claim_assessment": claims, "retrieval_trace": trace or None, "evidence_coverage": coverage, "cost_estimation": execution.get("cost_estimation"), "judge_cost_estimation": judge.get("cost_estimation"), "retrieval_hit": hit, "retrieval_precision": precision, "retrieval_rank": matching[0] if matching else None, "latency_ms": execution["latency_ms"], "ttft_ms": execution.get("ttft_ms"), "input_tokens": execution.get("input_tokens"), "output_tokens": execution.get("output_tokens"), "provider_cost": execution.get("provider_cost"), "stages": execution.get("stages"), "token_usage": execution.get("token_usage"), "estimated_cost": execution.get("estimated_cost"), "judge_stages": judge.get("stages"), "judge_usage": judge.get("token_usage"), "judge_cost": judge.get("estimated_cost")}, "judge_result": judge, "overall_score": score, "failure_tags": failure_tags, "primary_root_cause": primary, "secondary_root_causes": secondary, "root_cause": {"primary": primary, "secondary": secondary, "evidence_match": hit, "diagnostic_basis": basis}, "passed": not failure_tags, "redline_pass": not redline}

    def _score_business(self, item, execution, judge, expected):
        from .providers import ProviderInvalidResponse
        from .diagnostics import automatic_analysis
        from .retrieval import evidence_coverage
        trace = execution.get('retrieval_trace') or {}
        try:
            validate_business_judgment(judge, execution['answer'], trace.get('final'), category=item['test_category'], constraints=item.get('raw'), question=item['question'], reference=expected, candidates=trace.get('candidates'))
            quality = judge['quality']
            if not isinstance(quality,dict):raise ValueError('quality metrics must be an object')
            if (type(quality.get('correctness')) is not int or not 0 <= quality['correctness'] <= 4
                or any(type(quality.get(k)) not in (int,float) or not math.isfinite(quality[k]) or not 0 <= quality[k] <= 1 for k in ('faithfulness','completeness'))):
                raise ValueError('quality metrics required by unchanged Hard Gates are invalid')
        except (ValueError, KeyError, TypeError) as error:
            raise ProviderInvalidResponse(str(error),raw_provider_response=judge.get('raw_provider_response')) from error
        guard=check_safety(item['question'],execution['answer'],trace.get('final'),constraints=item.get('raw'))
        decision=adjudicate(judge,guard)
        passed = decision['verdict'] == 'PASS'
        severity = 'critical' if any(i['critical'] for i in judge['issues']) or item.get('negative_subtype') == 'safety_critical' or item.get('raw',{}).get('criticality') == 'high' else 'ordinary'
        required={c for e in item.get('evidence',[]) for c in e.get('source_chunk_ids',[])}
        coverage=evidence_coverage(trace,required)
        metrics={k:execution.get(k) for k in ('latency_ms','ttft_ms','input_tokens','output_tokens','provider_cost','stages','token_usage','estimated_cost','cost_estimation')}
        retrieved=[c for e in execution.get('retrieval',[]) for c in e.get('matched_child_ids',[e.get('chunk_id')])]
        matching=[i+1 for i,c in enumerate(retrieved) if c in required]
        roles=business_check_roles(judge,question=item['question'],reference=expected)
        metrics['judge_check_roles']=roles
        metrics['judge_support_locations']=[{'section':section,'index':index,'support':q,'stage':'final' if quote_present(q,trace.get('final'),display=True) else 'candidate_requirement_evidence'} for section in ('checks','issues') for index,finding in enumerate(judge[section]) for q in finding['support']]
        sufficient=None if item['test_category']=='negative' else all(check['support'] for check,role in zip(judge['checks'],roles) if role['role']=='required')
        metrics.update(retrieval_hit=bool(matching) if required else None,retrieval_precision=len(matching)/len(retrieved)*100 if required and retrieved else None,retrieval_rank=matching[0] if matching else None,retrieval_trace=trace,evidence_coverage=coverage,
            behavior_contract={'effective_pass':passed,'raw_judge_pass':judge['verdict']=='PASS','violations':judge['issues']},
            evidence_sufficiency={'status':'not_applicable' if sufficient is None else 'sufficient' if sufficient else 'insufficient','sufficient':sufficient,'source_constraints':{k:item.get('raw',{}).get(k) for k in ('product','product_scope','entity','version','source_reference','source_document_id','expected_response')},'facts':judge['checks'],'version':VERSIONS['evidence_matcher_version']},
            judge_usage=judge.get('token_usage'),judge_stages=judge.get('stages'),judge_cost=judge.get('estimated_cost'),judge_cost_estimation=judge.get('cost_estimation'))
        metrics['safety_guard']=guard
        outcome={'contract_version':VERSIONS['scoring_policy'],'execution_complete':True,**decision}
        case={'question':item['question'],'reference_answer':expected,'test_category':item['test_category'],'negative_subtype':item.get('negative_subtype'),'severity':severity,
            'model_answer':execution['answer'],'retrieved_chunks':execution.get('retrieval',[]),'programmatic_metrics':metrics,'judge_result':{**judge,**quality,'behavior_pass':judge['verdict']=='PASS'},
            'evaluation_outcome':outcome,'passed':passed,'redline_pass':passed,
            'overall_score':round((quality['correctness']*25+quality['completeness']*100+quality['faithfulness']*100)/3,2),
            'failure_tags':[] if passed else ['Business Failure']}
        analysis=automatic_analysis(case)
        case.update(primary_root_cause=analysis['primary_root_cause'],secondary_root_causes=[],
            diagnosis={'reason':analysis['analysis_reason'],'analysis_category':analysis['analysis_category'],'findings':analysis['evidence_checks'],'retrieval_failure_stage':analysis['retrieval_failure_stage']},
            root_cause={'primary':analysis['primary_root_cause'],'secondary':[],'diagnostic_basis':analysis['retrieval_failure_stage'] or analysis['analysis_reason']})
        return case

    def start_replay(self, source_id):
        source = self.store.evaluation_run(source_id)
        if not source or source['status'] != 'completed':
            raise ValueError('仅完整历史运行支持答案回放')
        snapshot = json.loads(source['dataset_snapshot_json'])
        saved = {r['question_id']: r for r in self.store.evaluation_case_results(source_id)}
        if set(saved) != set(snapshot['question_ids']):
            raise ValueError('历史逐题记录不完整')
        executions = {}
        for key, case in saved.items():
            trace = case.get('programmatic_metrics', {}).get('retrieval_trace')
            if not isinstance(trace, dict) or not isinstance(trace.get('final'), list) or any(not isinstance(e.get('content'), str) for e in trace['final']):
                raise ValueError('历史最终上下文未完整保存，不能回放评分')
            executions[key] = {**case['programmatic_metrics'], 'answer': case['model_answer'], 'retrieval': case.get('retrieved_chunks', []), 'retrieval_trace': trace}
        judge = {**source['judge'], **VERSIONS, 'model': self.runtime.model, 'source_evaluation_id': source_id, 'execution_kind': 'answer_replay'}
        judge['evaluation_identity'] = evaluation_identity(snapshot, judge)
        items = self.snapshot_items(snapshot)
        run_id = self.store.create_evaluation_run(snapshot, {**source['config'], 'run_target': 'answer_replay', 'source_evaluation_id': source_id}, judge)
        return run_id, items, executions

    def execute_replay(self, run_id, items, executions):
        cases = []
        try:
            for item in items:
                case = self.score_execution(item, executions[item['id']])
                self.store.record_evaluation_case(run_id, item['id'], case)
                cases.append(case)
            result = {**summarize_evaluation_cases(cases), 'execution_kind': 'answer_replay', 'release_eligible': False, 'timing_provenance': '历史生成耗时，非本次生成性能'}
            return self.store.finish_evaluation_run(run_id, 'completed', result)
        except Exception as error:
            return self.store.finish_evaluation_run(run_id, 'partial' if cases else 'failed', {**summarize_evaluation_cases(cases,complete=False), 'evaluation_complete':False, 'execution_kind': 'answer_replay', 'release_eligible': False}, str(error))

    def execute_baseline(self, run_id, approved, config):
        from .paid_run import execution_limits,accounting_only
        run=self.store.evaluation_run(run_id)
        if run['status']=='completed':return run
        if run['result'].get('auto_recovery',{}).get('authorized') and not self.store.claim_evaluation_worker(run_id):return self.store.evaluation_run(run_id)
        limits=run['judge'].get('execution_snapshot',{}).get('request_limits')
        with execution_limits(limits),accounting_only():return self._execute_baseline(run_id,approved,config)

    def _execute_baseline(self, run_id, approved, config):
        cases, checkpoints, phase, item = [], {}, 'initialization', None
        run = self.store.evaluation_run(run_id)
        frozen_ids = set(json.loads(run['dataset_snapshot_json'])['question_ids'])
        cases = self.store.evaluation_case_results(run_id)
        checkpoints = run['result'].get('checkpoints', {})
        lineage = {k:run['result'][k] for k in ('resume_source_id','execution_owner_pid','auto_recovery') if k in run['result']}
        def progress(*, complete=False):
            from .telemetry import cost_fields
            events=[u for cp in checkpoints.values() for attempt in cp.get('attempts',[]) for u in attempt.get('usage',[])]
            accounting={'provenance':'logical_task_including_resume_history','call_events':len(events),
                'unknown_usage_events':sum(type(u.get('prompt_tokens',u.get('total_tokens'))) is not int or u.get('provider')!='Alibaba' and type(u.get('completion_tokens')) is not int for u in events),
                'known_input_tokens':sum(u.get('prompt_tokens',u.get('total_tokens',0)) for u in events if type(u.get('prompt_tokens',u.get('total_tokens'))) is int),
                'known_output_tokens':sum(u['completion_tokens'] for u in events if type(u.get('completion_tokens')) is int),
                **cost_fields(self.runtime.model,events)}
            summary=summarize_evaluation_cases(cases,complete=complete)
            errors=[{'question_id':q, **cp['technical_error']} for q,cp in checkpoints.items() if cp.get('technical_error')]
            return {**summary, 'technical_errors':errors, 'technical_error_count':len(errors), 'attempted':len(cases)+len(errors), **lineage, 'total':len(frozen_ids), 'evaluation_complete':False, 'checkpoints':checkpoints,'request_accounting':accounting, 'runtime_limits':{'provider_request_seconds':getattr(getattr(getattr(self.runtime,'provider',None),'settings',None),'timeout_seconds',None), 'question_total_seconds':None, 'round_total_seconds':None, 'stage_total_seconds':600, 'stage_max_attempts':3}}
        try:
            if not policy_current(run['judge']) or run['judge'].get('evaluation_identity')!=evaluation_identity(json.loads(run['dataset_snapshot_json']),run['judge']):
                raise ValueError('Evaluation Identity或加载的合同版本不一致，禁止继续Provider调用')
            if {i['id'] for i in approved} != frozen_ids or len(approved) != len(frozen_ids):
                raise ValueError('未提交完整冻结题集，不能标为Completed')
            if not isinstance(checkpoints, dict) or not set(checkpoints) <= frozen_ids:
                raise ValueError('检查点不属于冻结Snapshot')
            saved = {c['question_id'] for c in cases}
            expected = {i['id'] for i in approved}
            if not saved <= expected or len(saved) != len(cases):
                raise ValueError('Saved evaluation cases do not match frozen snapshot')
            automatic=lineage.get('auto_recovery',{}).get('authorized') is True
            def check_stop():
                if self.store.evaluation_run(run_id)['result'].get('stop_request'):
                    raise InterruptedError('用户停止运行，断点已保存')
            def perform(phase,action):
                from .providers import ProviderAPIError,ProviderInvalidResponse,ProviderTimeout,retryable_error,stage_deadline
                # Explicit Resume starts a new retry window; process recovery of this Run keeps its failures.
                prior=[a for a in checkpoint['attempts'] if a.get('phase')==phase and a.get('recorded_by_run_id')==run_id]
                failures=0;invalid_failures=0
                for a in reversed(prior):
                    if a.get('status')=='ok':break
                    failures+=1;invalid_failures+=a.get('error_type')=='ProviderInvalidResponse'
                windows=checkpoint.setdefault('phase_windows',{})
                window=windows.get(phase)
                if not window or window.get('run_id')!=run_id:
                    window={'run_id':run_id,'started_at':time.time()};windows[phase]=window
                deadline=time.monotonic()+max(0,600-(time.time()-window['started_at']))
                if checkpoint.get('inflight')==phase:checkpoint.setdefault('unknown_execution',{})[phase]=True
                if checkpoint.get('unknown_execution',{}).get(phase):
                    raise RuntimeError('Unknown request execution after worker loss; explicit request/usage reconciliation required')
                while True:
                    check_stop()
                    if failures>=3 or invalid_failures>=2 or time.monotonic()>=deadline:
                        last=checkpoint['attempts'][-1] if checkpoint['attempts'] else {}
                        if (last.get('phase')==phase and last.get('recorded_by_run_id')==run_id
                                and last.get('status')=='error' and last.get('retryable') is True
                                and last.get('request_execution_unknown') is False):
                            last['retryable']=False
                            raise ProviderTimeout('Known Provider stage exhausted 3 attempts or 600 seconds')
                        raise RuntimeError('Provider stage exhausted 3 attempts or 600 seconds')
                    checkpoint['inflight']=phase
                    if automatic:lineage['auto_recovery'].update(state='running',question_id=item['id'],phase=phase)
                    self.store.update_evaluation_progress(run_id,progress())
                    started=time.perf_counter();usage=[]
                    try:
                        with collect_usage() as usage,stage_deadline(deadline):value=action()
                        if time.monotonic()>deadline:
                            checkpoint['execution' if phase=='generation' else 'scored_result']=value
                            raise ProviderTimeout('Known complete Provider response exceeded 600 seconds')
                    except Exception as error:
                        failures+=1
                        attempt={'phase':phase,'status':'error','error_type':type(error).__name__,'error':str(error),
                                 'cause_type':type(error.__cause__).__name__ if error.__cause__ else None,
                                 'cause_message':str(error.__cause__) if error.__cause__ else None,'usage':usage,
                                 'elapsed_ms':round((time.perf_counter()-started)*1000),
                                 'raw_provider_response':getattr(error,'raw_provider_response',None),
                                 'response_metadata':getattr(error,'response_metadata',None),'provider_status_code':getattr(error,'status_code',None),'recorded_by_run_id':run_id}
                        unknown=any(u.get('status')=='unknown' or u.get('provider') in {'DeepSeek','Alibaba'} and type(u.get('prompt_tokens',u.get('total_tokens'))) is not int for u in usage)
                        retry=retryable_error(error) and not unknown and failures<3 and time.monotonic()<deadline
                        # Repeated structurally invalid Judge replies are a terminal contract failure.
                        if isinstance(error,ProviderInvalidResponse):
                            invalid_failures+=1
                            if invalid_failures>=2:retry=False
                        attempt['request_execution_unknown']=unknown
                        if unknown:checkpoint.setdefault('unknown_execution',{})[phase]=True
                        attempt['retryable']=retry;checkpoint['attempts'].append(attempt);checkpoint.pop('inflight',None)
                        if automatic and retry:
                            delay=min(60,2**min(failures-1,6))
                            if isinstance(error,ProviderAPIError):
                                try:delay=max(delay,float(error.retry_after or 0))
                                except (TypeError,ValueError):
                                    try:
                                        from email.utils import parsedate_to_datetime
                                        delay=max(delay,parsedate_to_datetime(error.retry_after).timestamp()-time.time())
                                    except (TypeError,ValueError,OverflowError):pass
                            if not isinstance(delay,(int,float)) or not math.isfinite(delay):delay=60
                            delay=min(delay,max(0,deadline-time.monotonic()))
                            attempt['retry_delay_seconds']=delay
                            lineage['auto_recovery'].update(state='retrying',question_id=item['id'],phase=phase,error=str(error),retry_count=failures)
                            self.store.update_evaluation_progress(run_id,progress())
                            for _ in range(math.ceil(delay)):
                                check_stop();time.sleep(min(1,delay));delay-=min(1,delay)
                            continue
                        raise
                    checkpoint['attempts'].append({'phase':phase,'status':'ok','recorded_by_run_id':run_id,'usage':usage,'elapsed_ms':round((time.perf_counter()-started)*1000)})
                    checkpoint.pop('inflight',None);return value
            consecutive_errors=0
            for item in approved:
                check_stop()
                if item['id'] in saved:
                    if item['id'] in checkpoints:
                        for key in ('execution','scored_result','inflight','technical_error'):checkpoints[item['id']].pop(key,None)
                    continue
                checkpoint=checkpoints.setdefault(item['id'],{'attempts':[]})
                if 'execution' in checkpoint and (not isinstance(checkpoint['execution'].get('answer'),str) or not isinstance(checkpoint['execution'].get('retrieval_trace',{}).get('final'),list)):
                    raise ValueError('生成检查点缺少完整答案/最终上下文')
                try:
                    phase='generation'
                    if 'execution' not in checkpoint:
                        checkpoint['execution']=perform(phase,lambda:self.runtime.answer(item['question'],config))
                        self.store.update_evaluation_progress(run_id,progress())
                    phase='judge'
                    if 'scored_result' not in checkpoint:
                        def score():
                            previous=next((a for a in reversed(checkpoint['attempts']) if a.get('phase')=='judge' and a.get('recorded_by_run_id')==run_id and a.get('error_type')=='ProviderInvalidResponse'),None)
                            correction={'error':previous['error'], 'previous_response':previous.get('raw_provider_response')} if previous else None
                            return self.score_execution(item,checkpoint['execution'],judge_correction=correction)
                        checkpoint['scored_result']=perform(phase,score)
                        self.store.update_evaluation_progress(run_id,progress())
                except Exception as error:
                    from .providers import retryable_error
                    last=checkpoint['attempts'][-1] if checkpoint['attempts'] else {}
                    # Only known, exhausted recoverable requests are isolated; auth/config/Unknown/Stop halt.
                    if not (automatic and retryable_error(error) and last.get('status')=='error'
                            and last.get('recorded_by_run_id')==run_id and last.get('retryable') is False
                            and last.get('request_execution_unknown') is False):
                        raise
                    checkpoint['technical_error']={'phase':phase, 'error_type':type(error).__name__, 'error':str(error)}
                    consecutive_errors+=1
                    self.store.update_evaluation_progress(run_id,progress())
                    # ponytail: two adjacent exhausted cases are a circuit breaker; no extra diagnostic calls.
                    if consecutive_errors>=2:
                        raise RuntimeError('连续两题受控重试耗尽；疑似系统性配置或合同失效，已停止Provider调用') from error
                    continue
                result=checkpoint['scored_result']
                self.store.record_evaluation_case(run_id,item['id'],result,with_bad_case=True)
                cases.append({'question_id':item['id'],**result});saved.add(item['id'])
                consecutive_errors=0
                checkpoint.pop('technical_error',None)
                checkpoint.pop('execution',None);checkpoint.pop('scored_result',None);checkpoint.pop('inflight',None)
                self.store.update_evaluation_progress(run_id,progress())
            check_stop()
            errors=progress()['technical_errors']
            if errors:
                message=f"{len(errors)}题技术异常；已完成{len(cases)}/{len(frozen_ids)}，检查点已保存，须恢复后才能形成完整成绩"
                if automatic:lineage['auto_recovery'].update(state='stopped',error=message)
                return self.store.finish_evaluation_run(run_id,'partial',progress(),message)
            if automatic:lineage['auto_recovery']['state']='completed'
            return self.store.finish_evaluation_run(run_id, 'completed', {**progress(complete=True), 'evaluation_complete':True})
        except Exception as error:
            if item is not None:
                checkpoint = checkpoints.setdefault(item['id'], {'attempts':[]})
                checkpoint.pop('inflight', None)
                if not isinstance(error,InterruptedError):checkpoint.setdefault('technical_error',{'phase':phase,'error_type':type(error).__name__,'error':str(error)})
                if not checkpoint['attempts'] or checkpoint['attempts'][-1].get('status')!='error':checkpoint['attempts'].append({'phase':phase, 'status':'error', 'error_type':type(error).__name__, 'cause_type':type(error.__cause__).__name__ if error.__cause__ else None, 'error':str(error), 'usage':locals().get('usage', []), 'elapsed_ms':round((time.perf_counter()-started)*1000) if 'started' in locals() else None})
                checkpoint['attempts'][-1]['cause_message'] = str(error.__cause__) if error.__cause__ else None
                if isinstance(getattr(error, 'raw_provider_response', None), str):
                    checkpoint['attempts'][-1]['raw_provider_response'] = error.raw_provider_response
            if lineage.get('auto_recovery'):lineage['auto_recovery'].update(state='stopped',error=str(error))
            return self.store.finish_evaluation_run(run_id, 'partial' if cases or any('execution' in c for c in checkpoints.values()) else 'failed', progress(), str(error))

    def recover_run(self,run_id):
        from .paid_run import PaidRun,controlled_run,accounting_only
        run=self.store.evaluation_run(run_id)
        auto=run['result'].get('auto_recovery',{})
        if not auto.get('authorized') or auto.get('state')=='stopped' or run['result'].get('stop_request'):return
        snapshot=json.loads(run['dataset_snapshot_json'])
        if run['judge'].get('evaluation_identity')!=evaluation_identity(snapshot,run['judge']) or not policy_current(run['judge']):raise ValueError('自动恢复Evaluation Identity不匹配')
        if run['config'].get('candidate_id'):
            items,config,candidate,baseline=self.candidate_inputs(run['config']['candidate_id'])
            if config!=run['config'] or baseline['judge']!=run['judge']:raise ValueError('自动恢复Candidate身份不匹配')
            execute=lambda:self.execute_candidate(run_id,items,config,candidate,baseline)
        else:
            current,items,config,judge=self.baseline_inputs(run_id)
            if current!=snapshot or config!=run['config'] or judge!=run['judge']:raise ValueError('自动恢复冻结配置不匹配')
            execute=lambda:self.execute_baseline(run_id,items,config)
        if auto.get('ledger_path'):
            def check_ledger_identity():
                from .corpus import current_manifest,manifest_identity
                if self.store.dataset_snapshots()[0]['id']!=snapshot['id'] or snapshot.get('corpus_fingerprint')!=manifest_identity(current_manifest()):raise ValueError('恢复期间Golden/Corpus身份变化')
                return auto.get('ledger_identity')
            ledger=PaidRun.load_accounting(auto['ledger_path'],check_ledger_identity)
            if ledger.identity!=auto.get('ledger_identity'):raise ValueError('恢复费用账本绑定不同')
            with controlled_run(ledger),accounting_only():return execute()
        return execute()

    def candidate_inputs(self, candidate_id: str):
        candidate = self.store.candidate(candidate_id)
        if candidate is None:
            raise ValueError("Candidate 不存在")
        experiment = self.store.experiment(candidate["experiment_id"])
        baseline = self.store.evaluation_run(experiment["baseline_run_id"]) if experiment else None
        if baseline is None or baseline["status"] != "completed":
            raise ValueError("Candidate 必须基于已完成的 Baseline 运行")
        if not policy_current(baseline['judge']):
            raise ValueError('评测规则已升级，请授权建立新Baseline；旧Candidate只读')
        from .policy import validate_candidate_config
        if not validate_candidate_config(candidate["config"])["valid"]:
            raise ValueError("Candidate 参数超出 Search Space")
        snapshot = json.loads(baseline["dataset_snapshot_json"])
        from .paid_run import current_paid_run
        limits = baseline['judge'].get('execution_snapshot',{}).get('request_limits')
        if limits is not None:
            paid_run=current_paid_run()
            if paid_run is not None and (paid_run.output_limits is None or limits!={key:paid_run.output_limits.get(key) for key in ('answer','judge','query')}):
                raise ValueError('Candidate request limits must match frozen Baseline')
        if baseline['judge'].get('evaluation_identity') != evaluation_identity(snapshot, baseline['judge']):
            raise ValueError('Evaluation身份不匹配')
        self.store.require_current_baseline(baseline["id"])
        approved = self.snapshot_items(snapshot)
        baseline_cases={c['question_id']:c for c in self.store.evaluation_case_results(baseline['id'])}
        approved=[{**item,'baseline_findings':baseline_cases.get(item['id'],{}).get('judge_result',{}).get('issues',[])} for item in approved]
        if baseline['judge'].get('model') != self.runtime.model:
            raise ValueError('Sandbox 必须使用 Baseline 冻结的 Judge Model')
        config = {**candidate["config"], **({"knowledge_identity": baseline["config"]["knowledge_identity"]} if baseline["config"].get("knowledge_identity") else {}), "run_target": "sandbox_candidate", "candidate_id": candidate_id}
        return approved, config, candidate, baseline

    def start_candidate(self, candidate_id: str, *, automatic=False):
        approved, config, candidate, baseline = self.candidate_inputs(candidate_id)
        snapshot = json.loads(baseline["dataset_snapshot_json"])
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK:
            run_id = self.store.create_baseline_run(snapshot, config, baseline['judge'], candidate_id=candidate_id, automatic=automatic)
            candidate = self.store.candidate(candidate_id)
        return run_id, approved, config, candidate, baseline

    def execute_candidate(self, run_id, approved, config, candidate, baseline):
        run = self.execute_baseline(run_id, approved, config)
        if run['status'] in {'queued','running'}:return self.store.candidate(candidate['id'])
        baseline_cases = {item["question_id"]: item for item in self.store.evaluation_case_results(baseline["id"])}
        candidate_cases = {item["question_id"]: item for item in self.store.evaluation_case_results(run_id)}
        failed = [question_id for question_id, item in baseline_cases.items() if not item.get("passed")]
        passed = [(question_id, item) for question_id, item in baseline_cases.items() if item.get("passed")]
        regression = evaluate_regression(new_critical_failures=sum(not candidate_cases.get(question_id, {}).get("passed", False) and item.get("severity") == "critical" for question_id, item in passed), new_ordinary_failures=sum(not candidate_cases.get(question_id, {}).get("passed", False) and item.get("severity") != "critical" for question_id, item in passed))
        references = set(candidate['reasoning'].get('observed_evidence', []))
        targets = [q for q in failed if q in references or f"BC-{baseline['id']}-{q}" in references]
        comparison = compare_cases(baseline_cases, candidate_cases, targets)
        regression.update({key:comparison[key] for key in ('formal_blocking_question_ids','confirmed_regression_question_ids','pending_regression_question_ids','disputed_regression_question_ids','unclassified_regression_question_ids','regression_interpretation')})
        if comparison.get('comparison_version') == VERSIONS['scoring_policy']:
            critical_ids={q for q in comparison['new_regression_question_ids'] if candidate_cases[q].get('severity')=='critical' or any(i.get('critical') is True for i in candidate_cases[q].get('judge_result',{}).get('issues',[]))}
            regression=evaluate_regression(new_critical_failures=len(critical_ids),new_ordinary_failures=len(comparison['new_regression_question_ids'])-len(critical_ids))
            regression.update(comparison)
            regression['passed']=regression['passed'] and comparison.get('safety_verification_complete',True) and comparison['comparison_complete'] and not comparison['continued_failure_new_critical_question_ids']
            regression['status']='NOT_EVALUABLE' if not comparison.get('safety_verification_complete',True) else 'PASS' if regression['passed'] else 'FAIL' if comparison['comparison_complete'] else 'NOT_EVALUABLE'
        qualification = qualify_candidate(run["result"]["gates"], regression, comparison['target_bad_cases_fixed'], len(failed), run["result"]["bad_case_count"])
        if not comparison.get('safety_verification_complete',True):
            qualification['blocking_reason']='关键安全规则无法可靠核验；不伪造业务FAIL，不按新增退化数量超限解释'
        if run['status'] != 'completed':
            qualification = {**qualification, 'qualified': False}
        result = {"evaluation_run_id": run_id, "baseline_run_id": baseline["id"], "error": run.get("error_message"), **run["result"], "regression": regression, **comparison, "evaluation_identity": run["judge"].get("evaluation_identity"), "qualification": qualification, "recommendation": None}
        if candidate['reasoning'].get('candidate_label') == 'D':
            winner = self.store.candidate(candidate['reasoning']['winner_id'])
            winner_cases = {item['question_id']: item for item in self.store.evaluation_case_results(winner['result']['evaluation_run_id'])}
            newly_failed = [key for key, item in winner_cases.items() if item.get('passed') and not candidate_cases.get(key, {}).get('passed')]
            newly_fixed = [key for key, item in winner_cases.items() if not item.get('passed') and candidate_cases.get(key, {}).get('passed')]
            result['winner_comparison'] = {'winner_id': winner['id'], 'new_failures': newly_failed, 'fixed_cases': newly_fixed, 'promote': run['status'] == 'completed' and qualification['qualified'] and not newly_failed and bool(newly_fixed)}
        finished = self.store.finish_candidate(candidate["id"], "evaluated" if run['status'] == 'completed' else 'failed', result)
        recommendation = self.store.refresh_recommendation(candidate["experiment_id"])
        return {**finished, "recommendation": recommendation}

    def run_baseline(self, *, automatic=True):
        return self.execute_baseline(*self.start_baseline(automatic=automatic))

    def run_candidate(self, candidate_id: str, *, automatic=True):
        return self.execute_candidate(*self.start_candidate(candidate_id,automatic=automatic))
