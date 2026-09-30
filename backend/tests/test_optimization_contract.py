"""Fixed-provider checks for the V1.3 Optimization Agent contract."""

import json
import tempfile
import unittest
from pathlib import Path

from identity_fixture import completed_baseline
from app.governance import GovernanceStore
from app.optimization import OptimizationAgent
from app.policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, EXCLUDED_AUTOMATIC_PARAMETERS, search_space_contract, validate_candidate_config


def drafts():
    return {"root_cause_cluster": "coverage", "observed_evidence": ["case-1"], "candidates": [
        {"id": "A", "hypothesis": "depth", "why": "more evidence", "target_bad_cases": ["case-1"], "config_diff": {"top_k": 6}, "risk": "latency"},
        {"id": "B", "hypothesis": "noise", "why": "filter", "target_bad_cases": ["case-1"], "config_diff": {"min_score": 0.1}, "risk": "recall"},
        {"id": "C", "hypothesis": "coverage", "why": "more candidates", "target_bad_cases": ["case-1"], "config_diff": {"candidate_k": 24}, "risk": "latency"},
    ]}


class FixedProvider:
    def __init__(self, response):
        self.response = response
        self.prompt = None

    def complete(self, system, prompt, **kwargs):
        self.prompt = json.loads(prompt)
        assert kwargs["json_mode"] is True
        assert "config_diff" in system
        return self.response


class OptimizationContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GovernanceStore(Path(self.directory.name) / "demo.db")
        completed_baseline(self.store, run_id="EVAL-test")
        self.store.record_bad_case("EVAL-test", "Q1", "Generation", "medium", {"reason": "failed"})

    def run_drafts(self, result):
        # Each response is an independent first round; incomplete real rounds remain blocked.
        self.store = GovernanceStore(Path(self.directory.name) / f"contract-{len(list(Path(self.directory.name).glob('*.db')))}.db")
        completed_baseline(self.store, run_id="EVAL-test")
        raw = json.dumps(result, ensure_ascii=False)
        provider = FixedProvider(raw)
        try:
            experiment = OptimizationAgent(self.store, provider).generate("EVAL-test")
        except ValueError:
            experiment = self.store.latest_experiment()
        with self.store.connection() as connection:
            trace = connection.execute("SELECT * FROM agent_traces WHERE experiment_id=? ORDER BY id DESC LIMIT 1", (experiment["id"],)).fetchone()
        return experiment, dict(trace), json.loads(trace["result_json"]), provider, raw

    def test_valid_a_b_c_and_prompt_share_policy_values(self):
        experiment, trace, audit, provider, raw = self.run_drafts(drafts())
        self.assertEqual(trace["status"], "completed")
        self.assertEqual(len(experiment["candidates"]), 3)
        self.assertEqual(experiment["candidates"][0]["reasoning"]["proposal"], "more evidence")
        self.assertEqual(experiment["candidates"][0]["reasoning"]["observed_evidence"], ["case-1"])
        self.assertEqual(audit["provider_raw_text"], raw)
        self.assertEqual(provider.prompt["allowed_parameter_values"], search_space_contract())
        self.assertEqual(set(provider.prompt["allowed_parameter_values"]), set(ALLOWED_SEARCH_SPACE))
        self.assertEqual(provider.prompt["excluded_automatic_parameters"], sorted(EXCLUDED_AUTOMATIC_PARAMETERS))
        self.assertEqual(provider.prompt["allowed_parameter_values"]["multi_query"], {"type": "boolean false or integer", "allowed": [False, 2, 4, 6]})

    def test_bad_candidate_k_preserves_full_failed_trace_without_partial_candidates(self):
        result = drafts()
        result["candidates"][1]["config_diff"]["candidate_k"] = "32"
        experiment, trace, audit, _, raw = self.run_drafts(result)
        self.assertEqual(trace["status"], "failed")
        self.assertEqual(experiment["candidates"], [])
        self.assertEqual(audit["optimization_run_id"], experiment["id"])
        self.assertEqual(audit["baseline_id"], "EVAL-test")
        self.assertEqual(audit["provider_raw_text"], raw)
        self.assertEqual(audit["parsed_json"], result)
        self.assertEqual(audit["parsed_candidates"], result["candidates"])
        self.assertEqual(audit["validation_stage"], "search_space")
        self.assertEqual(audit["failed_candidate_id"], "B")
        self.assertEqual(audit["failed_field"], "candidate_k")
        self.assertEqual(audit["actual_value"], "32")
        self.assertEqual(audit["expected_type"], "integer")
        self.assertEqual(audit["allowed_values"], [12, 24])
        self.assertIn("invalid candidate_k", audit["validation_error"])
        self.assertTrue(audit["timestamp"])

    def test_strict_types_and_discrete_values(self):
        for field, value, valid in (
            ("top_k", True, False), ("top_k", False, False), ("top_k", 4, True),
            ("candidate_k", True, False), ("multi_query", False, True),
            ("multi_query", 2, True), ("multi_query", 4, True), ("multi_query", 6, True),
            ("multi_query", True, False), ("multi_query", 0, False), ("multi_query", "4", False),
            ("min_score", False, False), ("hybrid_alpha", True, False),
            ("metadata_filter", "OFF", True), ("metadata_filter", False, False), ("metadata_filter", "INVALID", False),
        ):
            with self.subTest(field=field, value=value):
                check = validate_candidate_config({**DEFAULT_PIPELINE_CONFIG, field: value})
                self.assertEqual(check["valid"], valid)
                if not valid:
                    self.assertEqual(check["issues"][0]["field"], field)

    def test_hybrid_off_and_dependency(self):
        result = drafts()
        result["candidates"][0]["config_diff"] = {"hybrid_search": False}
        experiment, trace, _, _, _ = self.run_drafts(result)
        self.assertEqual(trace["status"], "completed")
        self.assertNotIn("hybrid_alpha", experiment["candidates"][0]["config"])

        result = drafts()
        result["candidates"][0]["config_diff"] = {"hybrid_search": False, "hybrid_alpha": 0.5}
        _, trace, audit, _, _ = self.run_drafts(result)
        self.assertEqual(trace["status"], "failed")
        self.assertEqual(audit["failed_field"], "hybrid_alpha")

    def test_cross_field_duplicate_and_excluded_checks(self):
        for diff, expected in (
            ({"candidate_k": 4, "top_k": 6}, "candidate_k must be greater than or equal to top_k"),
            ({"top_k": 6, "temperature": 0.8}, "excluded automatic parameters"),
            ({"top_k": 6, "new_parameter": 1}, "unsupported parameters"),
        ):
            with self.subTest(diff=diff):
                result = drafts()
                result["candidates"][0]["config_diff"] = diff
                experiment, trace, audit, _, _ = self.run_drafts(result)
                self.assertEqual(trace["status"], "failed")
                self.assertEqual(experiment["candidates"], [])
                self.assertIn(expected, audit["validation_error"])
        result = drafts()
        result["candidates"][1]["config_diff"] = {"top_k": 6}
        experiment, trace, audit, _, _ = self.run_drafts(result)
        self.assertEqual(trace["status"], "failed")
        self.assertEqual(experiment["candidates"], [])
        self.assertIn("duplicate candidate configuration", audit["validation_error"])

    def test_json_parse_failure_retains_raw_text(self):
        provider = FixedProvider("{broken")
        with self.assertRaises(ValueError):
            OptimizationAgent(self.store, provider).generate("EVAL-test")
        experiment = self.store.latest_experiment()
        self.assertEqual(experiment["result"]["provider_raw_text"], "{broken")
        self.assertIsNone(experiment["result"]["parsed_json"])
        self.assertEqual(experiment["result"]["validation_stage"], "json_parse")


if __name__ == "__main__":
    unittest.main()
