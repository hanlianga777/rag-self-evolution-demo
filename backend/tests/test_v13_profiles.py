"""Profile counts are frozen per generation run and do not assume Mini."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.ai_service import AiService
from app.governance import GENERATION_PROFILES, GovernanceStore


class ProfileTests(unittest.TestCase):
    def test_run_counts_and_invalid_profile(self):
        with tempfile.TemporaryDirectory() as folder, patch("app.corpus.current_manifest", return_value={"sources": {}}):
            for name, counts in (("mini", (8, 4, 8, 20)), ("medium", (20, 10, 20, 50)), ("full", (40, 20, 40, 100))):
                with self.subTest(name=name):
                    store = GovernanceStore(Path(folder) / f"{name}.db")
                    run = store.generation_run(store.start_generation_run("fixture", name))
                    self.assertEqual(tuple(run["profile"][key] for key in ("positive_count", "ablation_count", "negative_count", "expected_count")), counts)
                    self.assertEqual(store._expected_count(run), counts[-1])
            with self.assertRaises(ValueError):
                store.start_generation_run("fixture", "unknown")

    def test_legacy_mini_profile_is_readable(self):
        self.assertEqual(GovernanceStore._expected_count({"profile": {"positive": 8, "ablation": 4, "negative": 8}}), 20)

    def test_coverage_plan_uses_each_profile_quota(self):
        chunks = [{"document_id": "D", "chunk_id": f"C{i:03d}", "chunk_text": f"设备维护步骤 {i}"} for i in range(98)]
        embeddings = np.eye(98, dtype="float32")
        for name, profile in GENERATION_PROFILES.items():
            with self.subTest(profile=name):
                plan = AiService._mini_coverage_plan(chunks, embeddings, profile)
                self.assertEqual(len(plan), profile["expected_count"])
                self.assertEqual([sum(item["test_category"] == category for item in plan) for category in ("positive", "ablation", "negative")], [profile[f"{category}_count"] for category in ("positive", "ablation", "negative")])
                self.assertEqual(len({item["slot"] for item in plan}), len(plan))
