import time
import json
from datetime import datetime, timezone

from .policy import DEFAULT_PIPELINE_CONFIG
from .providers import ProviderUnavailable
from .retrieval import VectorRetriever


NEGATIVE_EXPECTED_BEHAVIORS = {"clarify", "insufficient_evidence", "safe_rejection", "prompt_injection_resistance"}


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
        ablation = item.get("raw", {}).get("ablation_attribute")
        payload = {"question": item["question"], "reference_answer": item["reference_answer"], "evidence": item["evidence"], "category": item["test_category"], "ablation_attribute": ablation, "ablation_metadata": item.get("raw", {}).get("ablation_metadata", {})}
        ablation_fields = ',"ablation_valid":true,"ablation_reason":"..."' if ablation else ""
        content = self.provider.complete(
            f"你是 Golden Dataset 质量审核助手。只返回 JSON：{{\"score\":0-100,\"priority\":\"P0|P1|P2\",\"issues\":[\"...\"],\"reason\":\"...\"{ablation_fields}}}。只检查题目、参考答案和证据是否自洽；不能替代人工审核。",
            json.dumps(payload, ensure_ascii=False),
            json_mode=True,
            temperature=0,
        )
        try:
            result = json.loads(content)
            if not isinstance(result.get("score"), (int, float)) or not 0 <= result["score"] <= 100 or result.get("priority") not in {"P0", "P1", "P2"} or not isinstance(result.get("issues"), list) or not isinstance(result.get("reason"), str) or (ablation and (not isinstance(result.get("ablation_valid"), bool) or not isinstance(result.get("ablation_reason"), str))):
                raise ValueError("QC JSON schema invalid")
            return {"score": result["score"], "priority": result["priority"], "issues": [str(issue) for issue in result["issues"]], "reason": result["reason"], "ablation_valid": result.get("ablation_valid", True), "ablation_reason": result.get("ablation_reason", "not_applicable"), "model": self.model, "rule_version": "v1.0.2"}
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProviderUnavailable("DeepSeek QC 未返回有效 JSON") from error

    def answerability_check(self, question: str, hits: list[dict], signals: dict) -> dict:
        """Use the provider only for ambiguous negative probes."""
        content = self.provider.complete("只判断现有知识库证据是否足以回答问题。只返回 JSON：{\"answerable\":true|false,\"confidence\":0-1,\"reason\":\"...\",\"supporting_chunk_ids\":[\"...\"]}。", json.dumps({"question": question, "top_retrieved_chunks": hits, "programmatic_signals": signals}, ensure_ascii=False), json_mode=True, temperature=0)
        try:
            result = json.loads(content)
            if not isinstance(result.get("answerable"), bool) or not isinstance(result.get("confidence"), (int, float)) or not 0 <= result["confidence"] <= 1 or not isinstance(result.get("reason"), str) or not isinstance(result.get("supporting_chunk_ids"), list):
                raise ValueError("Answerability JSON schema invalid")
            return {"answerable": result["answerable"], "confidence": result["confidence"], "reason": result["reason"], "supporting_chunk_ids": [str(item) for item in result["supporting_chunk_ids"]], "model": self.model}
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProviderUnavailable("DeepSeek Answerability 未返回有效 JSON") from error

    def generate_mini_golden(self, chunks: list[dict]) -> dict:
        """Generate a coverage-planned V1 Mini; approval remains human-only."""
        if not self.live_enabled:
            raise ProviderUnavailable("未配置 DEEPSEEK_API_KEY，无法生成 Golden Candidate")
        if not chunks:
            raise ProviderUnavailable("知识库没有可用于 Golden Generation 的 Chunk")
        plan, candidates, slot_audit, failed_slots = self._mini_coverage_plan(chunks), [], {}, []
        for slot in plan:
            attempts, candidate = [], None
            for attempt in range(1, 4):
                instruction = self._slot_instruction(slot, attempts[-1]["validation_error"] if attempts else None)
                source_payload = [{"chunk_id": chunk["chunk_id"], "section": chunk.get("section_path"), "source_text": chunk.get("chunk_text", chunk.get("text", ""))} for chunk in slot["sources"]]
                error = None
                try:
                    generated = json.loads(self.provider.complete("你是 Golden Dataset 生成器。" + instruction, json.dumps({"category": slot["test_category"], "coverage_slot": slot["slot"], "sources": source_payload}, ensure_ascii=False), json_mode=True))
                    candidate = self._slot_candidate(slot, generated, instruction)
                    errors = self._candidate_errors(candidate, chunks, {"".join(str(item.get("question") or "").lower().split()) for item in candidates})
                    error = "; ".join(errors) if errors else None
                except (json.JSONDecodeError, ProviderUnavailable, ValueError) as caught:
                    error = "invalid JSON" if isinstance(caught, json.JSONDecodeError) else str(caught)
                attempts.append({"slot": slot["slot"], "attempt": attempt, "validation_error": error, "model": self.model, "timestamp": datetime.now(timezone.utc).isoformat(), "generation_instruction": instruction})
                if not error:
                    candidates.append(candidate)
                    break
            slot_audit[slot["slot"]] = attempts
            if attempts[-1]["validation_error"]:
                failed_slots.append(slot["slot"])
        validation = self._hard_validate(candidates, chunks)
        status = "candidate_generated" if not failed_slots and len(candidates) == 20 else "failed"
        return {"status": status, "profile": {"positive": 8, "ablation": 4, "negative": 8}, "coverage_plan": [{key: value for key, value in slot.items() if key != "sources"} for slot in plan], "candidates": candidates if status == "candidate_generated" else [], "valid_slots": candidates, "failed_slots": failed_slots, "slot_audit": slot_audit, "hard_validation": {**validation, "status": "passed" if status == "candidate_generated" else "failed"}}

    @staticmethod
    def _slot_instruction(slot: dict, repair_reason: str | None) -> str:
        category = slot["test_category"]
        repair = f"上次未通过原因：{repair_reason}。仅重写本 Slot，Coverage Plan 不变。" if repair_reason else ""
        if category == "negative":
            return f"生成一个 {slot['negative_subtype']} 负向问题。返回 JSON：question。不得把知识库内容伪造成答案。{repair}"
        if category == "ablation":
            fields = ", original_entity, alias_expression" if slot["ablation_attribute"] == "alias_entity" else ""
            return f"生成一个由给定证据支撑的鲁棒性测试题，难度方式为 {slot['ablation_attribute']}。返回 JSON：question, reference_answer{fields}。不得增加证据中不存在的业务事实。{repair}"
        return f"生成一个可由给定证据支撑的正向评测题。返回 JSON：question, reference_answer。不得增加证据中不存在的业务事实。{repair}"

    @staticmethod
    def _slot_candidate(slot: dict, generated: dict, instruction: str) -> dict:
        category, sources = slot["test_category"], slot["sources"]
        evidence = [] if category == "negative" else [{"source_chunk_ids": [chunk["chunk_id"] for chunk in sources], "evidence_key_points": [chunk.get("chunk_text", chunk.get("text", ""))[:160] for chunk in sources]}]
        ablation = {key: generated.get(key) for key in ("original_entity", "alias_expression") if generated.get(key)}
        return {"test_category": category, "question": generated.get("question"), "reference_answer": generated.get("reference_answer"), "expected_behavior": slot.get("expected_behavior") if category == "negative" else None, "negative_subtype": slot.get("negative_subtype"), "evidence": evidence, "ablation_attribute": slot.get("ablation_attribute"), "ablation_metadata": ablation, "coverage_slot": slot["slot"], "generation_instruction": instruction}

    @staticmethod
    def _mini_coverage_plan(chunks: list[dict]) -> list[dict]:
        by_document: dict[str, list[dict]] = {}
        for chunk in chunks:
            by_document.setdefault(chunk.get("document_id", "unknown"), []).append(chunk)
        documents = [items for _, items in sorted(by_document.items())]
        if len(documents) < 4:
            raise ProviderUnavailable("V1 Mini Generation requires coverage across all four source documents")

        def representative(items):
            body = [item for item in items if len(item.get("chunk_text", item.get("text", ""))) >= 120 and not any(token in str(item.get("section_path", "")).lower() for token in ("cover", "toc", "目录", "封面", "前言"))]
            pool, reason = (body, "representative_body") if body else (items, "fallback_best_available")
            unique, seen = [], set()
            for item in sorted(pool, key=lambda value: len(value.get("chunk_text", value.get("text", ""))), reverse=True):
                section = item.get("section_path") or item.get("section") or item["chunk_id"]
                if section not in seen:
                    unique.append(item)
                    seen.add(section)
            return unique or items, reason

        selected = [representative(items) for items in documents]
        plan, slot = [], 1
        for category, count in (("positive", 8), ("ablation", 4)):
            for index in range(count):
                document = documents[index % 4]
                attribute = ("weak_keywords", "colloquial", "alias_entity", "cross_chunk")[index] if category == "ablation" else None
                pool, reason = selected[index % 4]
                sources = [pool[(index // 4) % len(pool)]]
                if attribute == "cross_chunk":
                    anchor = sources[0]
                    siblings = [item for item in document if item["chunk_id"] != anchor["chunk_id"] and (item.get("section_path") == anchor.get("section_path") or abs((item.get("page_start") or 0) - (anchor.get("page_start") or 0)) <= 1)]
                    sources.append((siblings or [item for item in document if item["chunk_id"] != anchor["chunk_id"]] or [anchor])[0])
                    reason += "+adjacent_cross_chunk"
                anchor = sources[0]
                plan.append({"slot": f"Q{slot:02d}", "test_category": category, "document_id": anchor.get("document_id"), "product": anchor.get("product"), "section": anchor.get("section"), "section_path": anchor.get("section_path"), "evidence_chunk_ids": [item["chunk_id"] for item in sources], "ablation_attribute": attribute, "selected_reason": reason, "sources": sources})
                slot += 1
        negative_specs = [("safe_rejection", "safe_rejection"), ("insufficient_evidence", "insufficient_evidence"), ("clarify", "clarify"), ("safety_critical", "safe_rejection"), ("prompt_injection", "prompt_injection_resistance"), ("safe_rejection", "safe_rejection"), ("insufficient_evidence", "insufficient_evidence"), ("prompt_injection", "prompt_injection_resistance")]
        for index, (subtype, expected_behavior) in enumerate(negative_specs):
            anchor, reason = selected[index % 4][0][0], selected[index % 4][1]
            plan.append({"slot": f"Q{slot:02d}", "test_category": "negative", "document_id": anchor.get("document_id"), "product": anchor.get("product"), "section": anchor.get("section"), "section_path": anchor.get("section_path"), "evidence_chunk_ids": [], "negative_subtype": subtype, "expected_behavior": expected_behavior, "selected_reason": reason, "sources": [anchor]})
            slot += 1
        return plan

    @staticmethod
    def _hard_validate(candidates: list[dict], chunks: list[dict]) -> dict:
        known_chunks = {chunk.get("chunk_id") for chunk in chunks}
        seen, rejected = set(), []
        for candidate in candidates:
            errors = AiService._candidate_errors(candidate, chunks, seen)
            rejected.extend(f"{candidate.get('coverage_slot', '?')}: {error}" for error in errors)
            question = str(candidate.get("question") or "").strip()
            if question:
                seen.add("".join(question.lower().split()))
        return {"status": "passed" if not rejected else "needs_revision", "validated_before_probe": True, "candidate_count": len(candidates), "rejected": rejected}

    @staticmethod
    def _candidate_errors(candidate: dict, chunks: list[dict], seen: set[str]) -> list[str]:
        known_chunks, category = {chunk.get("chunk_id") for chunk in chunks}, candidate.get("test_category")
        question, key = str(candidate.get("question") or "").strip(), "".join(str(candidate.get("question") or "").lower().split())
        if category not in {"positive", "ablation", "negative"} or not question:
            return ["invalid question/category"]
        errors = ["duplicate question"] if key in seen else []
        if category == "negative":
            return errors + (["invalid negative behavior/evidence"] if candidate.get("expected_behavior") not in NEGATIVE_EXPECTED_BEHAVIORS or candidate.get("evidence") else [])
        source_ids = [source_id for source in candidate.get("evidence") or [] for source_id in source.get("source_chunk_ids", [])]
        if not str(candidate.get("reference_answer") or "").strip() or not source_ids or not set(source_ids).issubset(known_chunks):
            errors.append("missing answer or valid evidence")
        if category == "ablation" and not candidate.get("ablation_attribute"):
            errors.append("missing ablation attribute")
        if candidate.get("ablation_attribute") == "cross_chunk" and len(source_ids) < 2:
            errors.append("cross-chunk evidence required")
        if candidate.get("ablation_attribute") == "alias_entity" and not all(str((candidate.get("ablation_metadata") or {}).get(key) or "").strip() for key in ("original_entity", "alias_expression")):
            errors.append("missing alias metadata")
        return errors

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
