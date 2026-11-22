"""109c contract checks with a disposable SQLite database and fixed Provider replies."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from app.agent_strategy import conclude_round
from app.governance import GovernanceStore
from app.optimization import OptimizationAgent
from identity_fixture import completed_baseline
from test_optimization_contract import drafts, trace_case


class DecisionContractTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = GovernanceStore(Path(directory.name) / 'test.db')
        self.baseline = 'EVAL-109c'
        completed_baseline(self.store, run_id=self.baseline)
        baseline = self.store.evaluation_run(self.baseline)
        with self.store.connection() as db:
            db.execute("UPDATE evaluation_runs SET config_json=json_set(config_json,'$.knowledge_identity',json(?)) WHERE id=?",
                       (json.dumps(json.loads(baseline['dataset_snapshot_json'])['corpus_fingerprint']), self.baseline))
        self.store.record_bad_case(self.baseline, 'Q1', 'Retrieval', 'ordinary', trace_case())
        pause = patch('app.optimization.wait_for_off_peak')
        pause.start()
        self.addCleanup(pause.stop)
        self.provider = Mock(spec=['complete'], side_effect=None)
        self.provider.complete.side_effect = self.reply

    def reply(self, system, user, **kwargs):
        prompt = json.loads(user)
        output = drafts()
        output['prior_round_review']['summary'] = '无'
        output['bad_case_summary'] = {'groups':prompt['bad_case_groups'], 'focus':'查找证据',
                                      'conclusions':[{'id':'B1', 'conclusion':'有证据缺口'}]}
        for row in output['candidates']:
            row.update(bad_case_conclusion_ids=['B1'], predicted_fixed_question_ids=['Q1'],
                       adjustments=[{'parameter':k,'candidate_value':v,'expected_impact':'预计修好Q1'}
                                    for k,v in row['config_diff'].items()],
                       risks=[{'question_ids':[],'metric':'时延','reason':'可能变慢'}])
        return json.dumps(output, ensure_ascii=False)

    def generate(self, experiment_id=None):
        return OptimizationAgent(self.store, self.provider).generate(self.baseline, experiment_id=experiment_id)

    def test_empty_contract_refuses_before_provider_or_candidate_write(self):
        experiment_id = self.store.create_experiment(self.baseline)
        with self.store.connection() as db:
            db.execute("UPDATE experiments SET result_json=json_set(result_json,'$.strategy_contract',NULL) WHERE id=?", (experiment_id,))
        with self.assertRaisesRegex(ValueError, 'strategy_contract'):
            self.generate(experiment_id)
        self.provider.complete.assert_not_called()
        self.assertEqual(self.store.experiment(experiment_id)['status'], 'analyzing')
        self.assertEqual(self.store.experiment(experiment_id)['candidates'], [])

    def test_first_round_saves_contract_group_focus_conclusions_and_predictions(self):
        result = self.generate()
        self.assertEqual(result['result']['strategy_contract'], 'agent-strategy-4')
        prompt = json.loads(self.provider.complete.call_args.args[1])
        saved = result['result']['agent_strategies']['1']['bad_case_summary']
        self.assertEqual(saved['groups'], prompt['bad_case_groups'])
        self.assertEqual(saved['focus'], '查找证据')
        self.assertEqual(saved['conclusions'][0]['id'], 'B1')
        self.assertEqual(len(result['candidates']), 3)
        for row in result['candidates']:
            self.assertEqual(row['reasoning']['bad_case_conclusion_ids'], ['B1'])
            self.assertEqual(row['reasoning']['predicted_fixed_question_ids'], ['Q1'])

    def second_round(self, decisions, *, repeated=True):
        first = self.generate()
        experiment_id = first['id']
        first_a = first['candidates'][0]
        with self.store.connection() as db:
            db.execute("UPDATE candidate_configs SET status='evaluated',result_json=? WHERE experiment_id=?",
                       (json.dumps({'evaluation_complete':True,'all_fixed_question_ids':[]}), experiment_id))
        review_provider = Mock(spec=['complete'])
        review_provider.complete.return_value = json.dumps({
            'plans': [{'candidate_id':c['id'], 'unmatched_reason':'证据没有改善',
                       'parameter_assessment':'无效' if c['id']==first_a['id'] else '不确定',
                       'evidence_reason':'保存的结果', 'conclusion':'未修好'}
                      for c in first['candidates']],
            'lessons':['先处理证据位置。','比较上轮和本轮的前提。'],
        })
        with patch('app.paid_schedule.wait_for_off_peak'):
            review = conclude_round(self.store, SimpleNamespace(provider=review_provider), experiment_id)
        self.assertEqual(review['prediction_comparison']['by_direction']['检索方向'], {'hits':0,'predictions':3})
        self.assertEqual(review['prediction_comparison']['rows'][0]['predicted_fixed_question_ids'], ['Q1'])
        self.assertEqual(review['prediction_comparison']['rows'][0]['actual_fixed_question_ids'], [])

        def second_reply(system, user, **kwargs):
            prompt = json.loads(user)
            response = json.loads(self.reply(system, user, **kwargs))
            response['prior_round_review'].update(summary='对照上轮保存结果', plans=[
                {'candidate_id':c['id'], 'changes':c['reasoning']['changed_parameters'],
                 'fixed_question_ids':[], 'new_failure_question_ids':[],
                 'evidence_reason':'未修好', 'conclusion':'未修好'} for c in first['candidates']
            ])
            changes = [{'top_k':8} if repeated else {'top_k':2}, {'min_score':0.02}, {'candidate_k':8}]
            for candidate, diff in zip(response['candidates'], changes):
                candidate.update(config_diff=diff, hypothesis=candidate['hypothesis']+'重新试验')
                candidate['adjustments'] = [{'parameter':k,'candidate_value':v,'expected_impact':'预计修好Q1'} for k,v in diff.items()]
            response['history_decisions'] = decisions(prompt['history_lessons'], prompt['prior_parameter_findings'])
            return json.dumps(response, ensure_ascii=False)

        self.provider.complete.side_effect = second_reply
        return experiment_id

    @staticmethod
    def reject_lessons(lessons, findings):
        return [{'lesson':lesson,'decision':'拒绝','reason':'原配置和结果已明确','affected_candidates':[]}
                for lesson in lessons]

    def test_missing_lesson_rejects_round(self):
        experiment_id = self.second_round(lambda lessons, findings: self.reject_lessons(lessons, findings)[1:])
        with self.assertRaisesRegex(ValueError, 'lesson.*覆盖'):
            self.generate(experiment_id)
        self.assertEqual(len(self.store.experiment(experiment_id)['candidates']), 3)

    def test_repeating_failed_direction_without_exception_rejects_round(self):
        experiment_id = self.second_round(self.reject_lessons)
        with self.assertRaisesRegex(ValueError, '例外探索'):
            self.generate(experiment_id)

    def test_valid_exception_and_original_lessons_are_saved(self):
        def decisions(lessons, findings):
            rows = self.reject_lessons(lessons, findings)
            redo = next(f['lesson'] for f in findings if f['parameter']=='top_k')
            for row in rows:
                if row['lesson']==redo:
                    row.update(decision='例外探索', affected_candidates=['A'],
                               reason='上次：保留六条；这次：预演表明目标证据在第八条')
            return rows

        experiment_id = self.second_round(decisions)
        result = self.generate(experiment_id)
        decisions = result['result']['agent_strategies']['2']['history_decisions']
        self.assertEqual(len(result['candidates']), 6)
        self.assertEqual([row['affected_candidates'] for row in decisions if row['decision']=='例外探索'], [['A']])
        self.assertIn('先处理证据位置。', [row['lesson'] for row in decisions])
