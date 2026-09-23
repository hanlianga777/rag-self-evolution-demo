import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from app import governance
from app.governance import GovernanceStore


def mini_candidates():
    return [
        {
            "test_category": category,
            "question": f"{category}-{index}",
            "reference_answer": "证据答案" if category != "negative" else None,
            "expected_behavior": "insufficient_evidence" if category == "negative" else None,
            "evidence": [{"source_chunk_ids": ["C1"], "evidence_key_points": ["支持"]}] if category != "negative" else [],
            "negative_subtype": "unanswerable" if category == "negative" else None,
            "ablation_attribute": "检索参数" if category == "ablation" else None,
        }
        for category, count in (("positive", 8), ("ablation", 4), ("negative", 8))
        for index in range(count)
    ]


class LegacyGenerationStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "legacy.db"

    def test_draft_seed_uses_named_columns_with_qc_at_end_and_snapshot_already_present(self):
        with sqlite3.connect(self.path) as connection:
            connection.execute("""CREATE TABLE questions (
                id TEXT PRIMARY KEY, stage TEXT NOT NULL, legacy_question_type TEXT NOT NULL,
                test_category TEXT NOT NULL, negative_subtype TEXT, review_status TEXT NOT NULL,
                probe_status TEXT NOT NULL, question TEXT NOT NULL, reference_answer TEXT,
                evidence_json TEXT NOT NULL, raw_json TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            connection.execute("ALTER TABLE questions ADD COLUMN qc_status TEXT NOT NULL DEFAULT 'qc_pending'")
            connection.execute("""CREATE TABLE production_versions (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, config_json TEXT NOT NULL,
                evaluation_run_id TEXT, dataset_version_id TEXT, approval_id INTEGER,
                previous_version_id TEXT, created_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL DEFAULT '{}')""")

        store = GovernanceStore(self.path)

        self.assertEqual(store.question("GGC-001")["question"], store.question("GGC-001")["raw"]["question"])
        self.assertEqual(store.question("GGC-001")["qc_status"], "qc_pending")
        self.assertEqual(store.question("GGC-001")["probe_status"], "probe_pending")
        self.assertEqual(store.active_production()["id"], "baseline-v1")
        self.assertEqual(store.active_production()["snapshot"], {})

    def test_generated_groups_use_named_columns_with_qc_at_end(self):
        store = GovernanceStore(self.path)
        with sqlite3.connect(self.path) as connection:
            connection.execute("ALTER TABLE questions RENAME TO questions_original")
            connection.execute("""CREATE TABLE questions (
                id TEXT PRIMARY KEY, stage TEXT NOT NULL, legacy_question_type TEXT NOT NULL,
                test_category TEXT NOT NULL, negative_subtype TEXT, review_status TEXT NOT NULL,
                probe_status TEXT NOT NULL, question TEXT NOT NULL, reference_answer TEXT,
                evidence_json TEXT NOT NULL, raw_json TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, qc_status TEXT NOT NULL DEFAULT 'qc_pending')""")
            connection.execute("""INSERT INTO questions (
                id, stage, legacy_question_type, test_category, negative_subtype, review_status,
                probe_status, question, reference_answer, evidence_json, raw_json, created_at,
                updated_at, qc_status)
                SELECT id, stage, legacy_question_type, test_category, negative_subtype, review_status,
                probe_status, question, reference_answer, evidence_json, raw_json, created_at,
                updated_at, qc_status FROM questions_original""")
            connection.execute("DROP TABLE questions_original")

        rows = store.save_mini_golden_candidates(mini_candidates(), "test-model")

        self.assertEqual([sum(row["test_category"] == category for row in rows) for category in ("positive", "ablation", "negative")], [8, 4, 8])
        for row in rows:
            self.assertEqual(row["question"], row["raw"]["question"])
            self.assertEqual(row["qc_status"], "qc_pending")
            self.assertEqual(row["probe_status"], "probe_pending")
            self.assertEqual(row["stage"], "candidate")
        self.assertEqual(next(row for row in rows if row["test_category"] == "ablation")["raw"]["ablation_attribute"], "检索参数")
        negative = next(row for row in rows if row["test_category"] == "negative")
        self.assertEqual(negative["raw"]["expected_behavior"], "insufficient_evidence")
        self.assertIsNone(negative["reference_answer"])
        self.assertEqual(negative["evidence"], [])
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT reference_answer, evidence_json FROM questions WHERE id = ?", (negative["id"],)).fetchone(), (None, "[]"))

    def test_snapshot_column_repairs_even_when_migration_marker_exists(self):
        GovernanceStore(self.path)
        with sqlite3.connect(self.path) as connection:
            connection.execute("ALTER TABLE production_versions DROP COLUMN snapshot_json")
            self.assertIsNotNone(connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'v101-governance-results'").fetchone())

        store = GovernanceStore(self.path)

        self.assertEqual(store.active_production()["snapshot"], {})
        with sqlite3.connect(self.path) as connection:
            self.assertIn("snapshot_json", [column[1] for column in connection.execute("PRAGMA table_info(production_versions)")])

    def test_candidate_persistence_failure_records_stage_and_leaves_no_partial_questions(self):
        store = GovernanceStore(self.path)
        run_id = store.start_generation_run("test-model")
        candidates = mini_candidates()
        candidates[-1]["question"] = ""

        class GeneratedService:
            model = "test-model"

            def generate_mini_golden(self, _chunks, on_progress):
                return {"status": "passed", "candidates": candidates, "coverage_plan": [], "hard_validation": {}, "slot_audit": {}}

        class EmptyCorpus:
            def chunks(self):
                return []

        with patch.object(governance, "DEFAULT_DATABASE", Path(self.directory.name) / "import.db"):
            from app.main import _run_mini_generation

        _run_mini_generation(run_id, store, GeneratedService(), EmptyCorpus())

        run = store.generation_run(run_id)
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["artifacts"]["hard_validation"]["failed_stage"], "candidate_persistence")
        self.assertEqual(run["question_ids"], [])
        self.assertEqual([item for item in store.questions() if item["legacy_question_type"] == "v1_mini"], [])

    def test_generation_progress_counts_qc_skipped_only_for_failed_probes(self):
        store = GovernanceStore(self.path)
        run_id = store.start_generation_run("test-model")

        class GeneratedService:
            model = "test-model"
            retriever = None
            answerability_check = None

            def generate_mini_golden(self, _chunks, on_progress):
                return {"status": "passed", "candidates": mini_candidates(), "coverage_plan": [], "hard_validation": {}, "slot_audit": {}}

            def quality_check(self, _candidate):
                return {"score": 90}

        class EmptyCorpus:
            def chunks(self):
                return []

        with patch.object(governance, "DEFAULT_DATABASE", Path(self.directory.name) / "import.db"):
            from app.main import _run_mini_generation

        probe_results = [{"status": "failed"}] + [{"status": "passed"}] * 19
        with patch.object(store, "run_probe", side_effect=probe_results), patch.object(store, "record_qc"):
            _run_mini_generation(run_id, store, GeneratedService(), EmptyCorpus())

        run = store.generation_run(run_id)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["artifacts"]["hard_validation"]["progress"]["qc_completed"], 19)
        self.assertEqual(run["artifacts"]["hard_validation"]["progress"]["qc_skipped"], 1)


if __name__ == "__main__":
    unittest.main()
