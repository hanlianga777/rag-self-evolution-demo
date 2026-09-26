"""Manually started, bounded A/B/C Optimization Agent for V1.1."""

from __future__ import annotations

import json

from .policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS, validate_candidate_config
from .providers import ProviderUnavailable


class OptimizationAgent:
    def __init__(self, store, provider):
        self.store = store
        self.provider = provider

    def generate(self, baseline_run_id: str, trigger_id: str | None = None, experiment_id: str | None = None):
        if trigger_id and not self.store.trigger_is_confirmed(trigger_id):
            raise ValueError("Monitoring Trigger 必须经 Human Confirm 才能启动 Agent")
        bad_cases = [item for item in self.store.bad_case_rows() if item["run_id"] == baseline_run_id]
        if not bad_cases:
            raise ValueError("该 Baseline 没有真实 Bad Case，无法生成 Candidate")
        baseline = self.store.evaluation_run(baseline_run_id)
        base_config = {**DEFAULT_PIPELINE_CONFIG, **(baseline or {}).get("config", {})}
        existing_experiment = experiment_id or ((self.store.optimization_trigger(trigger_id) or {}).get("optimization_run_id") if trigger_id else None)
        prior = [item['config'] for item in self.store.candidates(existing_experiment)] if existing_experiment else []
        completed = self.store.experiment(existing_experiment)['evaluation_budget']['used'] if existing_experiment else 0
        if completed >= MAX_EVALS - 1:
            raise ValueError(f"evaluation budget exhausted: max_evals={MAX_EVALS}")
        prior_candidates = []
        if existing_experiment:
            existing = self.store.experiment(existing_experiment)
            if existing is None or existing["baseline_run_id"] != baseline_run_id:
                raise ValueError("Optimization Run 不属于该 Baseline")
            prior_candidates = self.store.candidates(existing_experiment)
            round_numbers = [item.get("reasoning", {}).get("round") for item in prior_candidates if isinstance(item.get("reasoning", {}).get("round"), int)]
            current_round = max(round_numbers) if round_numbers else 0
            current = [item for item in prior_candidates if item.get("reasoning", {}).get("round") == current_round]
            if existing['result'].get('report_confirmation'):
                raise ValueError('报告已确认，不能继续改变实验')
            if current_round == 0 or not current or any(item["status"] not in {'evaluated', 'failed'} for item in current):
                raise ValueError("上一轮 A/B/C 必须全部完成 Sandbox 后才能继续优化")
            if any(item["result"].get("qualification", {}).get("qualified") for item in current):
                raise ValueError("已有合格 Candidate，无需继续生成下一轮")
            round_number = current_round + 1
        else:
            round_number = 1
        experiment_id = existing_experiment or self.store.create_experiment(baseline_run_id)
        labels = ['A', 'B', 'C'][:min(3, MAX_EVALS - 1 - completed)]
        prompt = {
            "bad_cases": bad_cases,
            "baseline_configuration": base_config,
            'prior_sandbox_results': [{'id': item['id'], 'hypothesis': item['reasoning'].get('hypothesis'), 'configuration': item['config'], 'result': item['result'], 'status': item['status']} for item in prior_candidates],
            "allowed_parameter_values": "V1.1 frozen search space only; do not propose parser/OCR/chunk/model/temperature/query_decompose/retrieval_max_tokens/rerank_top_n",
            "rule": f"当前为 Round {round_number}。返回 {','.join(labels)} 并列、可解释 Candidate；config 只写相对 Baseline 的实际改动。根据 prior_sandbox_results 调整假设，不能重复已失败配置。每个 Candidate 必须有 root_cause_cluster、observed_evidence、hypothesis、proposal、risk。",
        }
        try:
            content = self.provider.complete(
                "你是 RAG Optimization Agent。只返回 JSON：{\"root_cause_cluster\":\"...\",\"observed_evidence\":[\"...\"],\"candidates\":[{\"id\":\"A\",\"config\":{},\"hypothesis\":\"...\",\"proposal\":\"...\",\"risk\":\"...\"}]}。不得输出隐藏推理或测试答案。",
                json.dumps(prompt, ensure_ascii=False), json_mode=True,
            )
            result = json.loads(content)
            candidates = result.get("candidates", [])
            if sorted(item.get("id") for item in candidates) != labels:
                raise ValueError(f"Agent 必须返回 {','.join(labels)} Candidates")
            for candidate in candidates:
                if not all(isinstance(candidate.get(field), str) and candidate[field].strip() for field in ("hypothesis", "proposal", "risk")):
                    raise ValueError("Agent Candidate 缺少可解释 Hypothesis / Proposal / Risk")
                if candidate["hypothesis"].strip() in {item.get("reasoning", {}).get("hypothesis", "").strip() for item in prior_candidates}:
                    raise ValueError("下一轮必须提出新的 Hypothesis")
                config = {**base_config, **candidate.get("config", {})}
                check = validate_candidate_config(config, prior_configs=prior, completed_evals=completed)
                if not check["valid"]:
                    raise ValueError("Agent Candidate Config 不符合冻结 Search Space：" + "; ".join(check["errors"]))
                prior.append(config)
                self.store.save_candidate(experiment_id, f"R{round_number}-{candidate['id']}", config, {
                    "root_cause_cluster": result.get("root_cause_cluster", "待人工复核"), "observed_evidence": result.get("observed_evidence", []), "hypothesis": candidate["hypothesis"], "proposal": candidate["proposal"], "risk": candidate["risk"],
                    "changed_parameters": {key: value for key, value in config.items() if value != base_config.get(key)}, "source_trigger_id": trigger_id, "round": round_number, "candidate_label": candidate["id"],
                })
            self.store.save_agent_trace(experiment_id, "completed", {**result, "round": round_number, "evaluation_budget": {"used": completed, "max": MAX_EVALS}})
            return self.store.experiment(experiment_id)
        except (ProviderUnavailable, ValueError, json.JSONDecodeError) as error:
            self.store.save_agent_trace(experiment_id, "failed", {}, str(error))
            raise ValueError(str(error)) from error
