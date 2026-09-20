import time
import json

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
        config = config or {"top_k": 4, "min_score": None}
        started_at = time.perf_counter()
        evidence = self.retriever.search(question, limit=int(config.get("top_k", 4)), min_score=config.get("min_score"))
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
        answer = self.provider.complete(
            "你是机器人官方 PDF 知识助手。只能基于给定证据回答；证据不足时明确说明。回答使用中文，简洁、可执行。",
            f"问题：{question}\n证据：\n{context}",
        )
        return {"answer": answer, "mode": "live", "model": self.provider.settings.model, "latency_ms": round((time.perf_counter() - started_at) * 1000), "retrieval": citations, "input_tokens": None, "output_tokens": None}

    def judge(self, question: str, expected: str, answer: str, category: str) -> dict:
        return self.provider.judge(question, expected, answer)

    def quality_check(self, item: dict) -> dict:
        if not self.live_enabled:
            raise ProviderUnavailable("未配置 DEEPSEEK_API_KEY")
        payload = {"question": item["question"], "reference_answer": item["reference_answer"], "evidence": item["evidence"], "category": item["test_category"]}
        content = self.provider.complete(
            "你是 Golden Dataset 质量审核助手。只返回 JSON：{\"status\":\"passed|needs_revision\",\"issues\":[\"...\"],\"reason\":\"...\"}。只检查题目、参考答案和证据是否自洽；不能替代人工审核。",
            json.dumps(payload, ensure_ascii=False),
            json_mode=True,
        )
        try:
            result = json.loads(content)
            if result.get("status") not in {"passed", "needs_revision"} or not isinstance(result.get("issues"), list) or not isinstance(result.get("reason"), str):
                raise ValueError("QC JSON schema invalid")
            return {"status": result["status"], "issues": [str(issue) for issue in result["issues"]], "reason": result["reason"], "model": self.model}
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProviderUnavailable("DeepSeek QC 未返回有效 JSON") from error

    def baseline_preview(self, question: str) -> dict:
        config = (self.store.active_production() or {"config": {"top_k": 4, "min_score": None}})["config"]
        result = self.answer(question, config)
        return {"pipeline": "baseline", "question": question, "version": (self.store.active_production() or {"id": "baseline-v1"})["id"], "sources": [], **result, "evidence": result["retrieval"], "fallback_reason": None}

    def candidate_preview(self, question: str) -> dict:
        return {"pipeline": "candidate", "question": question, "status": "not_run", "answer": "暂无可比较候选；请先完成真实 Evaluation 与 Sandbox。", "latency_ms": 0, "evidence": [], "retrieval": [], "fallback_reason": None}

    def preview(self, question: str) -> dict:
        try:
            baseline = self.baseline_preview(question)
        except ProviderUnavailable as error:
            baseline = {"pipeline": "baseline", "question": question, "version": "baseline-v1", "answer": "生成服务不可用；请先在设置中验证 Provider。", "mode": "unavailable", "model": None, "latency_ms": 0, "fallback_reason": str(error), "retrieval": [], "sources": [], "evidence": []}
        return {
            "question": question,
            "baseline": {key: baseline[key] for key in ("version", "answer", "sources")},
            "mode": baseline["mode"],
            "model": baseline["model"],
            "latency_ms": baseline["latency_ms"],
            "fallback_reason": baseline["fallback_reason"],
            "retrieval": baseline["retrieval"],
            "candidate_b": {key: baseline[key] for key in ("version", "answer", "sources", "evidence")},
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
                answer = preview["candidate_b"]["answer"]
                judgment = self.provider.judge(record["question"], record["expected_answer"], answer)
                scores.append(judgment["score"])
            except ProviderUnavailable:
                failures += 1
        return {"mode": "live", "completed": len(scores), "failed": failures, "average_score": round(sum(scores) / len(scores), 1) if scores else None, "latency_ms": round((time.perf_counter() - started_at) * 1000), "model": self.provider.settings.model}
