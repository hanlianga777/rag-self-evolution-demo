"""SQLite-backed Golden Dataset governance for the local RAG demo."""

from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS
from .corpus import EMBEDDING_MODEL, current_manifest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "demo.db"
GOLDEN_DRAFT = ROOT / "reports" / "golden_dataset_full_draft.json"
GENERATION_PROFILES = {
    "mini": {"positive_count": 8, "ablation_count": 4, "negative_count": 8, "expected_count": 20},
    "medium": {"positive_count": 20, "ablation_count": 9, "negative_count": 20, "expected_count": 49},
    "full": {"positive_count": 40, "ablation_count": 18, "negative_count": 40, "expected_count": 98},
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


def profile_count(profile: dict, category: str) -> int:
    """Read V1.3 counts while retaining old Mini run metadata."""
    return profile.get(f"{category}_count", profile.get(category, 0))


def _normalized(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _answer_anchor_supported(answer: str, evidence_texts: list[str]) -> bool:
    texts = [_normalized(text) for text in evidence_texts]
    whole = _normalized(answer)
    if not whole or not texts:
        return False

    def strict_matches(fact: str, original: str) -> bool:
        tokens = {_normalized(token) for token in re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", original)}
        return all(_normalized(token) in tokens for token in re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", fact))

    if any(whole in text and strict_matches(answer, original) for original, text in zip(evidence_texts, texts)):
        return True

    facts = [part.strip() for part in re.split(r"[。；;，,、\n]+", answer) if len(_normalized(part)) >= 3 or any(character.isdigit() for character in part)]
    if not facts:
        return False

    def supported(raw_fact: str, original: str, text: str) -> bool:
        fact = _normalized(raw_fact)
        if not strict_matches(raw_fact, original):
            return False
        if len(fact) >= 3 and fact in text:
            return True
        strict = re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", raw_fact)
        chinese = "".join(character for character in fact if "\u4e00" <= character <= "\u9fff")
        source_chinese = "".join(character for character in original if "\u4e00" <= character <= "\u9fff")
        pairs = {chinese[index:index + 2] for index in range(len(chinese) - 1)}
        if pairs and sum(pair in source_chinese for pair in pairs) / len(pairs) < .75:
            return False
        if not strict and not any(chinese[index:index + 4] in source_chinese for index in range(max(0, len(chinese) - 3))):
            return False
        for start in (index for index, character in enumerate(text) if character == fact[0]):
            position = start
            for character in fact[1:]:
                position = text.find(character, position + 1, position + 10)
                if position < 0:
                    break
            else:
                return True
        return False

    return all(any(supported(fact, original, text) for original, text in zip(evidence_texts, texts)) for fact in facts)


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
            review_columns = {row[1] for row in connection.execute("PRAGMA table_info(review_events)")}
            if "metadata_json" not in review_columns:
                connection.execute("ALTER TABLE review_events ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
            connection.execute("CREATE TABLE IF NOT EXISTS candidate_revision_runs (id TEXT PRIMARY KEY, generation_run_id TEXT NOT NULL, status TEXT NOT NULL, audit_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'v101-provenance-boundary'").fetchone():
                connection.execute("UPDATE questions SET stage = 'candidate', review_status = 'human_review_pending', probe_status = 'probe_pending', qc_status = 'qc_pending', updated_at = ? WHERE stage = 'golden' AND raw_json NOT LIKE '%\"generation_profile\": \"v1-mini-8-4-8\"%'", (_now(),))
                connection.execute("UPDATE dataset_versions SET status = 'legacy_unverified' WHERE status = 'approved' AND snapshot_json NOT LIKE '%\"generation_profile\": \"v1-mini-8-4-8\"%'")
                connection.execute("UPDATE evaluation_runs SET status = 'legacy_unverified' WHERE result_json NOT LIKE '%\"gates\"%'")
                connection.execute("UPDATE production_versions SET config_json = ? WHERE id = 'baseline-v1'", (_json(DEFAULT_PIPELINE_CONFIG),))
                connection.execute("INSERT INTO schema_migrations VALUES (?, ?)", ("v101-provenance-boundary", _now()))
            if "metrics_json" not in {row[1] for row in connection.execute("PRAGMA table_info(monitoring_events)")}:
                connection.execute("ALTER TABLE monitoring_events ADD COLUMN metrics_json TEXT")
            connection.execute("INSERT OR IGNORE INTO schema_migrations VALUES (?, ?)", ("phase1-monitoring-metrics", _now()))
            if "source_json" not in {row[1] for row in connection.execute("PRAGMA table_info(monitoring_events)")}:
                connection.execute("ALTER TABLE monitoring_events ADD COLUMN source_json TEXT")
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

    def save_business_candidates(self, candidates: list[dict], filename: str, file_hash: str):
        now, ids = _now(), []
        prefix = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = {_normalized(row[0]) for row in connection.execute("SELECT question FROM questions")}
            for index, candidate in enumerate(candidates):
                key = _normalized(candidate['question'])
                if key in existing:
                    raise ValueError('重复题目，请重新预览')
                existing.add(key)
                question_id = f"BUS-{prefix}-{index:03d}"
                raw = {**candidate, 'id': question_id, 'source': 'business_import', 'import_audit': {'filename': filename, 'sha256': file_hash, 'row': candidate['import_row'], 'imported_at': now}}
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (question_id, 'candidate', 'v1_mini', candidate['test_category'], candidate.get('negative_subtype'), 'human_review_pending', 'probe_pending', 'qc_pending', candidate['question'], candidate.get('reference_answer'), _json(candidate.get('evidence', [])), _json(raw), now, now))
                ids.append(question_id)
        return ids

    def create_pool_run(self, profile_name: str, question_ids: list[str], chunks: list[dict]):
        from .ai_service import AiService
        from .business_import import construction_errors
        from .corpus import current_manifest
        if profile_name not in GENERATION_PROFILES:
            raise ValueError('不支持的 Profile')
        profile = {'name': profile_name, **GENERATION_PROFILES[profile_name]}
        if len(question_ids) != profile['expected_count'] or len(set(question_ids)) != len(question_ids):
            raise ValueError('需选择完整配额，且不可重复选择')
        run_id, now = f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", _now()
        clones, plan, seen = [], [], set()
        known = {item['chunk_id']: item for item in chunks}
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if connection.execute("SELECT 1 FROM golden_generation_runs WHERE status IN ('queued','coverage','generating','validation','probing','qc')").fetchone():
                raise ValueError('已有 Run 正在执行')
            originals = []
            for question_id in question_ids:
                row = connection.execute('SELECT * FROM questions WHERE id=?', (question_id,)).fetchone()
                if row is None or row['stage'] == 'superseded':
                    raise ValueError('候选题不存在或已被替代')
                originals.append(self._row(row))
            counts = {group: sum(item['test_category'] == group for item in originals) for group in ('positive', 'ablation', 'negative')}
            if any(counts[group] != profile_count(profile, group) for group in counts):
                raise ValueError('Evaluation Group 配额不匹配')
            for index, item in enumerate(originals, 1):
                candidate = {**item['raw'], **item}
                errors = AiService._candidate_errors(candidate, chunks, seen)
                source_ids = {key for evidence in item['evidence'] for key in evidence.get('source_chunk_ids', [])}
                errors += construction_errors(item['raw'].get('construction_type'), item['reference_answer'] or '', [known[key] for key in source_ids if key in known])
                if errors:
                    raise ValueError(f"{item['id']}: {'; '.join(errors)}")
                seen.add(''.join(item['question'].lower().split()))
                new_id, slot = f"V1G-{run_id[-12:]}-{index:02d}", f"Q{index:02d}"
                raw = {**item['raw'], 'id': new_id, 'source': item['raw'].get('source', 'ai_generated'), 'source_reference': {'question_id': item['id'], 'generation_run_id': item['raw'].get('generation_run_id')}, 'generation_run_id': run_id, 'generation_profile': 'v1-mini-8-4-8' if profile_name == 'mini' else f'v1.3-{profile_name}', 'coverage_slot': slot}
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (new_id, 'candidate', 'v1_mini', item['test_category'], item['negative_subtype'], 'human_review_pending', 'probe_pending', 'qc_pending', item['question'], item['reference_answer'], _json(item['evidence']), _json(raw), now, now))
                clones.append(new_id)
                plan.append({'question_id': new_id, 'coverage_slot': slot, 'test_category': item['test_category'], 'negative_subtype': item['negative_subtype'], 'ablation_attribute': raw.get('ablation_attribute')})
            connection.execute('INSERT INTO golden_generation_runs VALUES (?, ?, ?, ?, ?, ?)', (run_id, _json(profile), 'pool_selection', 'completed', _json(clones), now))
            audit = {'slot_persistence_v1': True, 'source': 'mixed_pool', 'corpus_fingerprint': current_manifest()['sources'], 'status': 'passed', 'counts': counts, 'hard_validation': {'status': 'passed', 'rejected': []}, 'progress': {'stage': 'quality_not_run', 'completed_slots': len(clones), 'total_slots': len(clones), 'probe_completed': 0, 'qc_completed': 0}, 'source_question_ids': question_ids}
            connection.execute('INSERT INTO golden_generation_artifacts VALUES (?, ?, ?, ?)', (run_id, _json([]), _json(plan), _json(audit)))
        return self.generation_run(run_id)

    def require_generation_ready(self, question_id: str):
        item = self.question(question_id)
        run_id = item["raw"].get("generation_run_id")
        run = self.generation_run(run_id) if run_id else None
        if run and run["artifacts"]["hard_validation"].get("slot_persistence_v1") and run["status"] != "completed":
            raise ValueError("本轮测试集与 Probe / QC 尚未完成，部分 Candidate 仅可查看")

    def dataset_summary(self):
        runs = [run for run in self.generation_runs() if run["artifacts"]["hard_validation"].get("slot_persistence_v1") or run["status"] == "completed" and len(run["question_ids"]) == self._expected_count(run)]
        current = runs[0] if runs else None
        rows = [self.question(question_id) for question_id in current["question_ids"]] if current else []
        all_questions = self.questions()
        return {
            "generation_run_id": current["id"] if current else None,
            "total": len(rows),
            "expected_count": self._expected_count(current) if current else 0,
            "generation_status": current["status"] if current else None,
            "positive": sum(row["test_category"] == "positive" for row in rows),
            "negative": sum(row["test_category"] == "negative" for row in rows),
            "ablation": sum(row["test_category"] == "ablation" for row in rows),
            "approved": sum(row["stage"] == "golden" for row in rows),
            "pending_review": sum(row["review_status"] == "human_review_pending" for row in rows),
            "needs_revision": sum(row["review_status"] == "needs_revision" for row in rows),
            "legacy_total": sum(row["raw"].get("generation_run_id") is None for row in all_questions),
            "historical_run_total": sum(row["raw"].get("generation_run_id") not in {None, current["id"] if current else None} for row in all_questions),
        }

    @staticmethod
    def _expected_count(run: dict) -> int:
        profile = run.get("profile") or {}
        return profile.get("expected_count") or sum(profile_count(profile, category) for category in ("positive", "ablation", "negative"))

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

    def start_generation_run(self, model_version: str, profile_name: str = "mini"):
        from .corpus import current_manifest
        if profile_name not in GENERATION_PROFILES:
            raise ValueError("Unknown Golden profile")
        profile = {"name": profile_name, **GENERATION_PROFILES[profile_name]}
        run_id, now = f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", _now()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pending = connection.execute("SELECT profile_json FROM golden_generation_runs WHERE status = 'needs_regeneration' LIMIT 1").fetchone()
            if pending:
                old_mini = _load(pending["profile_json"], {}).get("name", "mini") == "mini"
                raise ValueError("当前 V1 Mini 尚有失败 Slot 待补齐，请先完成当前 Run。" if old_mini else "当前测试集尚有失败 Slot 待补齐，请先完成当前 Run。")
            if connection.execute("SELECT 1 FROM golden_generation_runs WHERE status IN ('queued', 'coverage', 'generating', 'validation', 'probing', 'qc') LIMIT 1").fetchone():
                raise ValueError("已有 Generation Run 正在执行")
            connection.execute("INSERT INTO golden_generation_runs VALUES (?, ?, ?, ?, ?, ?)", (run_id, _json(profile), model_version, "queued", _json([]), now))
            connection.execute("INSERT INTO golden_generation_artifacts VALUES (?, ?, ?, ?)", (run_id, _json([]), _json([]), _json({"slot_persistence_v1": True, "corpus_fingerprint": current_manifest()["sources"], "progress": {"stage": "queued", "completed_slots": 0, "total_slots": profile["expected_count"], "phase_processed": 0, "phase_total": profile["expected_count"], "processed_slot_ids": [], "probe_completed": 0, "qc_completed": 0, "started_at": now, "operation_id": run_id}})))
        return run_id

    def claim_regeneration(self, run_id: str, corpus_fingerprint):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.status, r.profile_json, r.question_ids_json, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            audit = _load(row["hard_validation_json"], {})
            if not audit.get("slot_persistence_v1") or row["status"] != "needs_regeneration":
                raise ValueError("仅待补题的新 Run 可以局部补题")
            if audit.get("corpus_fingerprint") != corpus_fingerprint:
                raise ValueError("Corpus 已变化，请创建新的 Generation Run")
            remaining = self._expected_count({"profile": _load(row["profile_json"], {})}) - len(_load(row["question_ids_json"], []))
            prior_progress = audit.get("progress", {})
            audit["progress"] = {**prior_progress, "stage": "generating", "phase_processed": 0, "phase_total": remaining, "processed_slot_ids": prior_progress.get("processed_slot_ids", list(audit.get("slot_audit", {}))), "started_at": _now(), "finished_at": None, "operation_id": f"{run_id}-R{audit.get('regeneration_count', 0) + 1}", "refill_round": 1, "refill_max_rounds": 3, "refill_remaining": remaining}
            audit["regeneration_count"] = audit.get("regeneration_count", 0) + 1
            connection.execute("UPDATE golden_generation_runs SET status='generating' WHERE id=?", (run_id,))
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), run_id))

    def persist_generation_attempt(self, run_id: str, candidate: dict | None, slot_audit: dict, *, slot: str, attempt: int, model: str, slot_complete: bool | None = None):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.question_ids_json, a.hard_validation_json, a.question_plan_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            ids, audit, question_plan = _load(row["question_ids_json"], []), _load(row["hard_validation_json"], {}), _load(row["question_plan_json"], [])
            if not audit.get("slot_persistence_v1"):
                raise ValueError("旧 Run 不支持局部写入")
            existing = {entry["coverage_slot"]: entry["question_id"] for entry in question_plan}
            if candidate and slot in existing:
                raise ValueError(f"{slot} 已有活动 Candidate")
            if candidate and any(_load(item["raw_json"], {}).get("coverage_slot") == slot for item in connection.execute("SELECT raw_json FROM questions WHERE legacy_question_type='v1_mini' AND stage!='superseded' AND raw_json LIKE ?", (f'%"generation_run_id": "{run_id}"%',))):
                raise ValueError(f"{slot} 已有活动 Candidate")
            audit["slot_audit"] = slot_audit
            progress = audit.get("progress", {})
            finished = bool(candidate) if slot_complete is None else slot_complete
            processed_ids = progress.get("processed_slot_ids", [])
            if finished and slot not in processed_ids:
                processed_ids = [*processed_ids, slot]
            audit["progress"] = {**progress, "stage": "generating", "slot": slot, "attempt": attempt, "completed_slots": len(ids) + bool(candidate), "processed_slot_ids": processed_ids, "phase_processed": progress.get("phase_processed", 0) + int(finished), "phase_total": progress.get("phase_total", 0)}
            if candidate:
                question_id = f"V1G-{run_id[-12:]}-{int(slot[1:]):02d}"
                now = _now()
                profile = _load(connection.execute("SELECT profile_json FROM golden_generation_runs WHERE id=?", (run_id,)).fetchone()[0], {})
                raw = {"id": question_id, "question": candidate["question"], "reference_answer": candidate.get("reference_answer"), "acceptable_evidence": candidate.get("evidence") or [], "expected_behavior": candidate.get("expected_behavior"), "generation_profile": "v1-mini-8-4-8" if profile.get("name", "mini") == "mini" else f"v1.3-{profile['name']}", "generation_run_id": run_id, "generation_model": model, "ablation_attribute": candidate.get("ablation_attribute"), "ablation_metadata": candidate.get("ablation_metadata", {}), "coverage_slot": slot, "generation_instruction": candidate.get("generation_instruction"), "source_positive_id": None, "source": "ai_generated", "construction_type": candidate.get("construction_type"), "generation_method": candidate.get("generation_method", "provider")}
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (question_id, "candidate", "v1_mini", candidate["test_category"], candidate.get("negative_subtype"), "human_review_pending", "probe_pending", "qc_pending", candidate["question"], candidate.get("reference_answer"), _json(candidate.get("evidence") or []), _json(raw), now, now))
                question_plan.append({"question_id": question_id, "coverage_slot": slot, "test_category": candidate["test_category"], "negative_subtype": candidate.get("negative_subtype"), "ablation_attribute": candidate.get("ablation_attribute")})
                question_plan.sort(key=lambda item: item["coverage_slot"])
                ids = [item["question_id"] for item in question_plan]
                connection.execute("UPDATE golden_generation_runs SET question_ids_json=? WHERE id=?", (_json(ids), run_id))
                connection.execute("UPDATE golden_generation_artifacts SET question_plan_json=? WHERE generation_run_id=?", (_json(question_plan), run_id))
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), run_id))

    def complete_generation_slots(self, run_id: str, *, failed_slots: list[str], hard_validation: dict, continue_refill: bool = False):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.question_ids_json, r.profile_json, a.question_plan_json, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.id=?", (run_id,)).fetchone()
            ids, plan, audit = _load(row["question_ids_json"], []), _load(row["question_plan_json"], []), _load(row["hard_validation_json"], {})
            profile = _load(row["profile_json"], {})
            counts = {category: sum(item["test_category"] == category for item in plan) for category in ("positive", "ablation", "negative")}
            expected = self._expected_count({"profile": profile})
            complete = len(ids) == expected and len(set(ids)) == expected and all(counts[key] == profile_count(profile, key) for key in counts) and not failed_slots and not hard_validation.get("rejected")
            if len(ids) == expected and not complete:
                raise ValueError("Candidate 配额或整轮 Hard Validation 复核失败")
            audit.update({"failed_slots": failed_slots, "status": "passed" if complete else "generating" if continue_refill else "needs_regeneration", "counts": counts, "hard_validation": hard_validation})
            progress = audit.get("progress", {})
            if progress.get("refill_round"):
                audit.setdefault("refill_rounds", []).append({"round": progress["refill_round"], "before": progress.get("phase_total"), "remaining": len(failed_slots), "failed_slots": failed_slots})
            next_status = "probing" if complete else "generating" if continue_refill else "needs_regeneration"
            audit["progress"] = {**progress, "stage": next_status, "completed_slots": len(ids), "finished_at": None if complete or continue_refill else _now(), "refill_remaining": len(failed_slots), **({"refill_round": progress["refill_round"] + 1, "phase_processed": 0, "phase_total": len(failed_slots), "slot": None, "attempt": None} if continue_refill else {})}
            connection.execute("UPDATE golden_generation_runs SET status=? WHERE id=?", (next_status, run_id))
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), run_id))
        return complete

    def update_generation_run(self, run_id: str, *, status: str, progress: dict | None = None, coverage_plan: list[dict] | None = None, validation: dict | None = None):
        with self.connection() as connection:
            row = connection.execute("SELECT coverage_plan_json, hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            audit = _load(row["hard_validation_json"], {})
            audit.update(validation or {})
            if progress:
                audit["progress"] = {**audit.get("progress", {}), **progress}
                if status in {"completed", "failed"}:
                    audit["progress"]["finished_at"] = _now()
            connection.execute("UPDATE golden_generation_runs SET status = ? WHERE id = ?", (status, run_id))
            connection.execute("UPDATE golden_generation_artifacts SET coverage_plan_json = ?, hard_validation_json = ? WHERE generation_run_id = ?", (_json(coverage_plan if coverage_plan is not None else _load(row["coverage_plan_json"], [])), _json(audit), run_id))

    def interrupt_generation_runs(self):
        """A process restart cannot resume daemon workers; preserve their audit and unblock manual retry."""
        with self.connection() as connection:
            rows = connection.execute("SELECT r.id, r.status, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id").fetchall()
            for row in rows:
                audit = _load(row["hard_validation_json"], {})
                changed = False
                if row["status"] in {"queued", "coverage", "generating", "validation", "probing", "qc"}:
                    audit.update({"failed_stage": audit.get("progress", {}).get("stage") or row["status"], "error": "服务重启后生成 Worker 已中断，请手动重新运行", "interrupted_at": _now()})
                    recoverable = audit.get("slot_persistence_v1") and row["status"] in {"coverage", "generating", "validation"}
                    connection.execute("UPDATE golden_generation_runs SET status=? WHERE id=?", ("needs_regeneration" if recoverable else "failed", row["id"]))
                    if audit.get("slot_persistence_v1"):
                        audit["progress"] = {**audit.get("progress", {}), "stage": "needs_regeneration" if recoverable else "failed", "finished_at": _now()}
                    changed = True
                rerun = audit.get("quality_rerun") or {}
                if rerun.get("status") == "running":
                    audit["quality_rerun"] = {**rerun, "status": "failed", "failed_stage": rerun.get("stage"), "error": "服务重启后质量 Worker 已中断，请手动重试", "interrupted_at": _now()}
                    changed = True
                if changed:
                    connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), row["id"]))

    def save_mini_golden_candidates(self, candidates: list[dict], model_version: str, *, coverage_plan: list[dict] | None = None, hard_validation: dict | None = None, slot_audit: dict | None = None, run_id: str | None = None):
        """Persist the V1 Mini profile only as review-pending candidates, never as Golden."""
        expected = GENERATION_PROFILES["mini"]
        actual = {category: sum(item.get("test_category") == category for item in candidates) for category in ("positive", "ablation", "negative")}
        if any(actual[category] != profile_count(expected, category) for category in actual) or len(candidates) != expected["expected_count"]:
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
                source_positive_id = candidate.get("source_positive_id")
                if not source_positive_id and candidate.get("source_positive_slot"):
                    source_positive_id = next((saved_id for saved_id, prior in zip(question_ids, candidates[:serial - 1]) if prior.get("coverage_slot") == candidate["source_positive_slot"] and prior.get("test_category") == "positive"), None)
                raw = {"id": question_id, "question": question, "reference_answer": answer, "acceptable_evidence": evidence, "expected_behavior": expected_behavior, "generation_profile": "v1-mini-8-4-8", "generation_run_id": run_id, "generation_model": model_version, "ablation_attribute": candidate.get("ablation_attribute"), "ablation_metadata": candidate.get("ablation_metadata", {}), "coverage_slot": candidate.get("coverage_slot"), "generation_instruction": candidate.get("generation_instruction"), "source_positive_id": source_positive_id, "source": "ai_generated", "construction_type": candidate.get("construction_type"), "generation_method": candidate.get("generation_method", "provider")}
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (question_id, "candidate", "v1_mini", category, candidate.get("negative_subtype"), "human_review_pending", "probe_pending", "qc_pending", question, answer, _json(evidence), _json(raw), now, now))
                question_ids.append(question_id)
            if existing_run:
                connection.execute("UPDATE golden_generation_runs SET status = 'probing', question_ids_json = ? WHERE id = ?", (_json(question_ids), run_id))
            else:
                connection.execute("INSERT INTO golden_generation_runs VALUES (?, ?, ?, ?, ?, ?)", (run_id, _json(expected), model_version, "candidate_generated", _json(question_ids), now))
            coverage = coverage_plan or [{"test_category": item["test_category"], "source_chunk_ids": [chunk_id for source in item.get("evidence", []) for chunk_id in source.get("source_chunk_ids", [])]} for item in candidates]
            question_plan = [{"question_id": question_id, "test_category": item["test_category"], "negative_subtype": item.get("negative_subtype"), "ablation_attribute": item.get("ablation_attribute"), "coverage_slot": item.get("coverage_slot"), "source_positive_id": item.get("source_positive_id") or next((saved_id for saved_id, prior in zip(question_ids, candidates) if prior.get("coverage_slot") == item.get("source_positive_slot") and prior.get("test_category") == "positive"), None)} for question_id, item in zip(question_ids, candidates)]
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
        return [self.generation_run(row["id"]) for row in rows]

    def generation_run(self, run_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM golden_generation_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        run = {**dict(row), "profile": _load(row["profile_json"], {}), "question_ids": _load(row["question_ids_json"], []), "artifacts": self.generation_artifacts(run_id)}
        audit = run["artifacts"]["hard_validation"]
        if audit.get("slot_persistence_v1"):
            progress = audit.get("progress", {})
            valid, probe, qc = len(run["question_ids"]), progress.get("probe_completed", 0), progress.get("qc_completed", 0) + progress.get("qc_skipped", 0)
            phase = audit.get("failed_stage") if run["status"] == "failed" and audit.get("failed_stage") in {"generating", "validation", "probing", "qc"} else progress.get("stage", run["status"])
            expected = self._expected_count(run)
            processed = len(progress["processed_slot_ids"]) if "processed_slot_ids" in progress else len(audit.get("slot_audit", {})) if run["status"] == "needs_regeneration" else valid
            generation_done = progress.get("phase_processed", processed)
            generation_total = progress.get("phase_total", expected)
            phase_done, phase_total = (probe, expected) if phase == "probing" else (qc, expected) if phase in {"qc", "completed"} else (generation_done, generation_total)
            failed_count = max(0, expected - valid) if run["status"] == "needs_regeneration" else max(0, processed - valid)
            started_at = progress.get("started_at", run["created_at"])
            ended_at = datetime.fromisoformat(progress["finished_at"]) if progress.get("finished_at") else datetime.now(timezone.utc)
            run["operation_progress"] = {"operation_id": progress.get("operation_id", run_id), "status": run["status"], "phase": phase, "phase_label": {"queued": "等待开始", "coverage": "覆盖规划", "generating": "补齐失败题" if audit.get("regeneration_count") else "逐题生成与校验", "validation": "逐题生成与校验", "needs_regeneration": "待补齐失败题", "probing": "Probe", "qc": "QC", "completed": "已完成", "failed": "运行失败"}.get(phase, phase), "completed_units": phase_done, "total_units": phase_total, "phase_processed": phase_done, "phase_total": phase_total, "phase_percent": round(phase_done / phase_total * 100) if phase_total else 0, "overall_percent": round((processed + probe + qc) / (expected * 3) * 100) if expected else 0, "processed_slots": processed, "expected_slots": expected, "hard_valid_completed": valid, "hard_valid_total": expected, "failed_count": failed_count, "refill_round": progress.get("refill_round"), "refill_max_rounds": progress.get("refill_max_rounds"), "refill_remaining": progress.get("refill_remaining"), "probe_processed": probe, "qc_processed": qc, "current_slot": progress.get("slot"), "current_item": progress.get("slot"), "attempt": progress.get("attempt"), "started_at": started_at, "elapsed_ms": max(0, round((ended_at - datetime.fromisoformat(started_at)).total_seconds() * 1000)), "message": progress.get("message"), "error": audit.get("error")}
        return run

    def update_quality_rerun(self, run_id: str, changes: dict, *, start: bool = False):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.status, r.profile_json, r.question_ids_json, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id = r.id WHERE r.id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            ids = _load(row["question_ids_json"], [])
            expected = self._expected_count({"profile": _load(row["profile_json"], {})})
            if not expected or len(ids) != expected or len(set(ids)) != expected or row["status"] != "completed":
                raise ValueError("本轮尚未完整入库 20 道 Candidate")
            marks = ",".join("?" for _ in ids)
            candidates = connection.execute(f"SELECT id, legacy_question_type, raw_json FROM questions WHERE id IN ({marks})", ids).fetchall()
            if len(candidates) != expected or any(item["legacy_question_type"] != "v1_mini" or _load(item["raw_json"], {}).get("generation_run_id") != run_id for item in candidates):
                raise ValueError("本轮 Candidate 归属或数量不一致")
            audit = _load(row["hard_validation_json"], {})
            previous = audit.get("quality_rerun", {})
            if start and previous.get("status") == "running":
                raise ValueError("本轮 Probe / QC 已在运行")
            audit["quality_rerun"] = {**({} if start else previous), **changes}
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json = ? WHERE generation_run_id = ?", (_json(audit), run_id))
        return ids

    def generation_review(self, run_id: str, chunks: list[dict], *, allow_partial: bool = False):
        run = self.generation_run(run_id)
        if run is None:
            raise KeyError(run_id)
        ids = run["question_ids"]
        expected = self._expected_count(run)
        if not expected or (len(ids) != expected and not allow_partial) or len(set(ids)) != len(ids):
            raise ValueError("本轮尚未完整入库 20 道 Candidate")
        if allow_partial and len(ids) != expected and not run["artifacts"]["hard_validation"].get("slot_persistence_v1"):
            raise ValueError("旧 Run 仅支持完整测试集读取")
        if not ids and allow_partial:
            return {"generation_run_id": run_id, "questions": []}
        marks = ",".join("?" for _ in ids)
        with self.connection() as connection:
            rows = {row["id"]: self._row(row) for row in connection.execute(f"SELECT * FROM questions WHERE id IN ({marks})", ids)}
            if len(rows) != len(ids) or any(rows[question_id]["raw"].get("generation_run_id") != run_id or rows[question_id]["legacy_question_type"] != "v1_mini" for question_id in ids):
                raise ValueError("本轮 Candidate 归属或数量不一致")
            probes = {question_id: [] for question_id in ids}
            for row in connection.execute(f"SELECT question_id, result_json, created_at FROM probe_results WHERE question_id IN ({marks}) ORDER BY id DESC", ids):
                probes[row["question_id"]].append({**_load(row["result_json"], {}), "created_at": row["created_at"]})
            qcs = {question_id: [] for question_id in ids}
            for row in connection.execute(f"SELECT question_id, status, result_json, created_at FROM qc_results WHERE question_id IN ({marks}) ORDER BY id DESC", ids):
                qcs[row["question_id"]].append({"status": row["status"], "result": _load(row["result_json"], {}), "created_at": row["created_at"]})
            reviews = {question_id: [] for question_id in ids}
            for row in connection.execute(f"SELECT question_id, gate, decision, actor, created_at, metadata_json FROM review_events WHERE question_id IN ({marks}) ORDER BY id DESC", ids):
                reviews[row["question_id"]].append({**dict(row), **_load(row["metadata_json"], {}), "reviewed_at": row["created_at"]})
        by_chunk = {chunk["chunk_id"]: chunk for chunk in chunks}
        questions = []
        for number, question_id in enumerate(ids, 1):
            item = rows[question_id]
            evidence_details = []
            for evidence in item["evidence"]:
                matched = []
                for chunk_id in evidence.get("source_chunk_ids", []):
                    chunk = by_chunk.get(chunk_id)
                    matched.append({"chunk_id": chunk_id, "resolution": "matched" if chunk else "missing_current_index", "document_id": chunk.get("document_id") if chunk else None, "document_name": chunk.get("document_name") if chunk else None, "section_path": chunk.get("section_path") if chunk else None, "page_start": chunk.get("page_start") if chunk else None, "page_end": chunk.get("page_end") if chunk else None, "chunk_text": chunk.get("chunk_text", chunk.get("text")) if chunk else None})
                evidence_details.append({**evidence, "chunks": matched})
            slot = item["raw"].get("coverage_slot") or f"Q{number:02d}"
            attempts = run["artifacts"].get("slot_audit", {}).get(slot, [])
            questions.append({**item, 'approval_eligibility': self.approval_eligibility(question_id), "slot": slot, "hard_validation_checks": attempts[-1].get("hard_validation_checks") if attempts else None, "evidence_details": evidence_details, "probe": probes[question_id][0] if probes[question_id] and item["probe_status"] != "probe_pending" else None, "qc": qcs[question_id][0]["result"] if qcs[question_id] and item["qc_status"] != "qc_pending" else None, "probe_history": probes[question_id], "qc_history": qcs[question_id], "review_history": reviews[question_id], "revision_history": self.revision_history(question_id)})
        return {"generation_run_id": run_id, "questions": questions}

    def approval_eligibility(self, question_id: str):
        item = self.question(question_id)
        probes, qcs = self.probe_history(question_id), self.qc_history(question_id)
        blockers = []
        generation = self.generation_run(item["raw"].get("generation_run_id")) if item["raw"].get("generation_run_id") else None
        if generation and generation["artifacts"]["hard_validation"].get("slot_persistence_v1") and generation["status"] != "completed":
            blockers.append("本轮测试集与 Probe / QC 尚未完成")
        if item['probe_status'] != 'probe_passed' or not probes or probes[0].get('evidence_direct_failure') or probes[0].get('status') != 'passed':
            blockers.append('Probe 尚未完成或确定性证据 / Negative 检查未通过')
        if item['qc_status'] == 'qc_pending' or not qcs:
            blockers.append('QC 尚未完成')
        if any(question_id in run.get('question_ids', []) for run in self.revision_runs(item['raw'].get('generation_run_id')) if run['status'] in {'queued', 'generating', 'validating', 'preview_ready', 'probing', 'qc', 'interrupted'}):
            blockers.append('局部修订未完成')
        qc = qcs[0]['result'] if qcs else {}
        requires_acceptance = qc.get('priority') == 'P0'
        accepted = any(event.get('decision') == 'approved' and event.get('accept_qc_p0') and (event.get('reason') or '').strip() and event.get('qc_created_at') == qcs[0]['created_at'] for event in self.review_history(question_id)) if qcs else False
        return {'can_approve': not blockers and (not requires_acceptance or accepted), 'blocking_reasons': blockers, 'requires_qc_p0_acceptance': requires_acceptance and not accepted, 'qc_reason': qc.get('reason'), 'qc_created_at': qcs[0]['created_at'] if qcs else None}

    def review_question(self, question_id: str, decision: str, actor: str, *, reason: str | None = None, tags: list[str] | None = None, accept_qc_p0: bool = False):
        if decision not in {"approved", "rejected", "needs_revision"}:
            raise ValueError("Unsupported review decision")
        current = self.question(question_id)
        generation = self.generation_run(current["raw"].get("generation_run_id")) if current["raw"].get("generation_run_id") else None
        if generation and generation["artifacts"]["hard_validation"].get("slot_persistence_v1") and generation["status"] != "completed":
            raise ValueError("本轮测试集与 Probe / QC 尚未完成，不可人工审核")
        if current["stage"] == "golden" and decision != "approved":
            raise ValueError("已批准题目已冻结")
        if decision == "needs_revision" and not (reason or "").strip():
            raise ValueError("需修订时必须填写修订原因")
        if decision == "approved" and any(question_id in run.get("question_ids", []) for run in self.revision_runs(current["raw"].get("generation_run_id")) if run["status"] in {"queued", "generating", "validating", "preview_ready", "probing", "qc", "interrupted"}):
            raise ValueError("局部修订未完成，不能批准")
        status = "approved" if decision == "approved" else decision
        stage = "golden" if decision == "approved" else "candidate"
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if not connection.execute("SELECT 1 FROM questions WHERE id = ?", (question_id,)).fetchone():
                raise KeyError(question_id)
            eligibility = self.approval_eligibility(question_id)
            if decision == 'approved':
                if eligibility['blocking_reasons']:
                    raise ValueError('；'.join(eligibility['blocking_reasons']))
                if eligibility['requires_qc_p0_acceptance'] and not (accept_qc_p0 and (reason or '').strip()):
                    raise ValueError('QC P0 必须明确接受并填写原因')
            connection.execute("UPDATE questions SET stage = ?, review_status = ?, updated_at = ? WHERE id = ?", (stage, status, _now(), question_id))
            connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at, metadata_json) VALUES (?, ?, ?, ?, ?, ?)", (question_id, "dataset", decision, actor, _now(), _json({'reason': (reason or '').strip(), 'tags': tags or [], 'accept_qc_p0': accept_qc_p0, 'qc_created_at': eligibility['qc_created_at']})))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, decision, actor, _now()))
        return self.question(question_id)

    def review_history(self, question_id: str):
        with self.connection() as connection:
            return [{**dict(row), **_load(row["metadata_json"], {}), "reviewed_at": row["created_at"]} for row in connection.execute("SELECT gate, decision, actor, created_at, metadata_json FROM review_events WHERE question_id = ? ORDER BY id DESC", (question_id,))]

    @staticmethod
    def _revision_hash(item: dict) -> str:
        content = {key: item[key] for key in ("stage", "review_status", "question", "reference_answer", "evidence", "raw")}
        return hashlib.sha256(_json(content).encode()).hexdigest()

    def revision_run(self, revision_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM candidate_revision_runs WHERE id = ?", (revision_id,)).fetchone()
        if row is None:
            raise KeyError(revision_id)
        return {**dict(row), **_load(row["audit_json"], {})}

    def revision_runs(self, generation_run_id: str | None = None):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM candidate_revision_runs WHERE generation_run_id = ? ORDER BY created_at DESC", (generation_run_id,)).fetchall() if generation_run_id else connection.execute("SELECT * FROM candidate_revision_runs ORDER BY created_at DESC").fetchall()
        return [{**dict(row), **_load(row["audit_json"], {})} for row in rows]

    def revision_history(self, question_id: str):
        return [run for run in self.revision_runs() if question_id in run.get("question_ids", []) or question_id in run.get('source_question_ids', [])]

    def related_positive(self, item: dict):
        if item["test_category"] != "ablation":
            return None
        run_id = item["raw"].get("generation_run_id")
        generation = self.generation_run(run_id) if run_id else None
        valid_ids = set(generation["question_ids"]) if generation else set()
        positive_id = item["raw"].get("source_positive_id") or item["raw"].get("paired_question_id")
        if not positive_id:
            for revision in self.revision_history(item["id"]):
                positive_id = next((key for key, before in revision.get("before", {}).items() if before["test_category"] == "positive"), None)
                if positive_id:
                    break
        if positive_id not in valid_ids:
            return None
        positive = self.question(positive_id)
        return positive if positive["test_category"] == "positive" else None

    def revision_positive(self, run: dict, drafts: dict | None = None):
        for item in (drafts or {}).values():
            if item["test_category"] == "positive":
                return item
        ablation = next((item for item in run["before"].values() if item["test_category"] == "ablation"), None)
        return self.related_positive(ablation) if ablation else None

    def update_revision(self, revision_id: str, *, status: str | None = None, **changes):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id = ?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            audit = {**_load(row["audit_json"], {}), **changes}
            connection.execute("UPDATE candidate_revision_runs SET status = ?, audit_json = ?, updated_at = ? WHERE id = ?", (status or row["status"], _json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def interrupt_revision_runs(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT id, audit_json FROM candidate_revision_runs WHERE status IN ('queued', 'generating', 'validating', 'probing', 'qc')").fetchall()
            for row in rows:
                audit = {**_load(row["audit_json"], {}), "interrupted_at": _now(), "interrupted_stage": _load(row["audit_json"], {}).get("stage"), "stage": "interrupted"}
                connection.execute("UPDATE candidate_revision_runs SET status='interrupted', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), row["id"]))

    def start_revision(self, question_id: str, mode: str, reason: str, paired: bool, changes_by_id: dict, chunks: list[dict], *, tags: list[str] | None = None, replacement: bool = False, actor: str = 'local_user'):
        if mode not in {"manual_edit", "ai_regenerate"} or not reason.strip():
            raise ValueError("请选择修订方式并填写原因")
        current = self.question(question_id)
        if current["stage"] == "golden":
            raise ValueError("已批准题目不能修订")
        if current["legacy_question_type"] != "v1_mini" or current['stage'] != 'candidate':
            raise ValueError("仅可编辑或替换活动 Golden Candidate")
        run_id = current["raw"].get("generation_run_id")
        run = self.generation_run(run_id)
        if not run or len(run["question_ids"]) != self._expected_count(run) or question_id not in run["question_ids"] or (run["artifacts"]["hard_validation"].get("slot_persistence_v1") and run["status"] != "completed"):
            raise ValueError("当前 Generation Run 不完整")
        ids = [question_id]
        if replacement and paired:
            raise ValueError('替换只作用于当前 Slot')
        if paired:
            linked = self.related_positive(current) if current["test_category"] == "ablation" else next((item for item_id in run["question_ids"] if (item := self.question(item_id))["test_category"] == "ablation" and (positive := self.related_positive(item)) and positive["id"] == question_id), None)
            if not linked or linked["stage"] == "golden" or linked["review_status"] not in {"needs_revision", "rejected"}:
                raise ValueError("没有可共同修订的待修订关联题")
            ids = [item_id for item_id in run["question_ids"] if item_id in {question_id, linked["id"]}]
        if mode == "manual_edit" and set(changes_by_id) != set(ids):
            raise ValueError("人工修订须为所选题目分别填写草案")
        if any(key not in ids for key in changes_by_id):
            raise ValueError("草案包含未选择的题目")
        before = {item_id: self.question(item_id) for item_id in ids}
        if any(item["stage"] == "golden" for item in before.values()):
            raise ValueError("已批准题目不能修订")
        revision_id = f"REV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        audit = {"question_ids": ids, "mode": mode, 'replacement': replacement, 'actor': actor, "reason": reason.strip(), "tags": tags or [], "before": before, "previous_hash": {item_id: self._revision_hash(item) for item_id, item in before.items()}, "changes": changes_by_id, "stage": "queued", "progress": {"current": 0, "total": len(ids)}}
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for row in connection.execute("SELECT audit_json FROM candidate_revision_runs WHERE generation_run_id=? AND status IN ('queued','generating','validating','preview_ready','probing','qc','interrupted')", (run_id,)):
                if set(_load(row["audit_json"], {}).get("question_ids", [])) & set(ids):
                    raise ValueError("所选题目已有未完成的 Revision Run")
            previous = [(row["status"], _load(row["audit_json"], {})) for row in connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE generation_run_id=?", (run_id,))]
            audit["attempt"] = {item_id: 1 + sum(item_id in other.get("question_ids", []) for _, other in previous) for item_id in ids}
            audit["version_from"] = {item_id: 1 + sum(status in {"probing", "qc", "completed", "failed_quality"} and item_id in other.get("question_ids", []) for status, other in previous) for item_id in ids}
            current_rows = {item_id: self._row(connection.execute("SELECT * FROM questions WHERE id=?", (item_id,)).fetchone()) for item_id in ids}
            if any(current_rows[item_id]["stage"] == "golden" or self._revision_hash(current_rows[item_id]) != audit["previous_hash"][item_id] for item_id in ids):
                raise ValueError("原题版本已变化，不能创建修订")
            connection.execute("INSERT INTO candidate_revision_runs VALUES (?, ?, ?, ?, ?, ?)", (revision_id, run_id, "queued", _json(audit), _now(), _now()))
        return self.revision_run(revision_id)

    def prepare_revision(self, revision_id: str, chunks: list[dict], *, similarity, generated: dict | None = None):
        run = self.revision_run(revision_id)
        if run["status"] not in {"queued", "interrupted"}:
            raise ValueError("Revision Run 不可重复校验")
        self.update_revision(revision_id, status="validating", stage="hard_validation")
        drafts, errors, new_hash, changed_fields = self._validate_revision_drafts(run, chunks, similarity, generated or run["changes"])
        if errors:
            editable_errors = ("草案未改变", "答案锚点")
            if run["mode"] == "manual_edit" and len(drafts) == len(run["question_ids"]) and all(any(marker in error for marker in editable_errors) for error in errors):
                return self.update_revision(revision_id, status="preview_ready", stage="preview_ready", error="；".join(errors), drafts=drafts, new_hash=new_hash, changed_fields=changed_fields, apply_blocked=True, validation={"passed": False, "errors": errors}, progress={"current": len(drafts), "total": len(drafts)})
            return self.update_revision(revision_id, status="failed", stage="hard_validation", error="；".join(errors), drafts=drafts, new_hash=new_hash, changed_fields=changed_fields, validation={"passed": False, "errors": errors})
        return self.update_revision(revision_id, status="preview_ready", stage="preview_ready", drafts=drafts, new_hash=new_hash, changed_fields=changed_fields, validation={"passed": True, "errors": []}, progress={"current": len(drafts), "total": len(drafts)})

    def _validate_revision_drafts(self, run: dict, chunks: list[dict], similarity, changes: dict):
        from .ai_service import AiService
        by_chunk = {chunk["chunk_id"]: chunk for chunk in chunks}
        drafts, errors = {}, []
        for item_id in run["question_ids"]:
            old = run["before"][item_id]
            change = changes.get(item_id, {})
            if not isinstance(change, dict):
                errors.append(f"{item_id}: 草案格式错误")
                continue
            allowed = {"question", "reference_answer", "source_chunk_ids", "ablation_metadata"}
            if set(change) - allowed:
                errors.append(f"{item_id}: 包含不可修改字段")
                continue
            source_ids = change.get("source_chunk_ids", [key for evidence in old["evidence"] for key in evidence.get("source_chunk_ids", [])])
            if not isinstance(source_ids, list) or any(not isinstance(key, str) or key not in by_chunk for key in source_ids):
                errors.append(f"{item_id}: Chunk 不存在于当前索引")
                continue
            original_chunks = [by_chunk[key] for evidence in old["evidence"] for key in evidence.get("source_chunk_ids", []) if key in by_chunk]
            old_documents = {chunk["document_id"] for chunk in original_chunks}
            original_product = next((chunk.get("product") for chunk in original_chunks if chunk.get("product")), None)
            if not original_product:
                coverage = (self.generation_run(run["generation_run_id"]).get("artifacts") or {}).get("coverage_plan", [])
                original_product = next((entry.get("product") for entry in coverage if entry.get("slot") == old["raw"].get("coverage_slot")), None)
            if old["test_category"] != "negative" and original_product and any(by_chunk[key]["document_id"] not in old_documents and by_chunk[key].get("product") not in {None, original_product} for key in source_ids):
                errors.append(f"{item_id}: 证据只能在当前产品文档内改选")
                continue
            if old["test_category"] == "negative" and source_ids:
                errors.append(f"{item_id}: 负向题不能添加 Golden Evidence")
                continue
            evidence = [] if old["test_category"] == "negative" else [{"source_chunk_ids": source_ids, "evidence_key_points": [by_chunk[key].get("chunk_text", by_chunk[key].get("text", ""))[:160] for key in source_ids if key in by_chunk]}]
            candidate = {"question": str(change.get("question", old["question"])).strip(), "reference_answer": change.get("reference_answer", old["reference_answer"]), "evidence": evidence, "test_category": old["test_category"], "expected_behavior": old["raw"].get("expected_behavior"), "ablation_attribute": old["raw"].get("ablation_attribute"), "ablation_metadata": change.get("ablation_metadata", old["raw"].get("ablation_metadata", {}))}
            errors.extend(f"{item_id}: {message.replace('unsupported answer anchor', '答案锚点未在所选证据原文中找到')}" for message in AiService._candidate_errors(candidate, chunks, set()))
            if old["test_category"] == "negative" and old["raw"].get("expected_behavior") == "safe_rejection" and not any(cue in candidate["question"] for cue in ("绕过", "禁用", "关闭", "短接", "忽略安全")):
                errors.append(f"{item_id}: 安全拒答题必须包含危险操作请求")
            drafts[item_id] = {**old, **candidate, "raw": {**old["raw"], "question": candidate["question"], "reference_answer": candidate["reference_answer"], "acceptable_evidence": evidence, "ablation_metadata": candidate["ablation_metadata"]}}
            old_ids = [key for source in old['evidence'] for key in source.get('source_chunk_ids', [])]
            if all(drafts[item_id][field] == old[field] for field in ("question", "reference_answer")) and source_ids == old_ids and candidate['ablation_metadata'] == old['raw'].get('ablation_metadata', {}):
                errors.append(f"{item_id}: 草案未改变问题、答案或证据")
        if len(drafts) == len(run["question_ids"]):
            active_ids = set(self.generation_run(run['generation_run_id'])['question_ids'])
            peers = [item for item in self.questions() if item['id'] in active_ids and item["id"] not in drafts]
            for item_id, draft in drafts.items():
                for peer in peers:
                    duplicate = _normalized(draft["question"]) == _normalized(peer["question"])
                    if duplicate:
                        errors.append(f"{item_id}: 与 {peer['id']} 规范化问题重复")
                        break
        changed_fields = {item_id: [field for field in ("question", "reference_answer", "evidence") if draft[field] != run["before"][item_id][field]] for item_id, draft in drafts.items()}
        new_hash = {item_id: self._revision_hash(draft) for item_id, draft in drafts.items()}
        return drafts, errors, new_hash, changed_fields

    @staticmethod
    def _draft_change(draft: dict):
        return {"question": draft["question"], "reference_answer": draft["reference_answer"], "source_chunk_ids": [key for evidence in draft["evidence"] for key in evidence.get("source_chunk_ids", [])], "ablation_metadata": draft["raw"].get("ablation_metadata", {})}

    def _begin_preview_attempt(self, revision_id: str, question_ids: list[str], expected_hashes: dict, kind: str, changes: dict | None = None, **intent):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, generation_run_id, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            if row["status"] not in {"preview_ready", "failed"}:
                raise ValueError("草案操作运行中或状态不允许")
            audit = _load(row["audit_json"], {})
            if audit.get("applied_at") or set(audit.get("drafts") or {}) != set(audit["question_ids"]) or set(audit.get("new_hash") or {}) != set(audit["question_ids"]):
                raise ValueError("仅未应用且已保存的草案可以重新生成")
            if not question_ids or set(question_ids) - set(audit["question_ids"]) or set(expected_hashes) != set(question_ids):
                raise ValueError("只能修改当前 Revision Run 的指定题目")
            if any(expected_hashes[item_id] != audit["new_hash"].get(item_id) for item_id in question_ids):
                raise ValueError("草案版本已过期，请刷新后重试")
            for item_id in audit["question_ids"]:
                current = self._row(connection.execute("SELECT * FROM questions WHERE id=?", (item_id,)).fetchone())
                if current["stage"] == "golden" or self._revision_hash(current) != audit["previous_hash"][item_id]:
                    raise ValueError("原题版本已变化，不能继续过期草案")
            for other in connection.execute("SELECT id, audit_json FROM candidate_revision_runs WHERE generation_run_id=? AND status IN ('queued','generating','validating','preview_ready','probing','qc','interrupted') AND id!=?", (row["generation_run_id"], revision_id)):
                if set(_load(other["audit_json"], {}).get("question_ids", [])) & set(audit["question_ids"]):
                    raise ValueError("所选题目已有其他未完成的 Revision Run")
            attempt = {"number": len(audit.get("draft_attempts", [])) + 1, "kind": kind, "question_ids": question_ids, "started_at": _now(), "status": "running", "previous_hash": {item_id: audit["new_hash"][item_id] for item_id in question_ids}, "before_drafts": {item_id: audit["drafts"][item_id] for item_id in question_ids}, **intent}
            if changes is not None:
                attempt["changes"] = changes
            audit["draft_attempts"] = [*audit.get("draft_attempts", []), attempt]
            audit["active_draft"] = {"number": attempt["number"], "kind": kind, "question_ids": question_ids, "changes": changes, **intent}
            audit["stage"] = "generating" if kind in {"regenerate", "reselect"} else "hard_validation"
            audit["error"] = None
            connection.execute("UPDATE candidate_revision_runs SET status=?, audit_json=?, updated_at=? WHERE id=?", ("generating" if kind in {"regenerate", "reselect"} else "validating", _json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def edit_revision_preview(self, revision_id: str, changes: dict, expected_hashes: dict, chunks: list[dict], *, similarity):
        if not changes or any(not isinstance(value, dict) for value in changes.values()):
            raise ValueError("请选择要编辑的草案")
        self._begin_preview_attempt(revision_id, list(changes), expected_hashes, "edit", changes)
        try:
            return self._finish_preview_attempt(revision_id, changes, chunks, similarity=similarity)
        except Exception as error:
            self.fail_revision_regeneration(revision_id, str(error))
            raise

    def begin_revision_regeneration(self, revision_id: str, question_id: str, expected_hash: str, *, material_mode: str = "retain", reason: str | None = None, tags: list[str] | None = None, manual_chunk_ids: list[str] | None = None):
        if material_mode not in {"retain", "reselect"}:
            raise ValueError("未知的材料处理方式")
        if material_mode == "retain" and (reason is not None or tags is not None or manual_chunk_ids is not None):
            raise ValueError("沿用证据时不能更新选材意图")
        if material_mode == "reselect":
            run = self.revision_run(revision_id)
            latest_reason = (reason if reason is not None else run["reason"]).strip()
            if not latest_reason or not isinstance(manual_chunk_ids, (list, type(None))) or manual_chunk_ids == []:
                raise ValueError("请填写重新选材意图，或选择有效的人工 Chunk")
            return self._begin_preview_attempt(revision_id, [question_id], {question_id: expected_hash}, "reselect", reason=latest_reason, tags=tags if tags is not None else run.get("tags", []), manual_chunk_ids=manual_chunk_ids)
        return self._begin_preview_attempt(revision_id, [question_id], {question_id: expected_hash}, "regenerate")

    def finish_revision_regeneration(self, revision_id: str, generated: dict, chunks: list[dict], *, similarity):
        return self._finish_preview_attempt(revision_id, generated, chunks, similarity=similarity)

    def _finish_preview_attempt(self, revision_id: str, replacements: dict, chunks: list[dict], *, similarity):
        run = self.revision_run(revision_id)
        active = run.get("active_draft")
        if run["status"] not in {"validating", "generating", "interrupted"} or not active or set(replacements) != set(active["question_ids"]):
            raise ValueError("草案操作运行中或状态不允许")
        changes = {item_id: self._draft_change(run["drafts"][item_id]) for item_id in run["question_ids"]}
        changes.update(replacements)
        drafts, errors, new_hash, changed_fields = self._validate_revision_drafts(run, chunks, similarity, changes)
        if active["kind"] == "regenerate":
            for item_id in active["question_ids"]:
                selected = self._draft_change(run["drafts"][item_id])["source_chunk_ids"]
                if changes[item_id].get("source_chunk_ids") != selected:
                    errors.append(f"{item_id}: 重生成必须沿用当前选定的证据 Chunk")
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            audit = _load(row["audit_json"], {})
            if row["status"] not in {"validating", "generating", "interrupted"} or audit.get("active_draft", {}).get("number") != active["number"]:
                raise ValueError("草案操作已变化，请刷新后重试")
            attempt = {**audit["draft_attempts"][-1], "status": "failed" if errors else "passed", "completed_at": _now(), "error": "；".join(errors) if errors else None, "result": replacements, "validated_drafts": {item_id: drafts[item_id] for item_id in active["question_ids"] if item_id in drafts}}
            audit["draft_attempts"][-1] = attempt
            audit.update({"active_draft": None, "stage": "preview_ready", "apply_blocked": bool(errors), "error": attempt["error"], "last_attempt_validation": {"passed": not errors, "errors": errors}})
            if not errors:
                audit.update({"drafts": {**audit["drafts"], **{item_id: drafts[item_id] for item_id in active["question_ids"]}}, "new_hash": {**audit["new_hash"], **{item_id: new_hash[item_id] for item_id in active["question_ids"]}}, "changed_fields": changed_fields, "validation": {"passed": True, "errors": []}})
                if active["kind"] == "reselect":
                    target = active["question_ids"][0]
                    audit.update({"reason": active["reason"], "tags": active["tags"], "material_selection": {**audit.get("material_selection", {}), target: active["material_selection"]}})
            connection.execute("UPDATE candidate_revision_runs SET status='preview_ready', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def fail_revision_regeneration(self, revision_id: str, error: str):
        run = self.revision_run(revision_id)
        if run["status"] not in {"generating", "validating", "interrupted"} or not run.get("active_draft"):
            raise ValueError("草案操作不在运行中")
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            audit = _load(row["audit_json"], {})
            if row["status"] not in {"generating", "validating", "interrupted"} or not audit.get("active_draft"):
                raise ValueError("草案操作不在运行中")
            audit["draft_attempts"][-1].update({"status": "failed", "completed_at": _now(), "error": error})
            audit.update({"active_draft": None, "stage": "preview_ready", "failed_stage": audit.get("stage"), "apply_blocked": True, "error": error, "last_attempt_validation": {"passed": False, "errors": [error]}})
            connection.execute("UPDATE candidate_revision_runs SET status='preview_ready', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def discard_revision(self, revision_id: str):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            audit = _load(row["audit_json"], {})
            if row["status"] not in {"preview_ready", "interrupted", "failed"} or not audit.get("drafts") or audit.get("applied_at") or audit.get("active_draft"):
                raise ValueError("仅可放弃未应用且未运行中的草案")
            audit.update({"stage": "discarded", "discarded_at": _now()})
            connection.execute("UPDATE candidate_revision_runs SET status='cancelled', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def apply_revision(self, revision_id: str, chunks: list[dict], *, similarity):
        run = self.revision_run(revision_id)
        if run["status"] != "preview_ready" or run.get("apply_blocked"):
            if run.get("apply_blocked"):
                raise ValueError("最近一次草案校验失败，已暂停应用")
            raise ValueError("草案尚未通过 Hard Validation")
        changes = {item_id: self._draft_change(run["drafts"][item_id]) for item_id in run["question_ids"]}
        _, errors, hashes, _ = self._validate_revision_drafts(run, chunks, similarity, changes)
        if errors or any(hashes.get(item_id) != run["new_hash"].get(item_id) for item_id in run["question_ids"]):
            raise ValueError("草案重新 Hard Validation 未通过：" + "；".join(errors or ["草案版本已变化"]))
        ids = run["question_ids"]
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            status_row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if status_row is None or status_row["status"] != "preview_ready" or _load(status_row["audit_json"], {}).get("apply_blocked") or _load(status_row["audit_json"], {}).get("new_hash") != run["new_hash"]:
                raise ValueError("草案已被应用或不再可用")
            current = {item_id: self._row(connection.execute("SELECT * FROM questions WHERE id = ?", (item_id,)).fetchone()) for item_id in ids}
            if any(current[item_id]["stage"] == "golden" or self._revision_hash(current[item_id]) != run["previous_hash"][item_id] for item_id in ids):
                raise ValueError("原题版本已变化，不能应用过期草案")
            versions = {item_id: 1 + sum(other["status"] in {"probing", "qc", "completed", "failed_quality"} and item_id in other["question_ids"] for other in self.revision_runs(run["generation_run_id"])) for item_id in ids}
            new_hash, changed_fields, replacements = {}, {}, {}
            for item_id in ids:
                draft = run["drafts"][item_id]
                selected_ids = [key for evidence in draft["evidence"] for key in evidence.get("source_chunk_ids", [])]
                if any(key not in {chunk["chunk_id"] for chunk in chunks} for key in selected_ids):
                    raise ValueError("当前索引已变化，证据 Chunk 不可用")
                changed_fields[item_id] = [field for field in ("question", "reference_answer", "evidence", "raw") if draft[field] != current[item_id][field]]
                new_hash[item_id] = self._revision_hash({**draft, "stage": "candidate", "review_status": "needs_revision"})
                if run.get('replacement'):
                    new_id = f"{item_id}-R{revision_id[-12:]}"
                    draft = {**draft, 'id': new_id, 'raw': {**draft['raw'], 'id': new_id, 'replaces_question_id': item_id}}
                    connection.execute("INSERT INTO questions (id,stage,legacy_question_type,test_category,negative_subtype,review_status,probe_status,qc_status,question,reference_answer,evidence_json,raw_json,created_at,updated_at) VALUES (?, 'candidate', 'v1_mini', ?, ?, 'human_review_pending', 'probe_pending', 'qc_pending', ?, ?, ?, ?, ?, ?)", (new_id, draft['test_category'], draft.get('negative_subtype'), draft['question'], draft['reference_answer'], _json(draft['evidence']), _json(draft['raw']), _now(), _now()))
                    connection.execute("UPDATE questions SET stage='superseded', updated_at=? WHERE id=?", (_now(), item_id))
                    replacements[item_id] = new_id
                    run['drafts'][new_id] = draft
                    new_hash[new_id] = self._revision_hash(draft)
                else:
                    connection.execute("UPDATE questions SET question=?, reference_answer=?, evidence_json=?, raw_json=?, stage='candidate', review_status='needs_revision', probe_status='probe_pending', qc_status='qc_pending', updated_at=? WHERE id=?", (draft["question"], draft["reference_answer"], _json(draft["evidence"]), _json(draft["raw"]), _now(), item_id))
                connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at, metadata_json) VALUES (?, 'revision', 'revision_applied', ?, ?, ?)", (item_id, run.get('actor', 'local_user'), _now(), _json({"revision_id": revision_id, 'replacement_id': replacements.get(item_id)})))
            audit = {**_load(status_row["audit_json"], {}), "new_hash": new_hash, "changed_fields": changed_fields, "version_from": versions, "version_to": {key: value + 1 for key, value in versions.items()}, "stage": "probe", "progress": {"current": 0, "total": len(ids)}, "applied_at": _now()}
            audit["drafts"] = {**audit["drafts"], **{item_id: run["drafts"][item_id] for item_id in ids}}
            if replacements:
                row = connection.execute('SELECT question_ids_json FROM golden_generation_runs WHERE id=?', (run['generation_run_id'],)).fetchone()
                active = _load(row[0], [])
                if not set(ids).issubset(active):
                    raise ValueError('活动 Slot 已变化')
                connection.execute('UPDATE golden_generation_runs SET question_ids_json=? WHERE id=?', (_json([replacements.get(key, key) for key in active]), run['generation_run_id']))
                audit.update(source_question_ids=ids, question_ids=[replacements.get(key, key) for key in ids], replacements=replacements, drafts={**audit['drafts'], **run['drafts']})
            connection.execute("UPDATE candidate_revision_runs SET status='probing', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def revision_quality_step(self, run: dict, question_id: str):
        applied_at = run.get("applied_at") or ""
        item = self.question(question_id)
        qc = self.qc_history(question_id)
        if item["qc_status"] == "qc_passed" and qc and qc[0]["created_at"] > applied_at:
            return "done"
        probe = self.probe_history(question_id)
        if item["probe_status"] == "probe_passed" and probe and probe[0]["created_at"] > applied_at:
            return "qc"
        return "probe"

    def resume_revision_quality(self, revision_id: str):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            audit = _load(row["audit_json"], {})
            if row["status"] not in {"failed_quality", "interrupted"} or not audit.get("applied_at") or (row["status"] == "failed_quality" and not audit.get("error")):
                raise ValueError("仅已应用且运行失败的 Revision Run 可继续；运行中或质量低分不可重试")
            for item_id in audit["question_ids"]:
                item = self._row(connection.execute("SELECT * FROM questions WHERE id=?", (item_id,)).fetchone())
                draft = audit["drafts"][item_id]
                if item["stage"] != "candidate" or any(item[key] != draft[key] for key in ("question", "reference_answer", "evidence", "raw")):
                    raise ValueError("Candidate 已变化，不能继续过期的质量运行")
            steps = {item_id: self.revision_quality_step(audit, item_id) for item_id in audit["question_ids"]}
            stage = "qc" if all(value in {"qc", "done"} for value in steps.values()) else "probe"
            failures = list(audit.get("failure_history") or [])
            if audit.get("error"):
                failures.append({"error": audit["error"], "error_type": audit.get("error_type"), "error_detail": audit.get("error_detail"), "failed_stage": audit.get("failed_stage") or stage, "finished_at": audit.get("finished_at")})
            audit.update({"stage": stage, "error": None, "error_type": None, "error_detail": None, "finished_at": None, "failure_history": failures})
            connection.execute("UPDATE candidate_revision_runs SET status=?, audit_json=?, updated_at=? WHERE id=?", ("qc" if stage == "qc" else "probing", _json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def finish_revision_quality(self, revision_id: str, results: dict, *, error: str | None = None, error_type: str | None = None, error_detail: str | None = None):
        run = self.revision_run(revision_id)
        if run["status"] not in {"probing", "qc", "interrupted"}:
            raise ValueError("Revision Run 未进入质量检查")
        passed = not error and all(results.get(item_id, {}).get("probe") == "passed" and results.get(item_id, {}).get("qc") == "qc_passed" for item_id in run["question_ids"])
        status = "completed" if passed else "failed_quality"
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if passed:
                for item_id in run["question_ids"]:
                    latest = connection.execute("SELECT decision FROM review_events WHERE question_id=? AND created_at > ? AND gate='dataset' ORDER BY id DESC LIMIT 1", (item_id, run["applied_at"])).fetchone()
                    if latest is None:
                        connection.execute("UPDATE questions SET review_status='human_review_pending', updated_at=? WHERE id=? AND stage='candidate' AND probe_status='probe_passed' AND qc_status='qc_passed'", (_now(), item_id))
            audit = _load(run["audit_json"], {})
            audit.update({"stage": status, "failed_stage": run["stage"] if error else None, "quality_results": results, "error": error, "error_type": error_type, "error_detail": error_detail, "progress": {"current": len(results), "total": len(run["question_ids"])}, "finished_at": _now()})
            connection.execute("UPDATE candidate_revision_runs SET status=?, audit_json=?, updated_at=? WHERE id=?", (status, _json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def update_question(self, question_id: str, question: str, reference_answer: str | None, evidence: list, actor: str):
        self.require_generation_ready(question_id)
        current = self.question(question_id)
        if current["legacy_question_type"] == "v1_mini" and (current["stage"] == "golden" or any(event["decision"] in {"needs_revision", "rejected"} for event in self.review_history(question_id))):
            raise ValueError("已批准或待修订题目须走局部修订流程")
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
        from .corpus import current_manifest
        snapshot = {"question_ids": [item["id"] for item in approved], "questions": [item["raw"] for item in approved], "corpus_fingerprint": current_manifest()["sources"]}
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
        run = self.generation_run(generation_run_id)
        expected = self._expected_count(run)
        if len(approved) != expected or len(set(question_ids)) != expected or any(item["stage"] != "golden" or item["review_status"] != "approved" or not self.approval_eligibility(item['id'])['can_approve'] for item in approved):
            raise ValueError(f"同一 Generation Run 的 {expected} 道题必须全部完成人工批准后才能创建 Snapshot")
        if any(set(item["question_ids"]) & set(question_ids) for item in self.revision_runs(generation_run_id) if item["status"] in {"queued", "generating", "validating", "preview_ready", "probing", "qc", "interrupted"}):
            raise ValueError("仍有未完成的局部修订，不能创建 Snapshot")
        existing = next((item['snapshot'] for item in self.dataset_snapshots() if item['snapshot'].get('generation_run_id') == generation_run_id and item['snapshot'].get('question_ids') == question_ids), None)
        return existing or self.create_dataset_snapshot(approved, generation_run_id)

    def run_probe(self, question_id: str, retriever, chunks: list[dict], answerability_judge=None, *, subtype_judge=None, fail_on_judge_error: bool = False):
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
        programmatic['answer_anchor'] = _answer_anchor_supported(item['reference_answer'] or '', [source_texts[key] for key in expected_chunks if key in source_texts]) if positive else True
        haystack = " ".join(source_texts.values())
        phrases = [point for source in evidence for point in source.get("evidence_key_points", [])]
        matched = [phrase for phrase in phrases if phrase and phrase in haystack]
        source_checks = [{"chunk_id": chunk_id, "text_available": bool(source_texts.get(chunk_id, "").strip())} for chunk_id in sorted(expected_chunks)]
        normalized_query = _normalized(item["question"])
        corpus_matches = [chunk_id for chunk_id, text in source_texts.items() if normalized_query and normalized_query in _normalized(text)]
        entity_tokens = [token for token in item["question"].replace("/", " ").replace("-", " ").split() if len(token) > 1 and any(character.isdigit() or character.isascii() and character.isalpha() for character in token)]
        entity_matches = [chunk_id for chunk_id, text in source_texts.items() if any(token.lower() in text.lower() for token in entity_tokens)]
        subtype = item.get("negative_subtype") if item["legacy_question_type"] == "v1_mini" else expected_behavior
        subtype = subtype or expected_behavior
        behavior = "prompt_injection_resistance" if subtype == "prompt_injection" else "safe_rejection" if subtype == "safety_critical" else subtype
        subtype_mismatch = behavior != expected_behavior
        subtype_semantic = None
        if not positive and not subtype_mismatch and subtype in {"safe_rejection", "safety_critical", "prompt_injection"}:
            explicit = re.search(r"(忽略|覆盖|泄露).{0,16}(系统提示|系统指令|内部规则)|忽略规则并伪造|越狱", item["question"]) if subtype == "prompt_injection" else re.search(r"(绕过|禁用|关闭|短接).{0,8}(安全|保护|急停)", item["question"])
            if explicit:
                subtype_semantic = {"matched": True, "detected_subtype": subtype, "reason": "explicit local signal", "source": "local"}
            else:
                try:
                    subtype_semantic = subtype_judge(item["question"], hits, {"negative_subtype": subtype, "expected_behavior": expected_behavior}) if subtype_judge else {"matched": False, "reason": "Negative subtype Judge unavailable"}
                except Exception as error:
                    if fail_on_judge_error:
                        raise
                    subtype_semantic = {"matched": False, "reason": str(error), "error_type": type(error).__name__}
                subtype_mismatch = subtype_semantic.get("matched") is not True or subtype_semantic.get("detected_subtype") != subtype
        ambiguous_negative = not positive and subtype in {"insufficient_evidence", "clarify"} and bool(corpus_matches or entity_matches or best >= .75)
        answerability = None
        if ambiguous_negative:
            try:
                answerability = answerability_judge(item["question"], hits, {"negative_subtype": subtype, "vector_best_similarity": best, "full_text_hits": corpus_matches, "entity_hits": entity_matches, "clarify_requires_unique_answer": subtype == "clarify"}) if answerability_judge else {"answerable": None, "reason": "Answerability Judge unavailable"}
            except Exception as error:
                if fail_on_judge_error:
                    raise
                answerability = {"answerable": None, "reason": str(error)}
        negative_passed = behavior == expected_behavior and not subtype_mismatch and (not ambiguous_negative or answerability.get("answerable") is False)
        full_text = {"mode": "evidence" if positive else "fake_negative_check", "phrases": phrases, "matched_phrases": matched, "source_checks": source_checks, "normalized_query": normalized_query, "corpus_match_chunk_ids": corpus_matches, "entity_match_chunk_ids": entity_matches, "passed": bool(source_checks) and all(check["text_available"] for check in source_checks) if positive else negative_passed}
        evidence_valid = all(programmatic.values()) and full_text["passed"]
        full_text['answer_anchor_supported'] = programmatic['answer_anchor'] if positive else None
        recalled = bool(expected_chunks & {hit.get("chunk_id") for hit in hits}) if positive else None
        classification = "RETRIEVAL_INCOHERENT" if positive and evidence_valid and not recalled else "EVIDENCE_VALID" if positive and evidence_valid else "EVIDENCE_INVALID" if positive else "NEGATIVE_VALID" if evidence_valid else "NEGATIVE_SUBTYPE_MISMATCH" if subtype_mismatch else "FAKE_NEGATIVE_RISK" if answerability and answerability.get("answerable") is True else "NEGATIVE_UNDETERMINED"
        exact_matches = [{"chunk_id": chunk_id, "document_id": next((chunk.get("document_id") for chunk in chunks if chunk.get("chunk_id") == chunk_id), None), "matched_terms": [term for term in entity_tokens if term.lower() in source_texts[chunk_id].lower()], "content_preview": source_texts[chunk_id][:240]} for chunk_id in dict.fromkeys(corpus_matches + entity_matches)]
        negative_checks = None if positive else {
            "vector_probe": {"observed_hits": hits, "signal_only": True},
            "full_text_probe": {"corpus_match_chunk_ids": corpus_matches, "entity_match_chunk_ids": entity_matches, "matches": exact_matches, "exact_match_count": len(exact_matches), "signal_only": True},
            "answerability": answerability,
            "subtype_semantic": subtype_semantic,
            "fake_negative_check": {"expected_behavior": expected_behavior, "negative_subtype": subtype, "subtype_mismatch": subtype_mismatch, "ambiguous": ambiguous_negative, "passed": negative_passed},
        }
        result = self.record_probe_result(question_id, {
            "question_quality": 30 if bool(item["question"].strip()) else 0,
            "golden_answer_quality": 30 if (not positive or bool(item["reference_answer"])) else 0,
            "evidence_support": 40 if evidence_valid else 0,
            "evidence_direct_failure": not evidence_valid,
            "reason": "Evidence exists but the production pipeline did not recall it" if classification == "RETRIEVAL_INCOHERENT" else "Programmatic evidence check" if evidence_valid else "Negative subtype does not match the question" if subtype_mismatch else "Negative may be answerable" if classification == "FAKE_NEGATIVE_RISK" else "Answerability could not be established" if not positive else "Evidence or required fields cannot support Golden",
            "rule_version": "v1.2",
            "model_version": "programmatic-probe-v1",
            "probe_details": {"pipeline": "CandidateK → Hybrid → Lightweight second-stage ranking → MinScore → TopK" if positive else "vector + full-text fake-negative check", "vector": {"top_k": hits, "best_similarity": best}, "full_text": full_text, "negative_checks": negative_checks, "classification": classification, "retrieval_coherent": recalled},
        })
        return {**result, "classification": classification, "programmatic": {"checks": programmatic, "passed": all(programmatic.values())}, "vector": {"top_k": hits, "best_similarity": best, "signal": "observed_only"}, "full_text": full_text, "passed": result["status"] == "passed"}

    def record_probe_result(self, question_id: str, result: dict):
        """Persist the frozen 30/30/40 probe; evidence failure is non-compensable."""
        item = self.question(question_id)
        caps = {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40}
        scores = {}
        for field, cap in caps.items():
            value = result.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= cap:
                raise ValueError(f"Invalid {field} score")
            scores[field] = float(value)
        evidence_direct_failure = result.get("evidence_direct_failure") is True
        score = round(sum(scores.values()), 1)
        passed = not evidence_direct_failure and (item['test_category'] != 'negative' or score >= 90)
        stored = {
            "question_id": question_id, **scores, "score": score,
            "threshold": 90 if item['test_category'] == 'negative' else None, "evidence_direct_failure": evidence_direct_failure,
            "status": "passed" if passed else "failed", "reason": str(result.get("reason", "")),
            "rule_version": str(result.get("rule_version", "v1.0.1")),
            "model_version": str(result.get("model_version", "programmatic-probe-v1")),
            "probe_details": result.get("probe_details", {}),
        }
        with self.connection() as connection:
            connection.execute("INSERT INTO probe_results(question_id, result_json, created_at) VALUES (?, ?, ?)", (question_id, _json(stored), _now()))
            manual = connection.execute("SELECT 1 FROM review_events WHERE question_id = ? LIMIT 1", (question_id,)).fetchone()
            review_status = self.question(question_id)["review_status"] if manual else "human_review_pending" if passed else "needs_revision"
            connection.execute("UPDATE questions SET probe_status = ?, review_status = ?, updated_at = ? WHERE id = ?", ("probe_passed" if passed else "needs_revision", review_status, _now(), question_id))
        return stored

    def reset_qc_for_rerun(self, question_id: str):
        with self.connection() as connection:
            connection.execute("UPDATE questions SET qc_status = 'qc_pending', updated_at = ? WHERE id = ?", (_now(), question_id))

    def probe_history(self, question_id: str):
        with self.connection() as connection:
            rows = connection.execute("SELECT result_json, created_at FROM probe_results WHERE question_id = ? ORDER BY id DESC", (question_id,)).fetchall()
        return [{**_load(row["result_json"], {}), "created_at": row["created_at"]} for row in rows]

    def review_generation_batch(self, question_ids: list[str], actor: str, *, confirmed_manual_review: bool = False):
        if not confirmed_manual_review:
            raise ValueError("Human Review confirmation is required")
        candidates = [self.question(question_id) for question_id in question_ids]
        runs = {item["raw"].get("generation_run_id") for item in candidates}
        run = self.generation_run(next(iter(runs))) if len(runs) == 1 and None not in runs else None
        from .corpus import current_manifest
        run_fingerprint = (run.get("artifacts", {}).get("hard_validation", {}) if run else {}).get("corpus_fingerprint")
        if run_fingerprint is not None and run_fingerprint != current_manifest()["sources"]:
            raise ValueError("Corpus 已变化；请基于当前知识库创建新的 Generation Run")
        expected = self._expected_count(run) if run else 0
        if not expected or len(candidates) != expected or len(set(question_ids)) != expected or len(runs) != 1 or any(item["raw"].get("generation_run_id") != run["id"] for item in candidates):
            raise ValueError("Batch review only accepts one complete generation run")
        if set(question_ids) != set((self.generation_run(next(iter(runs))) or {}).get("question_ids", [])):
            raise ValueError("Batch review question IDs must match the generation run")
        now = _now()
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            candidates = [self.question(question_id) for question_id in question_ids]
            if set(self.generation_run(run['id'])['question_ids']) != set(question_ids):
                raise ValueError('活动题目已变化，请刷新')
            if any(sum(item['test_category'] == category for item in candidates) != profile_count(run['profile'], category) for category in ('positive', 'ablation', 'negative')):
                raise ValueError('Profile 类别数量不符')
            for item in candidates:
                eligibility = self.approval_eligibility(item['id'])
                if not eligibility['can_approve']:
                    raise ValueError(f"{item['id']}: " + ('；'.join(eligibility['blocking_reasons']) or 'QC P0 请逐题明确接受'))
                if item['review_status'] in {'needs_revision', 'rejected'}:
                    raise ValueError('人工需修订或已拒绝的题目不得批量覆盖，请逐题审核')
            for question_id in question_ids:
                if next(item for item in candidates if item["id"] == question_id)["stage"] == "golden":
                    continue
                connection.execute("UPDATE questions SET stage = ?, review_status = ?, updated_at = ? WHERE id = ?", ("golden", "approved", now, question_id))
                connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (question_id, "dataset", "approved", actor, now))
                connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, "approved", actor, now))
            prior = next((item['snapshot'] for item in self.dataset_snapshots() if item['snapshot'].get('generation_run_id') == run['id'] and item['snapshot'].get('question_ids') == run['question_ids']), None)
            snapshot = prior or {'id': f"GD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", 'generation_run_id': run['id'], 'profile': run['profile'], 'question_ids': run['question_ids'], 'questions': [self.question(key)['raw'] for key in run['question_ids']], 'policy_version': 'v1.3', 'corpus_fingerprint': run_fingerprint or current_manifest()['sources']}
            if not prior:
                connection.execute('INSERT INTO dataset_versions VALUES (?, ?, ?, ?, ?)', (snapshot['id'], 'approved', 'human_review', _json(snapshot), now))
        return {"reviewed": [self.question(question_id) for question_id in question_ids], "generation_run_id": run['id'], 'snapshot': snapshot}

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
        qc_status = 'qc_failed' if priority == 'P0' else 'qc_passed'
        result = {**result, "score": float(score), "priority": priority, "threshold": None, "status": qc_status, "rule_version": 'v1.2'}
        with self.connection() as connection:
            connection.execute("INSERT INTO qc_results(question_id, status, result_json, created_at) VALUES (?, ?, ?, ?)", (question_id, qc_status, _json(result), _now()))
            manual = connection.execute("SELECT 1 FROM review_events WHERE question_id = ? LIMIT 1", (question_id,)).fetchone()
            review_status = item["review_status"] if manual else "human_review_pending" if qc_status == "qc_passed" else "needs_revision"
            connection.execute("UPDATE questions SET qc_status = ?, review_status = ?, updated_at = ? WHERE id = ?", (qc_status, review_status, _now(), question_id))
        return {"question_id": question_id, "status": qc_status, "result": result}

    def qc_history(self, question_id: str):
        with self.connection() as connection:
            rows = connection.execute("SELECT status, result_json, created_at FROM qc_results WHERE question_id = ? ORDER BY id DESC", (question_id,)).fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {})} for row in rows]

    def production_versions(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM production_versions ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "config": _load(row["config_json"], {}), "snapshot": _load(row["snapshot_json"] if "snapshot_json" in row.keys() else "{}", {}), "provenance": "bootstrap" if row["approval_id"] is None and row["evaluation_run_id"] is None else "published"} for row in rows]

    def active_production(self):
        return next((item for item in self.production_versions() if item["status"] == "active"), None)

    def evaluation_runs(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM evaluation_runs ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {}), "config": _load(row["config_json"], {}), "judge": _load(row["judge_json"], {})} for row in rows]

    def evaluation_run(self, run_id: str):
        return next((item for item in self.evaluation_runs() if item["id"] == run_id), None)

    def current_baseline_identity(self, connection=None):
        """One resolver for current APIs and transactional mutation guards."""
        if connection is None:
            with self.connection() as connection:
                return self.current_baseline_identity(connection)
        fingerprint = current_manifest()["sources"]
        golden = connection.execute("SELECT * FROM dataset_versions WHERE status='approved' ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
        identity = {"current_baseline_id": None, "current_experiment_id": None, "current_golden_id": golden["id"] if golden else None, "current_corpus_fingerprint": fingerprint, "baseline_unavailable_reason": None, "requires_new_golden": True}
        if golden is None:
            return {**identity, "baseline_unavailable_reason": "需要当前有效 Baseline：请先创建已批准（approved）的 Golden Snapshot"}
        snapshot = _load(golden["snapshot_json"], {})
        if snapshot.get("corpus_fingerprint") != fingerprint:
            return {**identity, "baseline_unavailable_reason": "Corpus 已变化；请创建并确认新的 Golden 测试集及 Baseline"}
        identity["requires_new_golden"] = False
        # Missing run_target is classified by persisted execution evidence, never by NULL alone.
        rows = connection.execute("SELECT * FROM evaluation_runs WHERE status='completed' AND run_mode='real' AND data_source='real' AND dataset_version_id=? ORDER BY created_at DESC, rowid DESC", (golden["id"],)).fetchall()
        for row in rows:
            config, judge, result = _load(row["config_json"], {}), _load(row["judge_json"], {}), _load(row["result_json"], {})
            frozen = _load(row["dataset_snapshot_json"], {})
            if config.get("run_target") not in (None, "baseline") or config.get("candidate_id") or result.get("invalidated") or config.get("invalidated"):
                continue
            if connection.execute("SELECT 1 FROM candidate_configs WHERE json_extract(result_json, '$.evaluation_run_id')=? LIMIT 1", (row["id"],)).fetchone():
                continue
            if not config or not judge.get("model") or not judge.get("prompt_version") or not judge.get("scoring_policy") or "gates" not in result or row["error_message"] or not row["completed_at"]:
                continue
            if frozen.get("corpus_fingerprint") != fingerprint or not snapshot.get("question_ids") or any(frozen.get(key) != snapshot.get(key) for key in ("question_ids", "questions")):
                continue
            cases = connection.execute("SELECT question_id FROM evaluation_case_results WHERE run_id=?", (row["id"],)).fetchall()
            if sorted(case["question_id"] for case in cases) != sorted(snapshot["question_ids"]):
                continue
            experiment = connection.execute("SELECT id FROM experiments WHERE baseline_run_id=? AND status!='direct_release' ORDER BY created_at DESC, rowid DESC LIMIT 1", (row["id"],)).fetchone()
            return {**identity, "current_baseline_id": row["id"], "current_experiment_id": experiment["id"] if experiment else None}
        return {**identity, "baseline_unavailable_reason": "当前 Golden/Corpus 需要新的有效 Baseline；旧实验仅供历史查看"}

    def require_current_baseline(self, run_id=None, connection=None):
        identity = self.current_baseline_identity(connection)
        if identity["current_baseline_id"] is None:
            raise ValueError(identity["baseline_unavailable_reason"])
        if run_id and run_id != identity["current_baseline_id"]:
            raise ValueError("Optimization Run 不属于当前 Baseline；旧实验仅供历史查看")
        return self.evaluation_run(identity["current_baseline_id"])

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

    def claim_agent_generation(self, baseline_run_id, trigger_id=None, experiment_id=None):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.require_current_baseline(baseline_run_id, connection)
            if trigger_id:
                trigger = connection.execute("SELECT * FROM optimization_triggers WHERE id=?", (trigger_id,)).fetchone()
                if trigger is None or trigger["status"] != "human_confirmed":
                    raise ValueError("Monitoring Trigger 必须经 Human Confirm 才能启动 Agent")
                if experiment_id and experiment_id != trigger["optimization_run_id"]:
                    raise ValueError("Optimization Run 不属于该 Monitoring Trigger")
                experiment_id = trigger["optimization_run_id"]
            if not experiment_id:
                row = connection.execute("SELECT id FROM experiments WHERE baseline_run_id=? AND status!='direct_release' ORDER BY created_at DESC, rowid DESC LIMIT 1", (baseline_run_id,)).fetchone()
                experiment_id = row["id"] if row else None
            existing = self.experiment(experiment_id) if experiment_id else None
            if experiment_id and (existing is None or existing["baseline_run_id"] != baseline_run_id):
                raise ValueError("Optimization Run 不存在或不属于该 Baseline")
            if existing and existing["status"] == "generating":
                raise ValueError("Optimization Agent 正在生成中，请等待当前请求完成")
            if existing and existing["result"].get("report_confirmation"):
                raise ValueError("报告已确认，不能继续改变实验")
            candidates = existing["candidates"] if existing else []
            rounds = [item["reasoning"]["round"] for item in candidates if type(item["reasoning"].get("round")) is int and item["reasoning"]["round"] >= 1]
            if candidates and not rounds:
                raise ValueError("历史 Candidate 缺少有效 Round，无法继续优化")
            current_round = max(rounds, default=0)
            current = [item for item in candidates if item["reasoning"].get("round") == current_round]
            if current and any(item["status"] not in {"evaluated", "failed"} for item in current):
                raise ValueError("上一轮 A/B/C 必须全部完成 Sandbox 后才能继续优化")
            if any(item["result"].get("qualification", {}).get("qualified") for item in current):
                raise ValueError("已有合格 Candidate，无需继续生成下一轮")
            used = existing["evaluation_budget"]["used"] if existing else 0
            if used >= MAX_EVALS - 1:
                raise ValueError(f"evaluation budget exhausted: max_evals={MAX_EVALS}")
            if not experiment_id:
                experiment_id = f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                connection.execute("INSERT INTO experiments VALUES (?, ?, 'generating', '{}', ?)", (experiment_id, baseline_run_id, _now()))
            else:
                connection.execute("UPDATE experiments SET status='generating' WHERE id=?", (experiment_id,))
        return experiment_id, candidates, current_round + 1, used

    def save_agent_round(self, experiment_id, candidates, result):
        """Validated A/B/C and completed trace become visible together or not at all."""
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
            self.require_current_baseline(row["baseline_run_id"], connection)
            persisted = _load(row["result_json"], {})
            if row["status"] != "generating" or persisted.get("report_confirmation"):
                raise ValueError("Optimization Context 已变化，不能保存本轮候选")
            for candidate_id, config, reasoning in candidates:
                connection.execute("INSERT INTO candidate_configs VALUES (?, ?, 'generated', ?, ?, '{}', ?)", (f"{experiment_id}-{candidate_id}", experiment_id, _json(config), _json(reasoning), _now()))
            connection.execute("INSERT INTO agent_traces(experiment_id, status, result_json, created_at) VALUES (?, 'completed', ?, ?)", (experiment_id, _json(result), _now()))
            connection.execute("UPDATE experiments SET status='completed', result_json=? WHERE id=?", (_json({**persisted, **result}), experiment_id))

    def save_agent_trace(self, experiment_id: str, status: str, result: dict, error_message: str | None = None):
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            current = connection.execute('SELECT status, result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
            persisted = _load(current['result_json'], {})
            merged = {**persisted, **result}
            for key in ('report_confirmation', 'composite'):
                if key in persisted:
                    merged[key] = persisted[key]
            connection.execute("INSERT INTO agent_traces(experiment_id, status, result_json, error_message, created_at) VALUES (?, ?, ?, ?, ?)", (experiment_id, status, _json(result), error_message, _now()))
            connection.execute("UPDATE experiments SET status = ?, result_json = ? WHERE id = ?", (current['status'] if persisted.get('report_confirmation') else status, _json(merged), experiment_id))

    def interrupt_agent_generations(self):
        with self.connection() as connection:
            connection.execute("UPDATE experiments SET status='failed' WHERE status='generating'")

    def interrupt_evaluation_runs(self):
        """Workers are process-local: retain spent attempts, never claim a live worker after restart."""
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute("UPDATE evaluation_runs SET status='failed', error_message=?, completed_at=? WHERE status IN ('queued', 'running')", ('进程重启，评测已中断', _now()))
            interrupted = connection.execute("SELECT id, experiment_id, result_json FROM candidate_configs WHERE status='running'").fetchall()
            for row in interrupted:
                result = {**_load(row['result_json'], {}), 'error': '进程重启，评测已中断', 'interrupted': True}
                connection.execute("UPDATE candidate_configs SET status='failed', result_json=? WHERE id=?", (_json(result), row['id']))
        for experiment_id in {row['experiment_id'] for row in interrupted}:
            self.refresh_recommendation(experiment_id)

    def save_candidate(self, experiment_id: str, candidate_id: str, config: dict, reasoning: dict):
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            experiment = connection.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
            if experiment and _load(experiment[0], {}).get('report_confirmation'):
                raise ValueError('报告已确认，不能改写候选配置')
            connection.execute("INSERT INTO candidate_configs VALUES (?, ?, ?, ?, ?, ?, ?)", (f"{experiment_id}-{candidate_id}", experiment_id, "generated", _json(config), _json(reasoning), _json({}), _now()))

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
        evaluated = sum(item["status"] in {'evaluated', 'failed'} for item in items)
        return {"round": number, "candidate_ids": [item["id"] for item in items], "evaluated": evaluated, "total": len(items), "complete": bool(items) and evaluated == len(items)}

    def round_completion(self, candidate: dict) -> dict:
        number = candidate.get("reasoning", {}).get("round")
        if not isinstance(number, int):
            return {"direct_or_legacy": True, "complete": True, "evaluated": 1, "total": 1}
        return self._round_summary(self.candidates(candidate["experiment_id"]), number)

    def finish_candidate(self, candidate_id: str, status: str, result: dict):
        with self.connection() as connection:
            connection.execute("UPDATE candidate_configs SET status = ?, result_json = ? WHERE id = ?", (status, _json(result), candidate_id))
        return self.candidate(candidate_id)

    def reserve_candidate_evaluation(self, candidate_id: str):
        """Reserve a real execution, not a result, under SQLite's writer lock."""
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            candidate = self.candidate(candidate_id)
            if not candidate or candidate['status'] not in {'generated', 'failed'}:
                raise ValueError('Candidate 已运行或正在执行')
            experiment = self.experiment(candidate['experiment_id'])
            is_d = candidate['reasoning'].get('candidate_label') == 'D'
            if experiment['result'].get('report_confirmation') and not is_d:
                raise ValueError('报告已确认，不能改变已确认的实验结果')
            used = experiment['evaluation_budget']['used']
            limit = MAX_EVALS if is_d else MAX_EVALS - 1
            if used >= limit:
                raise ValueError('Sandbox budget exhausted；D 保留一次额度')
            if is_d and not experiment['result'].get('report_confirmation'):
                raise ValueError('D 需要 Gate 2 报告确认')
            attempts = list(candidate['reasoning'].get('sandbox_attempts', []))
            attempts.append({'attempt': len(attempts) + 1, 'started_at': _now()})
            connection.execute("UPDATE candidate_configs SET status='running', reasoning_json=? WHERE id=?", (_json({**candidate['reasoning'], 'sandbox_attempts': attempts}), candidate_id))
        return self.candidate(candidate_id)

    def confirm_experiment_report(self, experiment_id: str, winner_id: str, actor: str):
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            experiment = self.experiment(experiment_id)
            if not experiment:
                raise ValueError('Experiment 不存在')
            if experiment['result'].get('report_confirmation'):
                raise ValueError('报告已确认')
            candidates = experiment['candidates']
            if any(item['status'] == 'running' for item in candidates):
                raise ValueError('仍有 Sandbox 运行中')
            winner = next((item for item in candidates if item['id'] == winner_id and item['reasoning'].get('candidate_label') in {'A', 'B', 'C'}), None)
            if not winner or winner['status'] != 'evaluated' or not winner['result'].get('qualification', {}).get('qualified'):
                raise ValueError('至少需要一个合格 A/B/C 赢家')
            if experiment['evaluation_budget']['used'] >= MAX_EVALS:
                raise ValueError('缺少 D 评测额度')
            confirmation = {'winner_id': winner_id, 'actor': actor, 'confirmed_at': _now(), 'candidates': [{'id': item['id'], 'status': item['status'], 'result': item['result'], 'config': item['config']} for item in candidates]}
            result = {**experiment['result'], 'report_confirmation': confirmation}
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?', (_json(result), experiment_id))
            connection.execute('INSERT INTO approvals(gate,target_id,decision,actor,created_at) VALUES (?,?,?,?,?)', ('experiment_report', experiment_id, 'approved', actor, _now()))
        self.refresh_recommendation(experiment_id)
        return confirmation

    def create_composite(self, experiment_id: str):
        from .policy import validate_candidate_config
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            experiment = self.experiment(experiment_id)
            confirmation = (experiment or {}).get('result', {}).get('report_confirmation')
            if not confirmation:
                raise ValueError('需要 Gate 2 报告确认')
            if experiment['result'].get('composite'):
                raise ValueError('本报告已生成 Composite 决策')
            winner = self.candidate(confirmation['winner_id'])
            baseline = self.evaluation_run(experiment['baseline_run_id'])
            base = {**DEFAULT_PIPELINE_CONFIG, **baseline['config']}
            config = dict(winner['config'])
            claimed = {key for key in config if config[key] != base.get(key)}
            sources, conflicts = [], []
            for item in experiment['candidates']:
                result = item['result']
                if item['id'] == winner['id'] or item['status'] != 'evaluated' or not result.get('regression', {}).get('passed') or result.get('target_bad_cases_fixed', 0) < 1:
                    continue
                diff = {key: value for key, value in item['config'].items() if value != base.get(key)}
                conflict = [key for key, value in diff.items() if key in claimed and config[key] != value]
                if conflict:
                    conflicts.append({'candidate_id': item['id'], 'parameters': conflict, 'resolution': 'retain_winner_or_prior_bundle'})
                    continue
                if not any(config.get(key) != value for key, value in diff.items()):
                    continue
                check = validate_candidate_config({**config, **diff})
                if not check['valid']:
                    conflicts.append({'candidate_id': item['id'], 'parameters': list(diff), 'resolution': 'incompatible_bundle', 'errors': check['errors']})
                    continue
                config.update(diff)
                claimed.update(diff)
                sources.append({'candidate_id': item['id'], 'parameter_diff': diff, 'why_merge': 'Observed case fixes and Regression PASS; bundle evidence, not per-parameter causality', 'qualification': result.get('qualification')})
            decision = {'winner_id': winner['id'], 'sources': sources, 'conflicts': conflicts, 'status': 'generated' if sources else 'no_effective_composite'}
            if sources:
                candidate_id = f'{experiment_id}-D'
                reasoning = {'candidate_label': 'D', 'hypothesis': 'Merge validated non-conflicting bundles', 'winner_id': winner['id'], 'sources': sources, 'conflicts': conflicts, 'changed_parameters': {key: value for key, value in config.items() if value != base.get(key)}}
                connection.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)', (candidate_id, experiment_id, 'generated', _json(config), _json(reasoning), '{}', _now()))
                decision['candidate_id'] = candidate_id
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?', (_json({**experiment['result'], 'composite': decision}), experiment_id))
        self.refresh_recommendation(experiment_id)
        return self.candidate(decision['candidate_id']) if sources else decision

    def refresh_recommendation(self, experiment_id: str):
        candidates = self.candidates(experiment_id)
        with self.connection() as connection:
            row = connection.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        state = _load(row[0], {}) if row else {}
        confirmation = state.get('report_confirmation')
        composite = state.get('composite')
        qualified = [item for item in candidates if item['status'] == 'evaluated' and item['result'].get('qualification', {}).get('qualified')]
        selected = None
        if any(item['status'] == 'running' for item in candidates):
            status = 'WAITING_FOR_ROUND_COMPLETION'
        elif not confirmation:
            status = 'Needs Report Confirmation' if qualified else 'No Qualified Candidate'
        elif not composite:
            status = 'Needs Composite'
        elif composite['status'] == 'no_effective_composite':
            status, selected = 'Recommended', confirmation['winner_id']
        else:
            d = self.candidate(composite['candidate_id'])
            if d['status'] in {'generated', 'running'}:
                status = 'Needs Composite Evaluation'
            else:
                promote = d['status'] == 'evaluated' and d['result'].get('qualification', {}).get('qualified') and d['result'].get('winner_comparison', {}).get('promote')
                status, selected = 'Recommended', d['id'] if promote else confirmation['winner_id']
        result = {'status': status, 'recommended_candidate': selected, 'report_confirmation': confirmation, 'composite': composite,
                  'why': 'D must improve the confirmed winner without new failures; otherwise retain the qualified winner.',
                  'pareto_frontier': [item['id'] for item in qualified if item['reasoning'].get('candidate_label') != 'D'],
                  'comparison': [{'candidate_id': item['id'], 'status': item['status'], **item['result'], 'parameter_diff': item['reasoning'].get('changed_parameters', {})} for item in candidates]}
        with self.connection() as connection:
            connection.execute('INSERT OR REPLACE INTO recommendations VALUES (?, ?, ?, ?, ?)', (experiment_id, selected, status, _json(result), _now()))
        return result

    def select_recommendation(self, experiment_id: str, candidate_id: str, actor: str):
        self.confirm_experiment_report(experiment_id, candidate_id, actor)
        return self.refresh_recommendation(experiment_id)

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
        if candidate.get('reasoning', {}).get('root_cause_cluster') == 'Human Direct Release':
            return 'V1.2 不允许绕过 Gate 2 报告确认及 D 决策'
        if candidate.get("reasoning", {}).get("candidate_label") not in {"A", "B", "C", 'D'}:
            return '仅允许已验证方案发布'
        recommendation = self.recommendation(candidate["experiment_id"])
        result = (recommendation or {}).get("result", {})
        if result.get("status") != "Recommended" or result.get("recommended_candidate") != candidate["id"]:
            return "需要 Gate 2 报告确认及 D 决策完成"
        return None

    def release_state(self, candidate: dict) -> dict:
        recommendation = (self.recommendation(candidate["experiment_id"]) or {}).get("result", {})
        return {"sandbox": candidate["status"] == "evaluated", "qualified": bool(candidate["result"].get("qualification", {}).get("qualified")), "recommended": recommendation.get("recommended_candidate") == candidate["id"], "human_release": (self.latest_approval("human_release", candidate["id"]) or {}).get("decision") == "approved", "round_complete": self.round_completion(candidate)["complete"]}

    def publish_candidate(self, candidate_id: str, actor: str):
        candidate = self.candidate(candidate_id)
        if candidate is None or candidate["status"] != "evaluated":
            raise ValueError("仅已完成 Sandbox 的 Candidate 可发布")
        if not candidate["result"].get("qualification", {}).get("qualified"):
            raise ValueError("Candidate 未通过 11/11 Gate、Regression 或有效提升要求，不能发布")
        if error := self.release_gate_error(candidate):
            raise ValueError(error)
        if not candidate["result"].get("gates", {}).get("passed") or not candidate["result"].get("regression", {}).get("passed"):
            raise ValueError("需要 11/11 Gate 与 Regression PASS")
        run = self.evaluation_run(candidate["result"]["evaluation_run_id"])
        if run is None or run["status"] != "completed":
            raise ValueError("Candidate Evaluation 未完成")
        version_id = f"production-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            experiment = connection.execute("SELECT baseline_run_id FROM experiments WHERE id=?", (candidate["experiment_id"],)).fetchone()
            self.require_current_baseline(experiment["baseline_run_id"], connection)
            if connection.execute("SELECT 1 FROM production_versions WHERE json_extract(snapshot_json, '$.candidate_id') = ?", (candidate_id,)).fetchone():
                raise ValueError("Candidate 已发布")
            row = connection.execute("SELECT status, result_json FROM candidate_configs WHERE id = ?", (candidate_id,)).fetchone()
            current_result = _load(row["result_json"], {}) if row else {}
            if row is None or row["status"] != "evaluated" or not current_result.get("qualification", {}).get("qualified"):
                raise ValueError("Candidate 发布资格已变化")
            if not current_result.get("gates", {}).get("passed") or not current_result.get("regression", {}).get("passed"):
                raise ValueError("11/11 Gate 或 Regression 已变化")
            if connection.execute("SELECT status FROM evaluation_runs WHERE id = ?", (run["id"],)).fetchone()["status"] != "completed":
                raise ValueError("Candidate Evaluation 已变化")
            candidate["result"] = current_result
            if error := self.release_gate_error(candidate):
                raise ValueError(error)
            recommendation = connection.execute("SELECT result_json FROM recommendations WHERE experiment_id = ?", (candidate["experiment_id"],)).fetchone()
            selected = _load(recommendation["result_json"], {}) if recommendation else {}
            if not self.round_completion(candidate).get("direct_or_legacy") and (selected.get("status") != "Recommended" or selected.get("recommended_candidate") != candidate_id):
                raise ValueError("Recommendation 已变化")
            previous = self.active_production()
            release = {"gate": "human_release", "target_id": candidate_id, "decision": "approved", "actor": actor, "created_at": _now()}
            approval = connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (release["gate"], candidate_id, release["decision"], actor, release["created_at"]))
            release["id"] = approval.lastrowid
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

    def record_monitoring_event(self, *, question: str, answer: str, bad_case: bool, severity: str, determinable: bool, metrics: dict | None = None, source: dict | None = None):
        if severity not in {"ordinary", "critical"}:
            raise ValueError("Unsupported monitoring severity")
        if not question.strip() or not answer.strip():
            raise ValueError("Monitoring requires a complete question and answer")
        production = self.active_production()
        provenance = source or {"production_version_id": production["id"] if production else None, "production_config": production["config"] if production else None, "corpus_fingerprint": current_manifest()["sources"]}
        event_id = f"MON-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO monitoring_events (id, question, answer, bad_case, severity, determinable, created_at, metrics_json, source_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, question.strip(), answer.strip(), int(bool(bad_case)), severity, int(bool(determinable)), _now(), _json(metrics) if metrics is not None else None, _json(provenance)),
            )
        event = {"id": event_id, "question": question.strip(), "answer": answer.strip(), "bad_case": bool(bad_case), "severity": severity, "determinable": bool(determinable), "metrics": metrics, "source": provenance}
        self._create_monitoring_trigger_if_needed(event)
        return event

    def monitoring_events(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM monitoring_events ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "bad_case": bool(row["bad_case"]), "determinable": bool(row["determinable"]), "metrics": _load(row["metrics_json"], None), "source": _load(row["source_json"], {})} for row in rows]

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
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM optimization_triggers WHERE id = ?", (trigger_id,)).fetchone()
            if row is None:
                raise KeyError(trigger_id)
            if row["status"] == "human_confirmed" and row["optimization_run_id"]:
                return dict(row)
            if row["status"] != "pending_human_confirm":
                raise ValueError("Trigger is not pending human confirmation")
            baseline = self.require_current_baseline(connection=connection)
            experiment_id = f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            event = connection.execute("SELECT * FROM monitoring_events WHERE id=?", (row["event_id"],)).fetchone()
            context = {"trigger_id": trigger_id, "round": 0, "baseline_id": baseline["id"], "golden_id": baseline["dataset_version_id"], "corpus_fingerprint": _load(baseline["dataset_snapshot_json"], {}).get("corpus_fingerprint"), "baseline_config": baseline["config"], "monitoring_event": {**dict(event), "source": _load(event["source_json"], {}), "metrics": _load(event["metrics_json"], None)} if event else None}
            connection.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?)", (experiment_id, baseline["id"], "pending_agent", _json(context), _now()))
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
        return {**dict(row), "result": _load(row["result_json"], {}), "candidates": [{**item, "release_state": self.release_state(item)} for item in items], "rounds": [self._round_summary(items, number) for number in numbers], "evaluation_budget": {"used": sum(len(item['reasoning'].get('sandbox_attempts', [])) or int(item['status'] in {'evaluated', 'failed', 'running'}) for item in items), "max": MAX_EVALS, 'reserved_for_d': 1}}

    def latest_experiment(self):
        with self.connection() as connection:
            row = connection.execute("SELECT id FROM experiments ORDER BY created_at DESC LIMIT 1").fetchone()
        return self.experiment(row["id"]) if row else None
