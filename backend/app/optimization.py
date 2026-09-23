"""Manually started, bounded Optimization Agent for the frozen V1.0.1 search space."""

from __future__ import annotations

import json

from .policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS, validate_candidate_config
from .providers import ProviderUnavailable


class OptimizationAgent:
    def __init__(self, store, provider):
        self.store = store
        self.provider = provider

    def generate(self, baseline_run_id: str, trigger_id: str | None = None):
        if trigger_id and not self.store.trigger_is_confirmed(trigger_id):
            raise ValueError("Monitoring Trigger 必须经 Human Confirm 才能启动 Agent")
        bad_cases = [item for item in self.store.bad_case_rows() if item["run_id"] == baseline_run_id]
        if not bad_cases:
            raise ValueError("该 Baseline 没有真实 Bad Case，无法生成 Candidate")
        baseline = self.store.evaluation_run(baseline_run_id)
        base_config = {**DEFAULT_PIPELINE_CONFIG, **(baseline or {}).get("config", {})}
        prior = [item["config"] for item in self.store.candidates()]
        existing_experiment = (self.store.optimization_trigger(trigger_id) or {}).get("optimization_run_id") if trigger_id else None
        completed = sum(item["status"] == "evaluated" for item in self.store.candidates(existing_experiment)) if existing_experiment else 0
        if completed >= MAX_EVALS:
            raise ValueError(f"evaluation budget exhausted: max_evals={MAX_EVALS}")
        experiment_id = existing_experiment or self.store.create_experiment(baseline_run_id)
        prompt = {
            "bad_cases": bad_cases,
            "baseline_configuration": base_config,
            "allowed_parameter_values": "V1.0.1 frozen search space only; do not propose parser/OCR/chunk/model/temperature/query_decompose/retrieval_max_tokens/rerank_top_n",
            "rule": "返回 A/B/C 三个并列、可解释 Candidate；config 可只写相对 Baseline 的改动。每个 Candidate 必须有 root_cause_cluster、observed_evidence、hypothesis、proposal、risk。",
        }
        try:
            content = self.provider.complete(
                "你是 RAG Optimization Agent。只返回 JSON：{\"root_cause_cluster\":\"...\",\"observed_evidence\":[\"...\"],\"candidates\":[{\"id\":\"A\",\"config\":{},\"hypothesis\":\"...\",\"proposal\":\"...\",\"risk\":\"...\"}]}。不得输出隐藏推理或测试答案。",
                json.dumps(prompt, ensure_ascii=False), json_mode=True,
            )
            result = json.loads(content)
            candidates = result.get("candidates", [])
            if sorted(item.get("id") for item in candidates) != ["A", "B", "C"]:
                raise ValueError("Agent 必须返回 A/B/C 三个 Candidate")
            for candidate in candidates:
                if not all(isinstance(candidate.get(field), str) and candidate[field].strip() for field in ("hypothesis", "proposal", "risk")):
                    raise ValueError("Agent Candidate 缺少可解释 Hypothesis / Proposal / Risk")
                config = {**base_config, **candidate.get("config", {})}
                check = validate_candidate_config(config, prior_configs=prior, completed_evals=completed)
                if not check["valid"]:
                    raise ValueError("Agent Candidate Config 不符合冻结 Search Space：" + "; ".join(check["errors"]))
                prior.append(config)
                self.store.save_candidate(experiment_id, candidate["id"], config, {
                    "root_cause_cluster": result.get("root_cause_cluster", "待人工复核"), "observed_evidence": result.get("observed_evidence", []), "hypothesis": candidate["hypothesis"], "proposal": candidate["proposal"], "risk": candidate["risk"],
                    "changed_parameters": candidate.get("config", {}), "source_trigger_id": trigger_id,
                })
            self.store.save_agent_trace(experiment_id, "completed", result)
            return self.store.experiment(experiment_id)
        except (ProviderUnavailable, ValueError, json.JSONDecodeError) as error:
            self.store.save_agent_trace(experiment_id, "failed", {}, str(error))
            raise ValueError(str(error)) from error

    def generate_composite_d(self, experiment_id: str, config: dict, reasoning: dict):
        """Conditional D is permitted only after independently evaluated candidates show a combination value."""
        evaluated = [item for item in self.store.candidates(experiment_id) if item["status"] == "evaluated" and item["result"].get("qualification", {}).get("qualified")]
        if len(evaluated) < 2:
            raise ValueError("Composite D requires at least two independently qualified Candidates")
        if not all(isinstance(reasoning.get(field), str) and reasoning[field].strip() for field in ("hypothesis", "proposal", "risk")):
            raise ValueError("Composite D requires hypothesis, proposal and risk")
        prior = [item["config"] for item in self.store.candidates()]
        check = validate_candidate_config(config, prior_configs=prior, completed_evals=sum(item["status"] == "evaluated" for item in self.store.candidates(experiment_id)))
        if not check["valid"]:
            raise ValueError("Composite D does not satisfy Search Space: " + "; ".join(check["errors"]))
        self.store.save_candidate(experiment_id, "D", config, reasoning)
        return self.store.candidate(f"{experiment_id}-D")
