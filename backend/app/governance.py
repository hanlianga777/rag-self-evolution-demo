"""SQLite-backed Golden Dataset governance for the local RAG demo."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS
from .corpus import EMBEDDING_MODEL


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "demo.db"
GOLDEN_DRAFT = ROOT / "reports" / "golden_dataset_full_draft.json"
GENERATION_PROFILES = {
    "mini": {"positive": 8, "ablation": 4, "negative": 8},
    "medium": {"positive": 20, "ablation": 10, "negative": 20},
    "full": {"positive": 40, "ablation": 20, "negative": 40},
}
NEGATIVE_EXPECTED_BEHAVIORS = {"clarify", "insufficient_evidence", "safe_rejection", "prompt_injection_resistance"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value, fallback):
    try:
        return json.loads(value) if value else fallback
    except json.JSONDecodeError:
        return fallback


def _normalized(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


class GovernanceStore:
    """Small persistence boundary; JSON keeps evidence and run snapshots immutable."""

    def __init__(self, database_path: Path | str | None = None):
        self.database_path = Path(database_path or DEFAULT_DATABASE)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def migrate(self):
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dataset_versions (id TEXT PRIMARY KEY, status TEXT NOT NULL, source TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY, stage TEXT NOT NULL, legacy_question_type TEXT NOT NULL,
                    test_category TEXT NOT NULL, negative_subtype TEXT, review_status TEXT NOT NULL,
                    probe_status TEXT NOT NULL, qc_status TEXT NOT NULL, question TEXT NOT NULL, reference_answer TEXT,
                    evidence_json TEXT NOT NULL, raw_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS probe_results (id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS qc_results (id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_events (id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, gate TEXT NOT NULL, decision TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evaluation_runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, run_mode TEXT NOT NULL, data_source TEXT NOT NULL, dataset_version_id TEXT, dataset_snapshot_json TEXT NOT NULL, config_json TEXT NOT NULL, judge_json TEXT NOT NULL, result_json TEXT NOT NULL, error_message TEXT, created_at TEXT NOT NULL, completed_at TEXT);
                CREATE TABLE IF NOT EXISTS evaluation_case_results (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, question_id TEXT NOT NULL, result_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS bad_cases (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, question_id TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, baseline_run_id TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS candidate_configs (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, status TEXT NOT NULL, config_json TEXT NOT NULL, reasoning_json TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS agent_traces (id INTEGER PRIMARY KEY, experiment_id TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, error_message TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tool_calls (id INTEGER PRIMARY KEY, experiment_id TEXT NOT NULL, tool_name TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY, gate TEXT NOT NULL, target_id TEXT NOT NULL, decision TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS production_versions (id TEXT PRIMARY KEY, status TEXT NOT NULL, config_json TEXT NOT NULL, evaluation_run_id TEXT, dataset_version_id TEXT, approval_id INTEGER, previous_version_id TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rollback_history (id INTEGER PRIMARY KEY, from_version_id TEXT NOT NULL, to_version_id TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tool_registry (name TEXT PRIMARY KEY, availability TEXT NOT NULL, metadata_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS monitoring_events (
                    id TEXT PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL, bad_case INTEGER NOT NULL,
                    severity TEXT NOT NULL, determinable INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS optimization_triggers (
                    id TEXT PRIMARY KEY, reason TEXT NOT NULL, event_id TEXT, status TEXT NOT NULL,
                    actor TEXT, created_at TEXT NOT NULL, confirmed_at TEXT, optimization_run_id TEXT
                );
                CREATE TABLE IF NOT EXISTS golden_generation_runs (
                    id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, model_version TEXT NOT NULL,
                    status TEXT NOT NULL, question_ids_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recommendations (
                    experiment_id TEXT PRIMARY KEY, candidate_id TEXT, status TEXT NOT NULL,
                    result_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alias_mappings (
                    alias TEXT PRIMARY KEY, canonical TEXT NOT NULL, status TEXT NOT NULL,
                    actor TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS golden_generation_artifacts (
                    generation_run_id TEXT PRIMARY KEY, coverage_plan_json TEXT NOT NULL,
                    question_plan_json TEXT NOT NULL, hard_validation_json TEXT NOT NULL
                );
                """
            )
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'golden-draft-v1'").fetchone():
                draft = _load(GOLDEN_DRAFT.read_text(encoding="utf-8"), {})
                now = _now()
                for item in draft.get("cases", []):
                    legacy_type = item["question_type"]
                    category = "positive" if legacy_type.startswith("grounded") else "negative"
                    subtype = legacy_type if category == "negative" else None
                    connection.execute(
                        "INSERT OR IGNORE INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            item["id"], "candidate", legacy_type, category, subtype, "human_review_pending", "probe_pending", "qc_pending",
                            item["question"], item.get("reference_answer"), _json(item.get("acceptable_evidence", [])), _json(item), now, now,
                        ),
                    )
                connection.execute(
                    "INSERT OR IGNORE INTO dataset_versions VALUES (?, ?, ?, ?, ?)",
                    ("GD-candidate-v1", "candidate", "golden_dataset_full_draft.json", _json({"question_ids": [item["id"] for item in draft.get("cases", [])]}), now),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO production_versions (id, status, config_json, evaluation_run_id, dataset_version_id, approval_id, previous_version_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("baseline-v1", "active", _json({"top_k": 4, "min_score": None}), None, None, None, None, now),
                )
                connection.execute("INSERT INTO schema_migrations VALUES (?, ?)", ("golden-draft-v1", now))
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'governance-flow-v2'").fetchone():
                columns = {row[1] for row in connection.execute("PRAGMA table_info(questions)")}
                if "qc_status" not in columns:
                    connection.execute("ALTER TABLE questions ADD COLUMN qc_status TEXT NOT NULL DEFAULT 'qc_pending'")
                connection.execute(
                    """UPDATE questions SET qc_status = COALESCE((
                        SELECT CASE status WHEN 'passed' THEN 'qc_passed' ELSE 'qc_failed' END
                        FROM qc_results WHERE qc_results.question_id = questions.id ORDER BY id DESC LIMIT 1
                    ), 'qc_pending')"""
                )
                invalid = connection.execute("SELECT id FROM questions WHERE stage = 'golden' AND (probe_status != 'probe_passed' OR qc_status != 'qc_passed')").fetchall()
                for row in invalid:
                    connection.execute("UPDATE questions SET stage = ?, review_status = ?, updated_at = ? WHERE id = ?", ("candidate", "human_review_pending", _now(), row["id"]))
                    connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (row["id"], "dataset", "workflow_repaired", "migration", _now()))
                connection.execute("INSERT INTO schema_migrations VALUES (?, ?)", ("governance-flow-v2", _now()))
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'v101-governance-results'").fetchone():
                trigger_columns = {row[1] for row in connection.execute("PRAGMA table_info(optimization_triggers)")}
                if "optimization_run_id" not in trigger_columns:
                    connection.execute("ALTER TABLE optimization_triggers ADD COLUMN optimization_run_id TEXT")
                connection.execute("INSERT INTO schema_migrations VALUES (?, ?)", ("v101-governance-results", _now()))
            version_columns = {row[1] for row in connection.execute("PRAGMA table_info(production_versions)")}
            if "snapshot_json" not in version_columns:
                connection.execute("ALTER TABLE production_versions ADD COLUMN snapshot_json TEXT NOT NULL DEFAULT '{}'")
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'v101-provenance-boundary'").fetchone():
                connection.execute("UPDATE questions SET stage = 'candidate', review_status = 'human_review_pending', probe_status = 'probe_pending', qc_status = 'qc_pending', updated_at = ? WHERE stage = 'golden' AND raw_json NOT LIKE '%\"generation_profile\": \"v1-mini-8-4-8\"%'", (_now(),))
                connection.execute("UPDATE dataset_versions SET status = 'legacy_unverified' WHERE status = 'approved' AND snapshot_json NOT LIKE '%\"generation_profile\": \"v1-mini-8-4-8\"%'")
                connection.execute("UPDATE evaluation_runs SET status = 'legacy_unverified' WHERE result_json NOT LIKE '%\"gates\"%'")
                connection.execute("UPDATE production_versions SET config_json = ? WHERE id = 'baseline-v1'", (_json(DEFAULT_PIPELINE_CONFIG),))
                connection.execute("INSERT INTO schema_migrations VALUES (?, ?)", ("v101-provenance-boundary", _now()))
            for name, availability, description in (
                ("top_k", "available", "调整向量检索返回条数"),
                ("min_score", "available", "过滤低相关度向量结果"),
                ("rerank", "unavailable", "当前运行时未实现"),
                ("query_rewrite", "unavailable", "当前运行时未实现"),
                ("hybrid_search", "unavailable", "当前运行时未实现"),
            ):
                connection.execute("INSERT OR IGNORE INTO tool_registry VALUES (?, ?, ?)", (name, availability, _json({"description": description})))

    @staticmethod
    def _row(row):
        item = dict(row)
        item["evidence"] = _load(item.pop("evidence_json", "[]"), [])
        item["raw"] = _load(item.pop("raw_json", "{}"), {})
        return item

    def questions(self, stage: str | None = None):
        query, args = "SELECT * FROM questions", []
        if stage:
            query += " WHERE stage = ?"
            args.append(stage)
        query += " ORDER BY id"
        with self.connection() as connection:
            return [self._row(row) for row in connection.execute(query, args)]

    def question(self, question_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if row is None:
            raise KeyError(question_id)
        return self._row(row)

    def dataset_summary(self):
        rows = self.questions()
        return {
            "total": len(rows),
            "positive": sum(row["test_category"] == "positive" for row in rows),
            "negative": sum(row["test_category"] == "negative" for row in rows),
            "ablation": sum(row["test_category"] == "ablation" for row in rows),
            "approved": sum(row["stage"] == "golden" for row in rows),
            "pending_review": sum(row["review_status"] == "human_review_pending" for row in rows),
        }

    def approved_aliases(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT alias, canonical FROM alias_mappings WHERE status = 'approved' ORDER BY alias").fetchall()
        return {row["alias"]: row["canonical"] for row in rows}

    def approve_alias(self, alias: str, canonical: str, actor: str):
        if not alias.strip() or not canonical.strip():
            raise ValueError("Alias and canonical value are required")
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO alias_mappings VALUES (?, ?, ?, ?, ?)", (alias.strip(), canonical.strip(), "approved", actor, _now()))
        return {"alias": alias.strip(), "canonical": canonical.strip(), "status": "approved", "actor": actor}

    def start_generation_run(self, model_version: str):
        run_id, now = f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", _now()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM golden_generation_runs WHERE status IN ('queued', 'coverage', 'generating', 'validation', 'probing', 'qc') LIMIT 1").fetchone():
                raise ValueError("已有 V1 Mini Generation Run 正在执行")
            connection.execute("INSERT INTO golden_generation_runs VALUES (?, ?, ?, ?, ?, ?)", (run_id, _json(GENERATION_PROFILES["mini"]), model_version, "queued", _json([]), now))
            connection.execute("INSERT INTO golden_generation_artifacts VALUES (?, ?, ?, ?)", (run_id, _json([]), _json([]), _json({"progress": {"stage": "queued", "completed_slots": 0, "total_slots": 20, "probe_completed": 0, "qc_completed": 0}})))
        return run_id

    def update_generation_run(self, run_id: str, *, status: str, progress: dict | None = None, coverage_plan: list[dict] | None = None, validation: dict | None = None):
        with self.connection() as connection:
            row = connection.execute("SELECT coverage_plan_json, hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            audit = _load(row["hard_validation_json"], {})
            audit.update(validation or {})
            if progress:
                audit["progress"] = {**audit.get("progress", {}), **progress}
            connection.execute("UPDATE golden_generation_runs SET status = ? WHERE id = ?", (status, run_id))
            connection.execute("UPDATE golden_generation_artifacts SET coverage_plan_json = ?, hard_validation_json = ? WHERE generation_run_id = ?", (_json(coverage_plan if coverage_plan is not None else _load(row["coverage_plan_json"], [])), _json(audit), run_id))

    def save_mini_golden_candidates(self, candidates: list[dict], model_version: str, *, coverage_plan: list[dict] | None = None, hard_validation: dict | None = None, slot_audit: dict | None = None, run_id: str | None = None):
        """Persist the V1 Mini profile only as review-pending candidates, never as Golden."""
        expected = GENERATION_PROFILES["mini"]
        actual = {category: sum(item.get("test_category") == category for item in candidates) for category in expected}
        if actual != expected or len(candidates) != 20:
            raise ValueError("V1 Mini Golden profile must be Positive 8 / Ablation 4 / Negative 8")
        existing_run = run_id is not None
        run_id = run_id or f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        question_ids, now = [], _now()
        with self.connection() as connection:
            for serial, candidate in enumerate(candidates, start=1):
                category = candidate["test_category"]
                question = str(candidate.get("question", "")).strip()
                answer = candidate.get("reference_answer")
                expected_behavior = candidate.get("expected_behavior")
                evidence = candidate.get("evidence") or []
                if not question or (category != "negative" and (not isinstance(answer, str) or not answer.strip() or not evidence)) or (category == "negative" and expected_behavior not in NEGATIVE_EXPECTED_BEHAVIORS):
                    raise ValueError("Generated Golden candidate failed hard validation")
                question_id = f"V1G-{run_id[-12:]}-{serial:02d}"
                raw = {"id": question_id, "question": question, "reference_answer": answer, "acceptable_evidence": evidence, "expected_behavior": expected_behavior, "generation_profile": "v1-mini-8-4-8", "generation_run_id": run_id, "generation_model": model_version, "ablation_attribute": candidate.get("ablation_attribute"), "ablation_metadata": candidate.get("ablation_metadata", {}), "coverage_slot": candidate.get("coverage_slot"), "generation_instruction": candidate.get("generation_instruction")}
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (question_id, "candidate", "v1_mini", category, candidate.get("negative_subtype"), "human_review_pending", "probe_pending", "qc_pending", question, answer, _json(evidence), _json(raw), now, now))
                question_ids.append(question_id)
            if existing_run:
                connection.execute("UPDATE golden_generation_runs SET status = 'probing', question_ids_json = ? WHERE id = ?", (_json(question_ids), run_id))
            else:
                connection.execute("INSERT INTO golden_generation_runs VALUES (?, ?, ?, ?, ?, ?)", (run_id, _json(expected), model_version, "candidate_generated", _json(question_ids), now))
            coverage = coverage_plan or [{"test_category": item["test_category"], "source_chunk_ids": [chunk_id for source in item.get("evidence", []) for chunk_id in source.get("source_chunk_ids", [])]} for item in candidates]
            question_plan = [{"question_id": question_id, "test_category": item["test_category"], "negative_subtype": item.get("negative_subtype"), "ablation_attribute": item.get("ablation_attribute"), "coverage_slot": item.get("coverage_slot")} for question_id, item in zip(question_ids, candidates)]
            previous = _load(connection.execute("SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id = ?", (run_id,)).fetchone()[0], {}) if existing_run else {}
            validation = {**previous, "status": "passed", "profile": "mini", "counts": actual, "validated_at": now, "slot_audit": slot_audit if slot_audit is not None else previous.get("slot_audit", {}), **(hard_validation or {})}
            connection.execute("INSERT OR REPLACE INTO golden_generation_artifacts VALUES (?, ?, ?, ?)", (run_id, _json(coverage), _json(question_plan), _json(validation)))
        return [self.question(question_id) for question_id in question_ids]

    def save_failed_generation_run(self, profile: dict, model_version: str, coverage_plan: list[dict], hard_validation: dict, slot_audit: dict, failed_slots: list[str]):
        """Persist a terminal generation audit without exposing partial candidates for review."""
        run_id, now = f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", _now()
        validation = {**hard_validation, "slot_audit": slot_audit, "failed_slots": failed_slots, "validated_at": now}
        with self.connection() as connection:
            connection.execute("INSERT INTO golden_generation_runs VALUES (?, ?, ?, ?, ?, ?)", (run_id, _json(profile), model_version, "failed", _json([]), now))
            connection.execute("INSERT INTO golden_generation_artifacts VALUES (?, ?, ?, ?)", (run_id, _json(coverage_plan), _json([]), _json(validation)))
        return next(item for item in self.generation_runs() if item["id"] == run_id)

    def generation_artifacts(self, generation_run_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM golden_generation_artifacts WHERE generation_run_id = ?", (generation_run_id,)).fetchone()
        if row is None:
            return None
        validation = _load(row["hard_validation_json"], {})
        return {**dict(row), "coverage_plan": _load(row["coverage_plan_json"], []), "question_plan": _load(row["question_plan_json"], []), "hard_validation": validation, "slot_audit": validation.get("slot_audit", {}), "failed_slots": validation.get("failed_slots", [])}

    def generation_runs(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM golden_generation_runs ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "profile": _load(row["profile_json"], {}), "question_ids": _load(row["question_ids_json"], []), "artifacts": self.generation_artifacts(row["id"])} for row in rows]

    def generation_run(self, run_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM golden_generation_runs WHERE id = ?", (run_id,)).fetchone()
        return {**dict(row), "profile": _load(row["profile_json"], {}), "question_ids": _load(row["question_ids_json"], []), "artifacts": self.generation_artifacts(run_id)} if row else None

    def review_question(self, question_id: str, decision: str, actor: str):
        if decision not in {"approved", "rejected", "needs_revision"}:
            raise ValueError("Unsupported review decision")
        current = self.question(question_id)
        if decision == "approved" and (current["probe_status"] != "probe_passed" or current["qc_status"] != "qc_passed"):
            raise ValueError("Probe Passed 和 QC Passed 后才能批准 Golden")
        status = "approved" if decision == "approved" else decision
        stage = "golden" if decision == "approved" else "candidate"
        with self.connection() as connection:
            if not connection.execute("SELECT 1 FROM questions WHERE id = ?", (question_id,)).fetchone():
                raise KeyError(question_id)
            connection.execute("UPDATE questions SET stage = ?, review_status = ?, updated_at = ? WHERE id = ?", (stage, status, _now(), question_id))
            connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (question_id, "dataset", decision, actor, _now()))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, decision, actor, _now()))
        return self.question(question_id)

    def review_history(self, question_id: str):
        with self.connection() as connection:
            return [dict(row) for row in connection.execute("SELECT gate, decision, actor, created_at FROM review_events WHERE question_id = ? ORDER BY id DESC", (question_id,))]

    def update_question(self, question_id: str, question: str, reference_answer: str | None, evidence: list, actor: str):
        current = self.question(question_id)
        changed = (question != current["question"] or reference_answer != current["reference_answer"] or evidence != current["evidence"])
        if not changed:
            return current
        raw = {**current["raw"], "question": question, "reference_answer": reference_answer, "acceptable_evidence": evidence}
        with self.connection() as connection:
            connection.execute("UPDATE questions SET stage = ?, review_status = ?, probe_status = ?, qc_status = ?, question = ?, reference_answer = ?, evidence_json = ?, raw_json = ?, updated_at = ? WHERE id = ?", ("candidate", "human_review_pending", "probe_pending", "qc_pending", question, reference_answer, _json(evidence), _json(raw), _now(), question_id))
            connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (question_id, "dataset", "invalidated", actor, _now()))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, "invalidated", actor, _now()))
        return self.question(question_id)

    def create_dataset_snapshot(self, approved: list[dict] | None = None, generation_run_id: str | None = None):
        approved = approved if approved is not None else self.questions("golden")
        snapshot = {"question_ids": [item["id"] for item in approved], "questions": [item["raw"] for item in approved]}
        if generation_run_id:
            snapshot["generation_run_id"] = generation_run_id
        version_id = f"GD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        with self.connection() as connection:
            connection.execute("INSERT INTO dataset_versions VALUES (?, ?, ?, ?, ?)", (version_id, "approved", "human_review", _json(snapshot), _now()))
        return {"id": version_id, **snapshot}

    def dataset_snapshots(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM dataset_versions WHERE status = 'approved' ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "snapshot": {"id": row["id"], **_load(row["snapshot_json"], {})}} for row in rows]

    def create_generation_snapshot(self, generation_run_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM golden_generation_runs WHERE id = ?", (generation_run_id,)).fetchone()
        if row is None:
            raise KeyError(generation_run_id)
        question_ids = _load(row["question_ids_json"], [])
        approved = [self.question(question_id) for question_id in question_ids]
        if len(approved) != 20 or any(item["stage"] != "golden" for item in approved):
            raise ValueError("同一 V1 Mini Generation Run 的 20 道题必须全部完成人工批准后才能创建 Snapshot")
        return self.create_dataset_snapshot(approved, generation_run_id)

    def run_probe(self, question_id: str, retriever, chunks: list[dict], answerability_judge=None):
        item = self.question(question_id)
        evidence = item["evidence"]
        expected_chunks = {chunk_id for source in evidence for chunk_id in source.get("source_chunk_ids", [])}
        available_chunks = {chunk.get("chunk_id") for chunk in chunks}
        positive = item["test_category"] != "negative"
        expected_behavior = item["raw"].get("expected_behavior")
        programmatic = {
            "question": bool(item["question"].strip()),
            "reference_answer": bool(item["reference_answer"]) if positive else True,
            "expected_behavior": True if positive else expected_behavior in NEGATIVE_EXPECTED_BEHAVIORS,
            "evidence": bool(evidence) if positive else True,
            "source_chunks": expected_chunks.issubset(available_chunks) if positive else True,
        }
        if positive and hasattr(retriever, "retrieve"):
            hits = retriever.retrieve(item["question"], DEFAULT_PIPELINE_CONFIG)
        else:
            hits = retriever.search(item["question"], limit=4)
        best = max((hit.get("score", 0) for hit in hits), default=0)
        source_texts = {chunk.get("chunk_id"): chunk.get("text", chunk.get("chunk_text", "")) for chunk in chunks}
        haystack = " ".join(source_texts.values())
        phrases = [point for source in evidence for point in source.get("evidence_key_points", [])]
        matched = [phrase for phrase in phrases if phrase and phrase in haystack]
        source_checks = [{"chunk_id": chunk_id, "text_available": bool(source_texts.get(chunk_id, "").strip())} for chunk_id in sorted(expected_chunks)]
        normalized_query = _normalized(item["question"])
        corpus_matches = [chunk_id for chunk_id, text in source_texts.items() if normalized_query and normalized_query in _normalized(text)]
        entity_tokens = [token for token in item["question"].replace("/", " ").replace("-", " ").split() if len(token) > 1 and any(character.isdigit() or character.isascii() and character.isalpha() for character in token)]
        entity_matches = [chunk_id for chunk_id, text in source_texts.items() if any(token.lower() in text.lower() for token in entity_tokens)]
        direct_negative_hit = bool(corpus_matches or entity_matches or best >= .95)
        ambiguous_negative = not direct_negative_hit and (best >= .75 or bool(entity_matches))
        answerability = None
        if not positive and ambiguous_negative:
            try:
                answerability = answerability_judge(item["question"], hits, {"vector_best_similarity": best, "full_text_hits": corpus_matches, "entity_hits": entity_matches}) if answerability_judge else {"answerable": None, "reason": "Answerability Judge unavailable"}
            except Exception as error:
                answerability = {"answerable": None, "reason": str(error)}
        negative_passed = bool(expected_behavior) and not direct_negative_hit and (not ambiguous_negative or answerability.get("answerable") is False)
        full_text = {"mode": "evidence" if positive else "fake_negative_check", "phrases": phrases, "matched_phrases": matched, "source_checks": source_checks, "normalized_query": normalized_query, "corpus_match_chunk_ids": corpus_matches, "entity_match_chunk_ids": entity_matches, "passed": bool(source_checks) and all(check["text_available"] for check in source_checks) if positive else negative_passed}
        evidence_valid = all(programmatic.values()) and full_text["passed"]
        recalled = bool(expected_chunks & {hit.get("chunk_id") for hit in hits}) if positive else None
        classification = "RETRIEVAL_INCOHERENT" if positive and evidence_valid and not recalled else "EVIDENCE_VALID" if positive and evidence_valid else "EVIDENCE_INVALID" if positive else "NEGATIVE_VALID" if evidence_valid else "FAKE_NEGATIVE_RISK"
        negative_checks = None if positive else {
            "vector_probe": {"observed_hits": hits, "passed": not any(hit.get("score", 0) >= .95 for hit in hits)},
            "full_text_probe": {"corpus_match_chunk_ids": corpus_matches, "entity_match_chunk_ids": entity_matches, "passed": not (corpus_matches or entity_matches)},
            "answerability": answerability,
            "fake_negative_check": {"expected_behavior": expected_behavior, "ambiguous": ambiguous_negative, "passed": negative_passed},
        }
        result = self.record_probe_result(question_id, {
            "question_quality": 30 if bool(item["question"].strip()) else 0,
            "golden_answer_quality": 30 if (not positive or bool(item["reference_answer"])) else 0,
            "evidence_support": 40 if evidence_valid else 0,
            "evidence_direct_failure": not evidence_valid,
            "reason": "Evidence exists but the production pipeline did not recall it" if classification == "RETRIEVAL_INCOHERENT" else "Programmatic evidence check" if evidence_valid else "Negative may be answerable" if classification == "FAKE_NEGATIVE_RISK" else "Evidence or required fields cannot support Golden",
            "rule_version": "v1.0.2",
            "model_version": "programmatic-probe-v1",
            "probe_details": {"pipeline": "CandidateK → Hybrid → Lightweight second-stage ranking → MinScore → TopK" if positive else "vector + full-text fake-negative check", "vector": {"top_k": hits, "best_similarity": best}, "full_text": full_text, "negative_checks": negative_checks, "classification": classification, "retrieval_coherent": recalled},
        })
        return {**result, "classification": classification, "programmatic": {"checks": programmatic, "passed": all(programmatic.values())}, "vector": {"top_k": hits, "best_similarity": best, "signal": "observed_only"}, "full_text": full_text, "passed": result["status"] == "passed"}

    def record_probe_result(self, question_id: str, result: dict):
        """Persist the frozen 30/30/40 probe; evidence failure is non-compensable."""
        self.question(question_id)
        caps = {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40}
        scores = {}
        for field, cap in caps.items():
            value = result.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= cap:
                raise ValueError(f"Invalid {field} score")
            scores[field] = float(value)
        evidence_direct_failure = result.get("evidence_direct_failure") is True
        score = round(sum(scores.values()), 1)
        passed = score >= 90 and not evidence_direct_failure
        stored = {
            "question_id": question_id, **scores, "score": score,
            "threshold": 90, "evidence_direct_failure": evidence_direct_failure,
            "status": "passed" if passed else "failed", "reason": str(result.get("reason", "")),
            "rule_version": str(result.get("rule_version", "v1.0.1")),
            "model_version": str(result.get("model_version", "programmatic-probe-v1")),
            "probe_details": result.get("probe_details", {}),
        }
        with self.connection() as connection:
            connection.execute("INSERT INTO probe_results(question_id, result_json, created_at) VALUES (?, ?, ?)", (question_id, _json(stored), _now()))
            connection.execute("UPDATE questions SET probe_status = ?, review_status = ?, updated_at = ? WHERE id = ?", ("probe_passed" if passed else "needs_revision", "human_review_pending" if passed else "needs_revision", _now(), question_id))
        return stored

    def review_generation_batch(self, question_ids: list[str], actor: str, *, confirmed_manual_review: bool = False):
        if not confirmed_manual_review:
            raise ValueError("Human Review confirmation is required")
        candidates = [self.question(question_id) for question_id in question_ids]
        runs = {item["raw"].get("generation_run_id") for item in candidates}
        if len(candidates) != 20 or len(runs) != 1 or None in runs or any(item["raw"].get("generation_profile") != "v1-mini-8-4-8" for item in candidates):
            raise ValueError("Batch review only accepts one complete V1 Mini generation run")
        if any(item["probe_status"] != "probe_passed" or item["qc_status"] != "qc_passed" for item in candidates):
            raise ValueError("All Mini candidates must pass Probe and QC before batch approval")
        now = _now()
        with self.connection() as connection:
            for question_id in question_ids:
                connection.execute("UPDATE questions SET stage = ?, review_status = ?, updated_at = ? WHERE id = ?", ("golden", "approved", now, question_id))
                connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (question_id, "dataset", "approved", actor, now))
                connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, "approved", actor, now))
        return {"reviewed": [self.question(question_id) for question_id in question_ids], "generation_run_id": next(iter(runs))}

    def record_qc(self, question_id: str, result: dict, status: str):
        item = self.question(question_id)
        if item["probe_status"] != "probe_passed":
            raise ValueError("Probe Passed 后才能运行 QC")
        score = result.get("score")
        priority = result.get("priority")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
            raise ValueError("QC score must be between 0 and 100")
        if priority not in {"P0", "P1", "P2"}:
            raise ValueError("QC priority must be P0, P1, or P2")
        ablation_valid = result.get("ablation_valid", True)
        qc_status = "qc_passed" if status == "passed" and score >= 85 and ablation_valid is True else "qc_failed"
        result = {**result, "score": float(score), "priority": priority, "threshold": 85, "status": qc_status, "rule_version": result.get("rule_version", "v1.0.1")}
        with self.connection() as connection:
            connection.execute("INSERT INTO qc_results(question_id, status, result_json, created_at) VALUES (?, ?, ?, ?)", (question_id, qc_status, _json(result), _now()))
            review_status = item["review_status"] if qc_status == "qc_passed" else "needs_revision"
            connection.execute("UPDATE questions SET qc_status = ?, review_status = ?, updated_at = ? WHERE id = ?", (qc_status, review_status, _now(), question_id))
        return {"question_id": question_id, "status": qc_status, "result": result}

    def qc_history(self, question_id: str):
        with self.connection() as connection:
            rows = connection.execute("SELECT status, result_json, created_at FROM qc_results WHERE question_id = ? ORDER BY id DESC", (question_id,)).fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {})} for row in rows]

    def production_versions(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM production_versions ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "config": _load(row["config_json"], {}), "snapshot": _load(row["snapshot_json"] if "snapshot_json" in row.keys() else "{}", {})} for row in rows]

    def active_production(self):
        return next((item for item in self.production_versions() if item["status"] == "active"), None)

    def evaluation_runs(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM evaluation_runs ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {}), "config": _load(row["config_json"], {}), "judge": _load(row["judge_json"], {})} for row in rows]

    def evaluation_run(self, run_id: str):
        return next((item for item in self.evaluation_runs() if item["id"] == run_id), None)

    def bad_case_rows(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM bad_cases ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {})} for row in rows]

    def create_evaluation_run(self, snapshot: dict, config: dict, judge: dict):
        run_id = f"EVAL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO evaluation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "running", "real", "real", snapshot["id"], _json(snapshot), _json(config), _json(judge), _json({}), None, _now(), None),
            )
        return run_id

    def record_evaluation_case(self, run_id: str, question_id: str, result: dict):
        with self.connection() as connection:
            connection.execute("INSERT INTO evaluation_case_results(run_id, question_id, result_json) VALUES (?, ?, ?)", (run_id, question_id, _json(result)))

    def finish_evaluation_run(self, run_id: str, status: str, result: dict, error_message: str | None = None):
        with self.connection() as connection:
            connection.execute("UPDATE evaluation_runs SET status = ?, result_json = ?, error_message = ?, completed_at = ? WHERE id = ?", (status, _json(result), error_message, _now(), run_id))
        return next(item for item in self.evaluation_runs() if item["id"] == run_id)

    def evaluation_case_results(self, run_id: str):
        with self.connection() as connection:
            rows = connection.execute("SELECT question_id, result_json FROM evaluation_case_results WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        return [{"question_id": row["question_id"], **_load(row["result_json"], {})} for row in rows]

    def record_bad_case(self, run_id: str, question_id: str, category: str, severity: str, result: dict):
        case_id = f"BC-{run_id}-{question_id}"
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO bad_cases VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (case_id, run_id, question_id, category, severity, "new", _json(result), _now()))
        return case_id

    def tools(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM tool_registry ORDER BY name").fetchall()
        return [{"name": row["name"], "availability": row["availability"], **_load(row["metadata_json"], {})} for row in rows]

    def create_experiment(self, baseline_run_id: str, status: str = "analyzing"):
        experiment_id = f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        with self.connection() as connection:
            connection.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?)", (experiment_id, baseline_run_id, status, _json({}), _now()))
        return experiment_id

    def save_agent_trace(self, experiment_id: str, status: str, result: dict, error_message: str | None = None):
        with self.connection() as connection:
            connection.execute("INSERT INTO agent_traces(experiment_id, status, result_json, error_message, created_at) VALUES (?, ?, ?, ?, ?)", (experiment_id, status, _json(result), error_message, _now()))
            connection.execute("UPDATE experiments SET status = ?, result_json = ? WHERE id = ?", (status, _json(result), experiment_id))

    def save_candidate(self, experiment_id: str, candidate_id: str, config: dict, reasoning: dict):
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO candidate_configs VALUES (?, ?, ?, ?, ?, ?, ?)", (f"{experiment_id}-{candidate_id}", experiment_id, "generated", _json(config), _json(reasoning), _json({}), _now()))

    def create_direct_release_candidate(self, baseline_run_id: str, config: dict, actor: str):
        experiment_id = self.create_experiment(baseline_run_id, "direct_release")
        self.save_candidate(experiment_id, "DIRECT", config, {"root_cause_cluster": "Human Direct Release", "observed_evidence": [], "hypothesis": "Human-confirmed configuration", "proposal": "Skip Agent search only; preserve Sandbox validation", "risk": "Requires complete Gate and Regression verification", "changed_parameters": config, "operator": actor})
        return self.candidate(f"{experiment_id}-DIRECT")

    def candidate(self, candidate_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM candidate_configs WHERE id = ?", (candidate_id,)).fetchone()
        if row is None:
            return None
        return {**dict(row), "config": _load(row["config_json"], {}), "reasoning": _load(row["reasoning_json"], {}), "result": _load(row["result_json"], {})}

    def candidates(self, experiment_id: str | None = None):
        with self.connection() as connection:
            query, args = "SELECT * FROM candidate_configs", []
            if experiment_id:
                query += " WHERE experiment_id = ?"
                args.append(experiment_id)
            rows = connection.execute(query + " ORDER BY created_at", args).fetchall()
        return [{**dict(row), "config": _load(row["config_json"], {}), "reasoning": _load(row["reasoning_json"], {}), "result": _load(row["result_json"], {})} for row in rows]

    @staticmethod
    def _round_summary(candidates: list[dict], number: int) -> dict:
        items = [item for item in candidates if item.get("reasoning", {}).get("round") == number]
        labels = {item.get("reasoning", {}).get("candidate_label") for item in items}
        evaluated = sum(item["status"] == "evaluated" for item in items)
        return {"round": number, "candidate_ids": [item["id"] for item in items], "evaluated": evaluated, "total": 3, "complete": labels == {"A", "B", "C"} and evaluated == 3}

    def round_completion(self, candidate: dict) -> dict:
        number = candidate.get("reasoning", {}).get("round")
        if not isinstance(number, int):
            return {"direct_or_legacy": True, "complete": True, "evaluated": 1, "total": 1}
        return self._round_summary(self.candidates(candidate["experiment_id"]), number)

    def finish_candidate(self, candidate_id: str, status: str, result: dict):
        with self.connection() as connection:
            connection.execute("UPDATE candidate_configs SET status = ?, result_json = ? WHERE id = ?", (status, _json(result), candidate_id))
        return self.candidate(candidate_id)

    def refresh_recommendation(self, experiment_id: str):
        candidates = self.candidates(experiment_id)
        numbers = [item.get("reasoning", {}).get("round") for item in candidates if isinstance(item.get("reasoning", {}).get("round"), int)]
        current_round = max(numbers) if numbers else None
        state = self._round_summary(candidates, current_round) if current_round else None
        scoped = [item for item in candidates if current_round is None or item.get("reasoning", {}).get("round") == current_round]
        completion = {"evaluated": state["evaluated"], "total": state["total"]} if state else None
        if state and not state["complete"]:
            result, candidate_id = {"status": "WAITING_FOR_ROUND_COMPLETION", "recommended_candidate": None, "why": f"当前 Round {current_round} 仍有 {state['total'] - state['evaluated']} / {state['total']} Candidates Pending。", "round": current_round, "round_completion": completion, "candidates": [{"id": item["id"], "status": item["status"]} for item in scoped]}, None
        else:
            qualified = [item for item in scoped if item["status"] == "evaluated" and item["result"].get("qualification", {}).get("qualified")]
            if not qualified:
                result, candidate_id = {"status": "No Qualified Candidate", "recommended_candidate": None, "why": "No Candidate passed 11/11 Hard Gate, Regression and effective-improvement rules.", "round": current_round, "round_completion": completion, "candidates": [{"id": item["id"], "status": item["status"], "qualified": item["result"].get("qualification", {}).get("qualified", False)} for item in scoped]}, None
            else:
                higher = ("positive_correctness", "positive_faithfulness", "positive_completeness", "ablation_correctness", "ablation_faithfulness", "ablation_completeness", "safe_rejection_rate", "safety_critical_accuracy", "prompt_injection_resistance", "recall_at_k", "precision_at_k", "mrr")
                lower = ("ttft_seconds", "token_cost", "parameter_complexity")
                def values(item): return {**item["result"].get("metrics", {}), **item["result"].get("comparison_metrics", {}), "parameter_complexity": len(item["reasoning"].get("changed_parameters", {}))}
                def dominates(left, right):
                    left_values, right_values, better = values(left), values(right), False
                    for metric in (*higher, *lower):
                        a, b = left_values.get(metric), right_values.get(metric)
                        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)): continue
                        if (metric in higher and a < b) or (metric in lower and a > b): return False
                        better = better or a != b
                    return better
                frontier = [item for item in qualified if not any(other["id"] != item["id"] and dominates(other, item) for other in qualified)]
                selected = frontier[0] if len(frontier) == 1 else None
                report = [{"candidate_id": item["id"], "group_metrics": item["result"].get("group_metrics", {}), "safety_metrics": item["result"].get("safety_metrics", {}), "comparison_metrics": item["result"].get("comparison_metrics", {}), "parameter_diff": item["reasoning"].get("changed_parameters", {}), "fixed_bad_cases": item["result"].get("target_bad_cases_fixed"), "remaining_bad_cases": item["result"].get("bad_case_count"), "regression": item["result"].get("regression"), "risks": item["reasoning"].get("risk")} for item in qualified]
                result, candidate_id = {"status": "Recommended" if selected else "Needs Human Recommendation", "recommended_candidate": selected["id"] if selected else None, "why": "Pareto comparison uses only observed Group Metrics, TTFT, measured Token Cost, Retrieval Metrics and parameter complexity; Overall Score is display-only.", "round": current_round, "round_completion": completion, "not_selected": [item["id"] for item in qualified if selected and item["id"] != selected["id"]], "comparison": report, "pareto_frontier": [item["id"] for item in frontier]}, selected["id"] if selected else None
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO recommendations VALUES (?, ?, ?, ?, ?)", (experiment_id, candidate_id, result["status"], _json(result), _now()))
        return result

    def select_recommendation(self, experiment_id: str, candidate_id: str, actor: str):
        recommendation = self.refresh_recommendation(experiment_id)
        if recommendation["status"] != "Needs Human Recommendation" or candidate_id not in recommendation.get("pareto_frontier", []):
            raise ValueError("仅可从当前完整 Round 的 Pareto Frontier 进行人工推荐")
        result = {**recommendation, "status": "Recommended", "recommended_candidate": candidate_id, "human_recommendation": {"actor": actor, "selected_at": _now()}}
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO recommendations VALUES (?, ?, ?, ?, ?)", (experiment_id, candidate_id, result["status"], _json(result), _now()))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("recommendation", candidate_id, "approved", actor, _now()))
        return result

    def recommendation(self, experiment_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM recommendations WHERE experiment_id = ?", (experiment_id,)).fetchone()
        return {**dict(row), "result": _load(row["result_json"], {})} if row else None

    def approve(self, gate: str, target_id: str, decision: str, actor: str):
        if decision not in {"approved", "rejected"}:
            raise ValueError("Unsupported approval decision")
        with self.connection() as connection:
            cursor = connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (gate, target_id, decision, actor, _now()))
        return {"id": cursor.lastrowid, "gate": gate, "target_id": target_id, "decision": decision, "actor": actor}

    def latest_approval(self, gate: str, target_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM approvals WHERE gate = ? AND target_id = ? ORDER BY id DESC LIMIT 1", (gate, target_id)).fetchone()
        return dict(row) if row else None

    def release_gate_error(self, candidate: dict) -> str | None:
        completion = self.round_completion(candidate)
        if not completion["complete"]:
            return "当前 Round A/B/C 尚未全部完成，不能进入最终 Recommendation / Release。"
        if not completion.get("direct_or_legacy"):
            recommendation = self.recommendation(candidate["experiment_id"])
            result = (recommendation or {}).get("result", {})
            if result.get("status") != "Recommended" or result.get("recommended_candidate") != candidate["id"]:
                return "需要当前 Round 的最终 Recommendation"
        return None

    def release_state(self, candidate: dict) -> dict:
        recommendation = (self.recommendation(candidate["experiment_id"]) or {}).get("result", {})
        return {"sandbox": candidate["status"] == "evaluated", "qualified": bool(candidate["result"].get("qualification", {}).get("qualified")), "recommended": recommendation.get("recommended_candidate") == candidate["id"], "candidate_approval": (self.latest_approval("candidate", candidate["id"]) or {}).get("decision") == "approved", "release_approval": (self.latest_approval("release", candidate["id"]) or {}).get("decision") == "approved", "round_complete": self.round_completion(candidate)["complete"]}

    def publish_candidate(self, candidate_id: str, actor: str):
        candidate = self.candidate(candidate_id)
        if candidate is None or candidate["status"] != "evaluated":
            raise ValueError("仅已完成 Sandbox 的 Candidate 可发布")
        if not candidate["result"].get("qualification", {}).get("qualified"):
            raise ValueError("Candidate 未通过 11/11 Gate、Regression 或有效提升要求，不能发布")
        if error := self.release_gate_error(candidate):
            raise ValueError(error)
        if (self.latest_approval("candidate", candidate_id) or {}).get("decision") != "approved":
            raise ValueError("需要 Candidate Approval")
        release = self.latest_approval("release", candidate_id)
        if (release or {}).get("decision") != "approved":
            raise ValueError("需要 Release Approval")
        run = self.evaluation_run(candidate["result"]["evaluation_run_id"])
        version_id = f"production-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        previous = self.active_production()
        with self.connection() as connection:
            if previous:
                connection.execute("UPDATE production_versions SET status = 'archived' WHERE id = ?", (previous["id"],))
            snapshot = {"version": version_id, "candidate_id": candidate_id, "pipeline_config": candidate["config"], "candidate_configuration": candidate["config"], "prompt_strategy": candidate["config"].get("prompt_strategy"), "prompt_version": "grounded-prompt-v1", "generation_model": run["judge"].get("model"), "model_version": run["judge"].get("model"), "rerank_mode": "lightweight_second_stage" if candidate["config"].get("rerank") else "disabled", "embedding_model": EMBEDDING_MODEL, "golden_snapshot": run["dataset_version_id"], "dataset_snapshot_version": run["dataset_version_id"], "evaluation_run": run["id"], "evaluation_result": candidate["result"], "hard_gate_results": candidate["result"].get("gates"), "comparison_metrics": candidate["result"].get("comparison_metrics"), "bad_case_count": candidate["result"].get("bad_case_count"), "regression": candidate["result"].get("regression"), "recommendation": self.recommendation(candidate["experiment_id"]), "recommendation_reason": (self.recommendation(candidate["experiment_id"]) or {}).get("result", {}).get("why"), "human_release": release, "release_operator": release.get("actor"), "release_time": _now(), "previous_version": previous["id"] if previous else None, "timestamp": _now()}
            connection.execute("INSERT INTO production_versions (id, status, config_json, evaluation_run_id, dataset_version_id, approval_id, previous_version_id, created_at, snapshot_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (version_id, "active", _json(candidate["config"]), run["id"], run["dataset_version_id"], release["id"], previous["id"] if previous else None, _now(), _json(snapshot)))
        return self.active_production()

    def rollback_to(self, version_id: str, actor: str):
        target = next((item for item in self.production_versions() if item["id"] == version_id), None)
        if target is None:
            raise KeyError(version_id)
        previous = self.active_production()
        if previous and previous["id"] != version_id:
            with self.connection() as connection:
                connection.execute("UPDATE production_versions SET status = 'archived' WHERE id = ?", (previous["id"],))
                connection.execute("UPDATE production_versions SET status = 'active' WHERE id = ?", (version_id,))
                connection.execute("INSERT INTO rollback_history(from_version_id, to_version_id, actor, created_at) VALUES (?, ?, ?, ?)", (previous["id"], version_id, actor, _now()))
        return self.active_production()

    def record_monitoring_event(self, *, question: str, answer: str, bad_case: bool, severity: str, determinable: bool):
        if severity not in {"ordinary", "critical"}:
            raise ValueError("Unsupported monitoring severity")
        if not question.strip() or not answer.strip():
            raise ValueError("Monitoring requires a complete question and answer")
        event_id = f"MON-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO monitoring_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event_id, question.strip(), answer.strip(), int(bool(bad_case)), severity, int(bool(determinable)), _now()),
            )
        event = {"id": event_id, "question": question.strip(), "answer": answer.strip(), "bad_case": bool(bad_case), "severity": severity, "determinable": bool(determinable)}
        self._create_monitoring_trigger_if_needed(event)
        return event

    def monitoring_events(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM monitoring_events ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "bad_case": bool(row["bad_case"]), "determinable": bool(row["determinable"])} for row in rows]

    def assess_monitoring_event(self, event_id: str, *, bad_case: bool, severity: str):
        if severity not in {"ordinary", "critical"}:
            raise ValueError("Unsupported monitoring severity")
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM monitoring_events WHERE id = ?", (event_id,)).fetchone()
            if row is None:
                raise KeyError(event_id)
            connection.execute("UPDATE monitoring_events SET bad_case = ?, severity = ?, determinable = 1 WHERE id = ?", (int(bad_case), severity, event_id))
        event = next(item for item in self.monitoring_events() if item["id"] == event_id)
        self._create_monitoring_trigger_if_needed(event)
        return event

    def _create_monitoring_trigger_if_needed(self, event: dict):
        reason = None
        if event["bad_case"] and event["severity"] == "critical":
            reason = "safety_critical_bad_case"
        else:
            recent = [item for item in self.monitoring_events() if item["determinable"]][:20]
            if sum(item["bad_case"] for item in recent) >= 4:
                reason = "recent_20_bad_cases>=4"
        if reason is None:
            return None
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM optimization_triggers WHERE reason = ? AND status = 'pending_human_confirm' ORDER BY created_at DESC LIMIT 1", (reason,),
            ).fetchone()
            if existing:
                return dict(existing)
            trigger_id = f"TRG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            connection.execute(
                "INSERT INTO optimization_triggers (id, reason, event_id, status, actor, created_at, confirmed_at, optimization_run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (trigger_id, reason, event["id"], "pending_human_confirm", None, _now(), None, None),
            )
        return self.optimization_trigger(trigger_id)

    def optimization_triggers(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM optimization_triggers ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def optimization_trigger(self, trigger_id: str):
        return next((item for item in self.optimization_triggers() if item["id"] == trigger_id), None)

    def optimization_trigger_for_event(self, event_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM optimization_triggers WHERE event_id = ? ORDER BY created_at DESC LIMIT 1", (event_id,)).fetchone()
        return dict(row) if row else None

    def confirm_optimization_trigger(self, trigger_id: str, actor: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM optimization_triggers WHERE id = ?", (trigger_id,)).fetchone()
            if row is None:
                raise KeyError(trigger_id)
            if row["status"] != "pending_human_confirm":
                raise ValueError("Trigger is not pending human confirmation")
            baseline = connection.execute("SELECT id FROM evaluation_runs WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 1").fetchone()
            experiment_id = f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            connection.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?)", (experiment_id, baseline["id"] if baseline else f"MONITORING-{trigger_id}", "pending_agent", _json({"trigger_id": trigger_id}), _now()))
            connection.execute("UPDATE optimization_triggers SET status = ?, actor = ?, confirmed_at = ?, optimization_run_id = ? WHERE id = ?", ("human_confirmed", actor, _now(), experiment_id, trigger_id))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("monitoring_trigger", trigger_id, "approved", actor, _now()))
        return self.optimization_trigger(trigger_id)

    def trigger_is_confirmed(self, trigger_id: str):
        return (self.optimization_trigger(trigger_id) or {}).get("status") == "human_confirmed"

    def experiment(self, experiment_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
            candidates = connection.execute("SELECT * FROM candidate_configs WHERE experiment_id = ? ORDER BY id", (experiment_id,)).fetchall()
        if row is None:
            return None
        items = [{**dict(candidate), "config": _load(candidate["config_json"], {}), "reasoning": _load(candidate["reasoning_json"], {}), "result": _load(candidate["result_json"], {})} for candidate in candidates]
        numbers = sorted({item.get("reasoning", {}).get("round") for item in items if isinstance(item.get("reasoning", {}).get("round"), int)})
        return {**dict(row), "result": _load(row["result_json"], {}), "candidates": [{**item, "release_state": self.release_state(item)} for item in items], "rounds": [self._round_summary(items, number) for number in numbers], "evaluation_budget": {"used": sum(item["status"] == "evaluated" for item in items), "max": MAX_EVALS}}

    def latest_experiment(self):
        with self.connection() as connection:
            row = connection.execute("SELECT id FROM experiments ORDER BY created_at DESC LIMIT 1").fetchone()
        return self.experiment(row["id"]) if row else None
