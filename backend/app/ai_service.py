import time

from .providers import ProviderUnavailable
from .retrieval import LocalRetriever


class AiService:
    def __init__(self, store, provider, force_mock: bool, fallback_preview):
        self.store = store
        self.provider = provider
        self.force_mock = force_mock
        self.fallback_preview = fallback_preview
        self.retriever = LocalRetriever(store.get("documents"))
        self.last_probe = None

    @property
    def live_enabled(self) -> bool:
        return self.provider.settings.configured and not self.force_mock

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

    def preview(self, question: str) -> dict:
        fallback = self.fallback_preview(question)
        if not self.live_enabled:
            return {**fallback, "mode": "mock", "model": None, "latency_ms": None, "fallback_reason": "未配置 DEEPSEEK_API_KEY"}
        evidence = self.retriever.search(question)
        sources = [f"{item['document']} · 分块 {item['chunk']}" for item in evidence]
        context = "\n".join(f"- {item['content']}" for item in evidence)
        started_at = time.perf_counter()
        try:
            answer = self.provider.complete(
                "你是园区运营知识助手。只能基于给定证据回答；证据不足时明确说明。回答使用中文，简洁、可执行。",
                f"问题：{question}\n证据：\n{context}",
            )
        except ProviderUnavailable as error:
            return {**fallback, "mode": "mock", "model": None, "latency_ms": None, "fallback_reason": str(error), "retrieval": evidence}
        return {**fallback, "mode": "live", "model": self.provider.settings.model, "latency_ms": round((time.perf_counter() - started_at) * 1000), "fallback_reason": None, "retrieval": evidence, "candidate_b": {"version": "v1.2", "answer": answer, "sources": sources}}

    def evaluate(self, limit: int) -> dict:
        records = self.store.get("dataset")[:limit]
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
