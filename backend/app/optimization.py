"""Manually started, bounded A/B/C Optimization Agent for V1.3."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from collections import Counter

from .policy import DEFAULT_PIPELINE_CONFIG, EXCLUDED_AUTOMATIC_PARAMETERS, MAX_EVALS, search_space_contract, validate_candidate_config


class OptimizationAgent:
    def __init__(self, store, provider):
        self.store = store
        self.provider = provider

    def generate(self, baseline_run_id: str, trigger_id: str | None = None, experiment_id: str | None = None):
        # Check identity before budget reads; the short claim serializes duplicate starts.
        self.store.require_current_baseline(baseline_run_id)
        bad_cases = [item for item in self.store.bad_case_rows() if item["run_id"] == baseline_run_id]
        if not bad_cases:
            raise ValueError("该 Baseline 没有真实 Bad Case，无法生成 Candidate")
        baseline = self.store.evaluation_run(baseline_run_id)
        base_config = {**DEFAULT_PIPELINE_CONFIG, **baseline["config"]}
        base_config.pop("run_target", None)
        experiment_id, prior_candidates, round_number, completed = self.store.claim_agent_generation(baseline_run_id, trigger_id, experiment_id)
        prior = [item["config"] for item in prior_candidates]
        context = self.store.experiment(experiment_id)["result"]
        trigger_id = trigger_id or context.get("trigger_id")
        monitoring_context = {"trigger": self.store.optimization_trigger(trigger_id), "event": context.get("monitoring_event"), "confirmed_baseline_id": context.get("baseline_id"), "golden_id": context.get("golden_id"), "corpus_fingerprint": context.get("corpus_fingerprint")} if trigger_id else None
        labels = ['A', 'B', 'C'][:min(3, MAX_EVALS - 1 - completed)]
        audit = {"optimization_run_id": experiment_id, "baseline_id": baseline_run_id, "timestamp": datetime.now(timezone.utc).isoformat(), "provider_raw_text": None, "parsed_json": None, "parsed_candidates": None, "validation_stage": "provider", "failed_candidate_id": None, "failed_field": None, "actual_value": None, "expected_type": None, "allowed_values": None, "validation_issues": [], "root_cause_counts": dict(Counter(item.get("category") or "Unknown" for item in bad_cases)), "source_bad_case_ids": [item["id"] for item in bad_cases], "monitoring_context": monitoring_context}
        prompt = {
            "bad_cases": bad_cases,
            "monitoring_context": monitoring_context,
            "baseline_configuration": base_config,
            'prior_sandbox_results': [{'id': item['id'], 'hypothesis': item['reasoning'].get('hypothesis'), 'configuration': item['config'], 'result': item['result'], 'status': item['status']} for item in prior_candidates],
            "allowed_parameter_values": search_space_contract(),
            "excluded_automatic_parameters": sorted(EXCLUDED_AUTOMATIC_PARAMETERS),
            "rule": f"当前为 Round {round_number}。返回 {','.join(labels)} 并列、可解释 Candidate。One Candidate = One Hypothesis + Minimum Necessary Parameters。config_diff 只写相对 Baseline 的实际改动，且只允许 allowed_parameter_values 中的字段和值；禁止所有其他字段。hybrid_alpha 只在 hybrid_search=true 时有效；若关闭 Hybrid，不要在 config_diff 中提供 hybrid_alpha。根据 prior_sandbox_results 调整假设，不能重复已失败配置。",
        }
        try:
            content = self.provider.complete(
                "你是 RAG Optimization Agent。只返回 JSON：{\"root_cause_cluster\":\"...\",\"observed_evidence\":[\"...\"],\"candidates\":[{\"id\":\"A\",\"hypothesis\":\"...\",\"why\":\"...\",\"target_bad_cases\":[\"...\"],\"config_diff\":{},\"risk\":\"...\"}]}。A/B/C 均按此格式；严格遵守用户消息中的 allowed_parameter_values 类型和值，不得输出隐藏推理或测试答案。",
                json.dumps(prompt, ensure_ascii=False), json_mode=True,
            )
            audit["provider_raw_text"] = content
            audit["validation_stage"] = "json_parse"
            result = json.loads(content)
            audit["parsed_json"] = result
            audit["validation_stage"] = "schema"
            if not isinstance(result, dict) or not isinstance(result.get("candidates"), list):
                audit.update(failed_field="candidates", actual_value=result.get("candidates") if isinstance(result, dict) else result, expected_type="array", allowed_values=None)
                raise ValueError("Agent 输出必须包含 candidates 数组")
            candidates = result.get("candidates", [])
            audit["parsed_candidates"] = candidates
            if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in candidates) or sorted(item["id"] for item in candidates) != labels:
                raise ValueError(f"Agent 必须返回 {','.join(labels)} Candidates")
            staged = []
            for candidate in candidates:
                audit["validation_stage"] = "schema"
                audit["failed_candidate_id"] = candidate["id"]
                for field in ("hypothesis", "why", "risk", "target_bad_cases", "config_diff"):
                    value = candidate.get(field)
                    if field in ("hypothesis", "why", "risk"):
                        expected = "non-empty string"
                        valid = isinstance(value, str) and bool(value.strip())
                    elif field == "target_bad_cases":
                        expected = "array of non-empty strings"
                        valid = isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)
                    else:
                        expected = "object"
                        valid = isinstance(value, dict)
                    if not valid:
                        audit.update(failed_field=field, actual_value=value, expected_type=expected, allowed_values=None)
                        raise ValueError(f"Agent Candidate {candidate['id']} 缺少有效 {field}")
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
                prior.append(config)
                staged.append((candidate, config))
            audit["validation_stage"] = "completed"
            audit["failed_candidate_id"] = None
            batch = []
            for candidate, config in staged:
                batch.append((f"R{round_number}-{candidate['id']}", config, {
                    "root_cause_cluster": result.get("root_cause_cluster", "待人工复核"), "observed_evidence": candidate["target_bad_cases"], "hypothesis": candidate["hypothesis"], "proposal": candidate["why"], "risk": candidate["risk"],
                    "changed_parameters": {key: value for key, value in config.items() if value != base_config.get(key)}, "source_trigger_id": trigger_id, "round": round_number, "candidate_label": candidate["id"],
                }))
            audit["validation_stage"] = "persistence"
            self.store.save_agent_round(experiment_id, batch, {**result, **audit, "validation_stage": "completed", "round": round_number, "evaluation_budget": {"used": completed, "max": MAX_EVALS}})
            return self.store.experiment(experiment_id)
        except Exception as error:
            audit["validation_error"] = str(error)
            self.store.save_agent_trace(experiment_id, "failed", audit, str(error))
            raise ValueError(str(error)) from error
