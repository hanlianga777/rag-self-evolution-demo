"""SQLite-backed Golden Dataset governance for the local RAG demo."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "demo.db"
GOLDEN_DRAFT = ROOT / "reports" / "golden_dataset_full_draft.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value, fallback):
    try:
        return json.loads(value) if value else fallback
    except json.JSONDecodeError:
        return fallback


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
                    probe_status TEXT NOT NULL, question TEXT NOT NULL, reference_answer TEXT,
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
                        "INSERT OR IGNORE INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            item["id"], "candidate", legacy_type, category, subtype, "human_review_pending", "probe_pending",
                            item["question"], item.get("reference_answer"), _json(item.get("acceptable_evidence", [])), _json(item), now, now,
                        ),
                    )
                connection.execute(
                    "INSERT OR IGNORE INTO dataset_versions VALUES (?, ?, ?, ?, ?)",
                    ("GD-candidate-v1", "candidate", "golden_dataset_full_draft.json", _json({"question_ids": [item["id"] for item in draft.get("cases", [])]}), now),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO production_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("baseline-v1", "active", _json({"top_k": 4, "min_score": None}), None, None, None, None, now),
                )
                connection.execute("INSERT INTO schema_migrations VALUES (?, ?)", ("golden-draft-v1", now))
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

    def review_question(self, question_id: str, decision: str, actor: str):
        if decision not in {"approved", "rejected", "needs_revision"}:
            raise ValueError("Unsupported review decision")
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
            connection.execute("UPDATE questions SET stage = ?, review_status = ?, probe_status = ?, question = ?, reference_answer = ?, evidence_json = ?, raw_json = ?, updated_at = ? WHERE id = ?", ("candidate", "human_review_pending", "probe_pending", question, reference_answer, _json(evidence), _json(raw), _now(), question_id))
            connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (question_id, "dataset", "invalidated", actor, _now()))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, "invalidated", actor, _now()))
        return self.question(question_id)

    def create_dataset_snapshot(self):
        approved = self.questions("golden")
        snapshot = {"question_ids": [item["id"] for item in approved], "questions": [item["raw"] for item in approved]}
        version_id = f"GD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        with self.connection() as connection:
            connection.execute("INSERT INTO dataset_versions VALUES (?, ?, ?, ?, ?)", (version_id, "approved", "human_review", _json(snapshot), _now()))
        return {"id": version_id, **snapshot}

    def run_probe(self, question_id: str, retriever, chunks: list[dict], thresholds=None):
        item = self.question(question_id)
        thresholds = thresholds or {"high": 0.65, "medium": 0.35}
        evidence = item["evidence"]
        expected_chunks = {chunk_id for source in evidence for chunk_id in source.get("source_chunk_ids", [])}
        available_chunks = {chunk.get("chunk_id") for chunk in chunks}
        positive = item["test_category"] == "positive"
        programmatic = {
            "question": bool(item["question"].strip()),
            "reference_answer": bool(item["reference_answer"] or not positive),
            "evidence": bool(evidence),
            "source_chunks": expected_chunks.issubset(available_chunks),
        }
        hits = retriever.search(item["question"], limit=4)
        best = max((hit.get("score", 0) for hit in hits), default=0)
        signal = "high" if best >= thresholds["high"] else "medium" if best >= thresholds["medium"] else "low"
        haystack = " ".join(chunk.get("text", chunk.get("chunk_text", "")) for chunk in chunks)
        phrases = [point for source in evidence for point in source.get("evidence_key_points", [])]
        full_text = {"matched": any(phrase and phrase in haystack for phrase in phrases), "phrases": phrases}
        result = {"question_id": question_id, "programmatic": {"checks": programmatic, "passed": all(programmatic.values())}, "vector": {"top_k": hits, "best_similarity": best, "signal": signal, "thresholds": thresholds}, "full_text": full_text}
        status = "probe_passed" if result["programmatic"]["passed"] else "needs_revision"
        with self.connection() as connection:
            connection.execute("INSERT INTO probe_results(question_id, result_json, created_at) VALUES (?, ?, ?)", (question_id, _json(result), _now()))
            connection.execute("UPDATE questions SET probe_status = ?, updated_at = ? WHERE id = ?", (status, _now(), question_id))
        return result

    def record_qc(self, question_id: str, result: dict, status: str):
        self.question(question_id)
        with self.connection() as connection:
            connection.execute("INSERT INTO qc_results(question_id, status, result_json, created_at) VALUES (?, ?, ?, ?)", (question_id, status, _json(result), _now()))
        return {"question_id": question_id, "status": status, "result": result}

    def qc_history(self, question_id: str):
        with self.connection() as connection:
            rows = connection.execute("SELECT status, result_json, created_at FROM qc_results WHERE question_id = ? ORDER BY id DESC", (question_id,)).fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {})} for row in rows]

    def production_versions(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM production_versions ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "config": _load(row["config_json"], {})} for row in rows]

    def active_production(self):
        return next((item for item in self.production_versions() if item["status"] == "active"), None)

    def evaluation_runs(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM evaluation_runs ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {}), "config": _load(row["config_json"], {})} for row in rows]

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

    def create_experiment(self, baseline_run_id: str):
        experiment_id = f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        with self.connection() as connection:
            connection.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?)", (experiment_id, baseline_run_id, "analyzing", _json({}), _now()))
        return experiment_id

    def save_agent_trace(self, experiment_id: str, status: str, result: dict, error_message: str | None = None):
        with self.connection() as connection:
            connection.execute("INSERT INTO agent_traces(experiment_id, status, result_json, error_message, created_at) VALUES (?, ?, ?, ?, ?)", (experiment_id, status, _json(result), error_message, _now()))
            connection.execute("UPDATE experiments SET status = ?, result_json = ? WHERE id = ?", (status, _json(result), experiment_id))

    def save_candidate(self, experiment_id: str, candidate_id: str, config: dict, reasoning: dict):
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO candidate_configs VALUES (?, ?, ?, ?, ?, ?, ?)", (f"{experiment_id}-{candidate_id}", experiment_id, "generated", _json(config), _json(reasoning), _json({}), _now()))

    def candidate(self, candidate_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM candidate_configs WHERE id = ?", (candidate_id,)).fetchone()
        if row is None:
            return None
        return {**dict(row), "config": _load(row["config_json"], {}), "reasoning": _load(row["reasoning_json"], {}), "result": _load(row["result_json"], {})}

    def finish_candidate(self, candidate_id: str, status: str, result: dict):
        with self.connection() as connection:
            connection.execute("UPDATE candidate_configs SET status = ?, result_json = ? WHERE id = ?", (status, _json(result), candidate_id))
        return self.candidate(candidate_id)

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

    def publish_candidate(self, candidate_id: str, actor: str):
        candidate = self.candidate(candidate_id)
        if candidate is None or candidate["status"] != "evaluated":
            raise ValueError("仅已完成 Sandbox 的 Candidate 可发布")
        if not candidate["result"].get("redline_pass"):
            raise ValueError("红线未通过，不能发布")
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
            connection.execute("INSERT INTO production_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (version_id, "active", _json(candidate["config"]), run["id"], run["dataset_version_id"], release["id"], previous["id"] if previous else None, _now()))
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

    def experiment(self, experiment_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
            candidates = connection.execute("SELECT * FROM candidate_configs WHERE experiment_id = ? ORDER BY id", (experiment_id,)).fetchall()
        if row is None:
            return None
        return {**dict(row), "result": _load(row["result_json"], {}), "candidates": [{**dict(candidate), "config": _load(candidate["config_json"], {}), "reasoning": _load(candidate["reasoning_json"], {})} for candidate in candidates]}
