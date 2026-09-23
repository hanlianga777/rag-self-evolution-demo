import unittest

from app.policy import (
    DEFAULT_PIPELINE_CONFIG,
    GATE_DEFINITIONS,
    MAX_EVALS,
    canonicalize_config,
    calculate_overall_score,
    evaluate_gates,
    evaluate_regression,
    qualify_candidate,
    validate_candidate_config,
)


PASSING_METRICS = {
    "positive_correctness": 80,
    "positive_faithfulness": 80,
    "positive_completeness": 75,
    "ablation_correctness": 70,
    "ablation_faithfulness": 75,
    "ablation_completeness": 65,
    "safe_rejection_rate": 95,
    "safety_critical_accuracy": 95,
    "prompt_injection_resistance": 95,
    "latency_p50_seconds": 25,
    "latency_p99_seconds": 60,
}


class FinalPolicyTests(unittest.TestCase):
    def test_gate_definitions_are_exactly_the_frozen_eleven(self):
        self.assertEqual(len(GATE_DEFINITIONS), 11)
        self.assertEqual([gate["metric"] for gate in GATE_DEFINITIONS], list(PASSING_METRICS))

    def test_overall_score_is_equal_quality_average_and_excludes_diagnostics(self):
        metrics = {**PASSING_METRICS, "ttft_seconds": 999, "token_cost": 999, "recall_at_k": 0, "precision_at_k": 0, "mrr": 0}
        result = calculate_overall_score(metrics)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["score"], 81.1)
        self.assertEqual(result["included_metrics"], [gate["metric"] for gate in GATE_DEFINITIONS[:9]])
        self.assertNotIn("ttft_seconds", result["included_metrics"])

    def test_missing_gate_metric_is_not_evaluable_and_fails(self):
        result = evaluate_gates({key: value for key, value in PASSING_METRICS.items() if key != "latency_p99_seconds"})

        self.assertFalse(result["passed"])
        self.assertEqual(result["passed_count"], 10)
        self.assertEqual(result["gates"][-1]["status"], "NOT_EVALUABLE")

    def test_regression_allows_no_new_critical_and_at_most_one_ordinary(self):
        self.assertTrue(evaluate_regression(new_critical_failures=0, new_ordinary_failures=1)["passed"])
        self.assertFalse(evaluate_regression(new_critical_failures=1, new_ordinary_failures=0)["passed"])
        self.assertFalse(evaluate_regression(new_critical_failures=0, new_ordinary_failures=2)["passed"])

    def test_candidate_qualification_requires_all_release_conditions(self):
        gates = evaluate_gates(PASSING_METRICS)
        regression = evaluate_regression(new_critical_failures=0, new_ordinary_failures=0)
        result = qualify_candidate(gates, regression, target_bad_cases_fixed=1, baseline_bad_case_count=4, candidate_bad_case_count=3)

        self.assertTrue(result["qualified"])
        self.assertEqual(result["status"], "QUALIFIED")
        self.assertFalse(qualify_candidate(gates, regression, 0, 4, 3)["qualified"])

    def test_config_is_canonical_and_rejects_dependencies_exclusions_duplicates_and_budget(self):
        config = {
            "top_k": 6,
            "candidate_k": 24,
            "hybrid_search": True,
            "hybrid_alpha": 0.7,
            "rerank": False,
            "query_rewrite": True,
            "multi_query": 2,
            "hyde": False,
            "metadata_filter": "FALLBACK",
            "alias_mapping": True,
            "prompt_strategy": "Grounded",
            "min_score": 0.2,
        }
        canonical = canonicalize_config(config)
        self.assertEqual(canonical, canonicalize_config(dict(reversed(list(config.items())))))
        self.assertTrue(validate_candidate_config(config, prior_configs=[], completed_evals=MAX_EVALS - 1)["valid"])
        self.assertFalse(validate_candidate_config({**config, "hybrid_search": False, "hybrid_alpha": 0.7})["valid"])
        hybrid_off = {key: value for key, value in config.items() if key != "hybrid_alpha"}
        hybrid_off["hybrid_search"] = False
        self.assertTrue(validate_candidate_config(hybrid_off)["valid"])
        self.assertFalse(validate_candidate_config({**config, "rerank_top_n": 10})["valid"])
        self.assertFalse(validate_candidate_config(config, prior_configs=[config])["valid"])
        self.assertFalse(validate_candidate_config(config, completed_evals=MAX_EVALS)["valid"])

    def test_default_configuration_is_the_frozen_baseline(self):
        self.assertEqual(DEFAULT_PIPELINE_CONFIG["candidate_k"], 12)
        self.assertEqual(DEFAULT_PIPELINE_CONFIG["top_k"], 4)
        self.assertEqual(DEFAULT_PIPELINE_CONFIG["hybrid_alpha"], 0.5)
        self.assertTrue(DEFAULT_PIPELINE_CONFIG["hybrid_search"])
        self.assertTrue(DEFAULT_PIPELINE_CONFIG["rerank"])


if __name__ == "__main__":
    unittest.main()
