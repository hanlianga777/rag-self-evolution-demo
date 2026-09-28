import unittest

from app.evaluation import gate_details, summarize_evaluation_cases


class GateDetailTests(unittest.TestCase):
    def test_details_use_the_same_case_inputs_as_aggregation(self):
        cases = [
            {"question_id": "Q01", "test_category": "positive", "judge_result": {"correctness": 4, "faithfulness": 1, "completeness": 1}, "programmatic_metrics": {"latency_ms": 1000}, "passed": True},
            {"question_id": "Q02", "test_category": "positive", "judge_result": {"correctness": 2, "faithfulness": .5, "completeness": .5}, "programmatic_metrics": {"latency_ms": 3000}, "passed": False},
            {"question_id": "Q03", "test_category": "negative", "negative_subtype": "prompt_injection", "severity": "critical", "judge_result": {"behavior_pass": False}, "programmatic_metrics": {"latency_ms": 2000}, "passed": False},
        ]
        gates = summarize_evaluation_cases(cases)["gates"]["gates"]
        details = gate_details(cases, gates)
        self.assertEqual([item["metric"] for item in details], [item["metric"] for item in gates])
        self.assertEqual(details[0]["actual"], 75)
        self.assertEqual([item["value"] for item in details[0]["contributing_cases"]], [100, 50])
        self.assertEqual([item["question_id"] for item in details[0]["failed_cases"]], ["Q02"])
        self.assertEqual(details[6]["contributing_cases"][0]["value"], 0)
        self.assertEqual(details[9]["included_cases"], 3)
