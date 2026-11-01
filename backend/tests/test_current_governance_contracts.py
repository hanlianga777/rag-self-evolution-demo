"""Current guard semantics, isolated fixtures only; old conflicting tests remain intact."""
from copy import deepcopy
import unittest
import test_baseline_resume as resume_fixture
import test_generation_partial_slots as generation_fixture
from app.evaluation import summarize_evaluation_cases


class CurrentGovernanceContracts(unittest.TestCase):
    def test_unknown_request_blocks_child_creation_and_preserves_checkpoint_history(self):
        holder = resume_fixture.ResumeTests(); holder.setUp(); self.addCleanup(holder.tearDown)
        key, items, config = holder.runner.start_baseline()
        execution = holder.runtime.answer('Q1', config)
        holder.store.update_evaluation_progress(key, {'checkpoints':{'Q1':{'execution':execution, 'attempts':[], 'inflight':'judge'}}})
        holder.store.interrupt_evaluation_runs()
        before = deepcopy(holder.store.evaluation_runs())
        with self.assertRaisesRegex(ValueError, 'Unknown request execution'):
            holder.runner.start_baseline(key)
        self.assertEqual(holder.store.evaluation_runs(), before)
        self.assertEqual(len(holder.store.evaluation_runs()), 1)
        self.assertEqual(holder.store.evaluation_run(key)['result']['checkpoints']['Q1']['execution'], execution)
        self.assertEqual(holder.runtime.judges, [])

    def test_machine_qualified_without_review_remains_pending_and_unfrozen(self):
        holder = generation_fixture.PartialGenerationTests(); holder.setUp(); self.addCleanup(holder.doCleanups)
        key = holder.store.start_generation_run('mock-provider', 'mini')
        generated = holder.service.generate_mini_golden(holder.chunks)
        holder.store.save_mini_golden_candidates(generated['valid_slots'], 'mock-provider',
            coverage_plan=generated['coverage_plan'], hard_validation=generated['hard_validation'], run_id=key)
        holder.store.update_generation_run(key, status='completed')
        for question_id in holder.store.generation_run(key)['question_ids']:
            holder.passed_probe(question_id)
            holder.store.record_qc(question_id, {'score':95,'priority':'P2','reason':'offline fixture'}, 'passed')
        gate = holder.store.generation_run(key)['human_gate']
        self.assertEqual(gate['machine_qualified'], 20)
        self.assertEqual(gate['approved'], 0)
        self.assertEqual(gate['status'], 'pending')
        self.assertEqual(holder.store.dataset_snapshots(), [])
        self.assertTrue(all(not holder.store.review_history(qid) for qid in holder.store.generation_run(key)['question_ids']))

    def test_partial_bad_case_total_is_unknown_with_explicit_observed_count(self):
        case = {'test_category':'positive', 'passed':False,
                'judge_result':{'correctness':0,'faithfulness':0,'completeness':0},
                'programmatic_metrics':{'latency_ms':1}}
        for cases, observed in (([], 0), ([case], 1)):
            with self.subTest(observed=observed):
                result = summarize_evaluation_cases(cases, complete=False)
                self.assertIsNone(result['bad_case_count'])
                self.assertEqual(result['partial_bad_case_count'], observed)
                self.assertIsNone(result['overall_score'])
                self.assertEqual(result['overall_score_status'], 'NOT_EVALUABLE')
                self.assertIsNone(result['gates']['passed'])
                self.assertEqual([gate['status'] for gate in result['gates']['gates']], ['NOT_EVALUABLE'] * 11)
