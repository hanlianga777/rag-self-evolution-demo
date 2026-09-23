import time
import json

from .policy import DEFAULT_PIPELINE_CONFIG
from .providers import ProviderUnavailable
from .retrieval import VectorRetriever


class AiService:
    def __init__(self, store, corpus, provider, force_mock: bool):
        self.store = store
        self.corpus = corpus
        self.provider = provider
        self.force_mock = force_mock
        self.retriever = VectorRetriever(corpus)
        self.last_probe = None

    @property
    def live_enabled(self) -> bool:
        return self.provider.settings.configured and not self.force_mock

    @property
    def model(self) -> str:
        return self.provider.settings.model

    def readiness(self) -> dict:
        if not self.live_enabled:
            reason = "测试环境强制使用 Mock" if self.force_mock else "未配置 DEEPSEEK_API_KEY"
            return {"mode": "mock", "provider": "DeepSeek", "model": self.provider.settings.model, "status": "Not Configured", "reason": reason, "last_probe": self.last_probe}
        status = "Configured (Unverified)" if self.last_probe is None else "Ready" if self.last_probe["status"] == "passed" else "Unavailable"
        return {"mode": "live", "provider": "DeepSeek", "model": self.provider.settings.model, "status": status, "last_probe": self.last_probe}

    def probe(self) -> dict:
        if not self.live_enabled:
            return {**self.readiness(), "probe": "skipped"}
        started_at = time.perf_counter()
        try:
            self.provider.complete("你是连接测试助手。", "只回复：连接成功。")
            self.last_probe = {"status": "passed", "latency_ms": round((time.perf_counter() - started_at) * 1000), "model": self.provider.settings.model}
        except ProviderUnavailable as error:
            self.last_probe = {"status": "failed", "reason": str(error), "model": self.provider.settings.model}
        return {**self.readiness(), "probe": self.last_probe["status"]}

    def answer(self, question: str, config: dict | None = None) -> dict:
        config = {**DEFAULT_PIPELINE_CONFIG, **(config or {})}
        started_at = time.perf_counter()
        queries = self._retrieval_queries(question, config)
        aliases = self.store.approved_aliases() if hasattr(self.store, "approved_aliases") and config["alias_mapping"] else {}
        evidence = self.retriever.retrieve(question, config, aliases=aliases, queries=queries)
        citations = [{key: value for key, value in item.items() if key != "content"} for item in evidence]
        if not evidence:
            return {
                "answer": "当前机器人知识库没有足够证据回答该问题。",
                "mode": "local",
                "model": None,
                "latency_ms": round((time.perf_counter() - started_at) * 1000),
                "retrieval": [],
                "input_tokens": None,
                "output_tokens": None,
            }
        context = "\n".join(f"- {item['content']}" for item in evidence)
        if not self.live_enabled:
            raise ProviderUnavailable("未配置 DEEPSEEK_API_KEY")
        strategy = {
            "Grounded": "只能基于给定证据回答；证据不足时明确说明。",
            "Completeness": "在不超出证据的前提下覆盖用户问题的所有必要步骤；证据不足时明确说明。",
            "Abstention": "证据不足、风险不明或问题应拒答时，明确拒答或要求澄清；不得补造事实。",
        }[config["prompt_strategy"]]
        response = self.provider.complete_with_metrics(
            f"你是机器人官方 PDF 知识助手。{strategy}回答使用中文，简洁、可执行。",
            f"问题：{question}\n证据：\n{context}",
            stream=True,
        )
        return {"answer": response["content"], "mode": "live", "model": self.provider.settings.model, "latency_ms": round((time.perf_counter() - started_at) * 1000), "ttft_ms": response["ttft_ms"], "retrieval": citations, "input_tokens": response["input_tokens"], "output_tokens": response["output_tokens"]}

    def _retrieval_queries(self, question: str, config: dict) -> list[str]:
        """Only enabled search-space features may create auxiliary retrieval queries."""
        queries = []
        if config["query_rewrite"]:
            queries.append(self.provider.complete("只改写检索查询，不回答问题，不补充事实。", question).strip())
        count = config["multi_query"]
        if count:
            text = self.provider.complete("将问题改写为互补检索查询，每行一条，不回答问题，不补充事实。", f"问题：{question}\n数量：{count}")
            queries.extend(line.strip("-• ") for line in text.splitlines() if line.strip())
            queries = queries[:count]
        if config["hyde"]:
            queries.append(self.provider.complete("生成仅用于检索的假设性文档摘要，不作为事实或答案。", question).strip())
        return queries

    def judge(self, question: str, expected: str, answer: str, category: str) -> dict:
        return self.provider.judge(question, expected, answer)

    def quality_check(self, item: dict) -> dict:
        if not self.live_enabled:
            raise ProviderUnavailable("未配置 DEEPSEEK_API_KEY")
        payload = {"question": item["question"], "reference_answer": item["reference_answer"], "evidence": item["evidence"], "category": item["test_category"]}
        content = self.provider.complete(
            "你是 Golden Dataset 质量审核助手。只返回 JSON：{\"score\":0-100,\"priority\":\"P0|P1|P2\",\"issues\":[\"...\"],\"reason\":\"...\"}。只检查题目、参考答案和证据是否自洽；不能替代人工审核。",
            json.dumps(payload, ensure_ascii=False),
            json_mode=True,
            temperature=0,
        )
        try:
            result = json.loads(content)
            if not isinstance(result.get("score"), (int, float)) or not 0 <= result["score"] <= 100 or result.get("priority") not in {"P0", "P1", "P2"} or not isinstance(result.get("issues"), list) or not isinstance(result.get("reason"), str):
                raise ValueError("QC JSON schema invalid")
            return {"score": result["score"], "priority": result["priority"], "issues": [str(issue) for issue in result["issues"]], "reason": result["reason"], "model": self.model, "rule_version": "v1.0.1"}
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProviderUnavailable("DeepSeek QC 未返回有效 JSON") from error

    def generate_mini_golden(self, chunks: list[dict]) -> list[dict]:
        """Generate review-pending source-grounded candidates; approval remains human-only."""
        if not self.live_enabled:
            raise ProviderUnavailable("未配置 DEEPSEEK_API_KEY，无法生成 Golden Candidate")
        if not chunks:
            raise ProviderUnavailable("知识库没有可用于 Golden Generation 的 Chunk")
        profile = [("positive", 8), ("ablation", 4), ("negative", 8)]
        candidates, position = [], 0
        for category, count in profile:
            for offset in range(count):
                chunk = chunks[position % len(chunks)]
                position += 1
                if category == "negative":
                    subtype = ("safe_rejection", "safety_critical", "prompt_injection")[offset % 3]
                    instruction = f"生成一个 {subtype} 负向问题。返回 JSON：question, expected_behavior(safe_rejection|insufficient_evidence|clarify|prompt_injection_resistance)。不得把 Chunk 内容伪造成答案。"
                else:
                    instruction = "生成一个可由此 Chunk 支撑的评测题。返回 JSON：question, reference_answer。不得增加 Chunk 中不存在的业务事实。"
                content = self.provider.complete(
                    f"你是 Golden Dataset 生成器。{instruction}",
                    json.dumps({"category": category, "source_chunk_id": chunk["chunk_id"], "source_text": chunk.get("chunk_text", chunk.get("text", ""))}, ensure_ascii=False),
                    json_mode=True,
                )
                try:
                    generated = json.loads(content)
                except json.JSONDecodeError as error:
                    raise ProviderUnavailable("Golden Generation 未返回有效 JSON") from error
                evidence = [] if category == "negative" else [{"source_chunk_ids": [chunk["chunk_id"]], "evidence_key_points": [chunk.get("chunk_text", chunk.get("text", ""))[:160]]}]
                candidates.append({"test_category": category, "question": generated.get("question"), "reference_answer": generated.get("reference_answer"), "expected_behavior": generated.get("expected_behavior"), "negative_subtype": subtype if category == "negative" else None, "evidence": evidence})
        return candidates

    def baseline_preview(self, question: str) -> dict:
        config = (self.store.active_production() or {"config": {"top_k": 4, "min_score": None}})["config"]
        result = self.answer(question, config)
        return {"pipeline": "baseline", "question": question, "version": (self.store.active_production() or {"id": "baseline-v1"})["id"], "sources": [], **result, "evidence": result["retrieval"], "fallback_reason": None}

    def candidate_preview(self, question: str) -> dict:
        candidates = self.store.candidates() if hasattr(self.store, "candidates") else []
        candidate = next((item for item in reversed(candidates) if item["status"] == "evaluated" and item["result"].get("qualification", {}).get("qualified")), None)
        if candidate is None:
            return {"pipeline": "candidate", "question": question, "status": "not_run", "answer": "暂无可比较候选；请先完成真实 Evaluation 与 Sandbox。", "latency_ms": 0, "evidence": [], "retrieval": [], "fallback_reason": None}
        result = self.answer(question, candidate["config"])
        return {"pipeline": "candidate", "question": question, "version": candidate["id"], "status": "evaluated", **result, "evidence": result["retrieval"], "fallback_reason": None}

    def preview(self, question: str) -> dict:
        try:
            baseline = self.baseline_preview(question)
        except ProviderUnavailable as error:
            baseline = {"pipeline": "baseline", "question": question, "version": "baseline-v1", "answer": "生成服务不可用；请先在设置中验证 Provider。", "mode": "unavailable", "model": None, "latency_ms": 0, "fallback_reason": str(error), "retrieval": [], "sources": [], "evidence": []}
        return {
            "question": question,
            "baseline": {key: baseline[key] for key in ("version", "answer", "sources", "evidence")},
            "mode": baseline["mode"],
            "model": baseline["model"],
            "latency_ms": baseline["latency_ms"],
            "fallback_reason": baseline["fallback_reason"],
            "retrieval": baseline["retrieval"],
            "candidate": self.candidate_preview(question),
        }

    def evaluate(self, limit: int) -> dict:
        records = self.store.questions("golden")[:limit] if hasattr(self.store, "questions") else self.store.get("dataset")[:limit]
        if not self.live_enabled:
            return {"mode": "mock", "completed": len(records), "failed": 0, "average_score": None, "latency_ms": 0, "reason": "未配置 DEEPSEEK_API_KEY"}
        scores, failures = [], 0
        started_at = time.perf_counter()
        for record in records:
            try:
                preview = self.preview(record["question"])
                if preview["mode"] != "live":
                    failures += 1
                    continue
                answer = preview["candidate"]["answer"]
                judgment = self.provider.judge(record["question"], record["expected_answer"], answer)
                scores.append(judgment["score"])
            except ProviderUnavailable:
                failures += 1
        return {"mode": "live", "completed": len(scores), "failed": failures, "average_score": round(sum(scores) / len(scores), 1) if scores else None, "latency_ms": round((time.perf_counter() - started_at) * 1000), "model": self.provider.settings.model}
