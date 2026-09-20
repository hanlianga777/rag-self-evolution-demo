"""A single, manually-triggered optimization agent with a constrained Tool Registry."""

from __future__ import annotations

import json

from .providers import ProviderUnavailable


class OptimizationAgent:
    def __init__(self, store, provider):
        self.store = store
        self.provider = provider

    def generate(self, baseline_run_id: str):
        bad_cases = [item for item in self.store.bad_case_rows() if item["run_id"] == baseline_run_id]
        if not bad_cases:
            raise ValueError("该 Baseline 没有真实 Bad Case，无法生成 Candidate")
        available = [tool["name"] for tool in self.store.tools() if tool["availability"] == "available"]
        experiment_id = self.store.create_experiment(baseline_run_id)
        prompt = {"bad_cases": bad_cases, "available_tools": available, "rule": "只生成 A/B/C；只可使用 available_tools；每项 config 仅可含 top_k(1-12整数) 和 min_score(0-1数值或null)。"}
        try:
            content = self.provider.complete("你是 RAG Optimization Agent。只返回 JSON：{\"root_cause\":\"...\",\"candidates\":[{\"id\":\"A\",\"config\":{},\"hypothesis\":\"...\",\"risk\":\"...\"}]}。", json.dumps(prompt, ensure_ascii=False), json_mode=True)
            result = json.loads(content)
            candidates = result.get("candidates", [])
            ids = [item.get("id") for item in candidates]
            if sorted(ids) != ["A", "B", "C"]:
                raise ValueError("Agent 必须返回 A/B/C 三个 Candidate")
            for candidate in candidates:
                config = candidate.get("config", {})
                if set(config) - {"top_k", "min_score"} or not isinstance(config.get("top_k"), int) or not 1 <= config["top_k"] <= 12 or (config.get("min_score") is not None and not isinstance(config["min_score"], (int, float))):
                    raise ValueError("Agent Candidate Config 不符合可用 Tool Registry")
                self.store.save_candidate(experiment_id, candidate["id"], config, {"root_cause": result.get("root_cause", "待人工复核"), "hypothesis": candidate.get("hypothesis", ""), "risk": candidate.get("risk", "")})
            self.store.save_agent_trace(experiment_id, "completed", result)
            return self.store.experiment(experiment_id)
        except (ProviderUnavailable, ValueError, json.JSONDecodeError) as error:
            self.store.save_agent_trace(experiment_id, "failed", {}, str(error))
            raise ValueError(str(error)) from error
