"""用户 2026-11-16 19:45：参考答案要结构化分行、可适度润色；锚点只查事实，不查排版。"""
import unittest

from app.governance import _answer_anchor_supported, _strip_answer_layout
from app.golden_v2 import friend_answer_supported

SOURCE = [{'chunk_text': '先短按电源开关一次，再长按电源开关3秒以上，即可开启电池。悬崖激光扫描器脏了\n后部激光扫描器脏了\n前部激光扫描器脏了'}]


class AnswerLayoutTests(unittest.TestCase):
    def test_layout_markers_and_framing_are_not_facts(self):
        self.assertEqual(_strip_answer_layout('按以下步骤操作：\n1. 甲\n2. 乙'), '甲\n乙')
        self.assertTrue(_answer_anchor_supported('按以下步骤操作：\n1. 先短按电源开关一次\n2. 再长按电源开关3秒以上', [SOURCE[0]['chunk_text']]))

    def test_count_line_must_match_items(self):
        self.assertTrue(friend_answer_supported('共三条：\n1. 悬崖激光扫描器脏了\n2. 后部激光扫描器脏了\n3. 前部激光扫描器脏了', SOURCE))
        self.assertFalse(friend_answer_supported('共四条：\n1. 悬崖激光扫描器脏了\n2. 后部激光扫描器脏了\n3. 前部激光扫描器脏了', SOURCE))

    def test_friend_anchor_allows_polish_but_blocks_invented_facts(self):
        self.assertTrue(friend_answer_supported('1. 机器人开机：先短按电源开关一次。\n2. 再长按电源开关3秒以上，即可开启电池。', SOURCE))
        self.assertFalse(friend_answer_supported('1. 先短按电源开关一次\n2. 再长按电源开关5秒以上', SOURCE))
        self.assertFalse(friend_answer_supported('先按下“复位”按钮，再长按电源开关3秒以上', SOURCE))
        self.assertFalse(friend_answer_supported('可以用酒精擦拭电池表面后再开机使用', SOURCE))


if __name__ == '__main__':
    unittest.main()


class FriendSnapshotManifestTests(unittest.TestCase):
    def test_friend_snapshot_needs_no_atomic_manifest_but_legacy_still_does(self):
        from app.scoring_contract import validate_snapshot_manifest
        friend = {'question_ids': ['A'], 'questions': [{'id': 'A', 'golden_contract': 'friend-golden-v1', 'test_category': 'positive'}]}
        validate_snapshot_manifest(friend)
        legacy = {'question_ids': ['A'], 'questions': [{'id': 'A', 'test_category': 'positive'}]}
        with self.assertRaises(ValueError):
            validate_snapshot_manifest(legacy)


class JudgeSourceLabelTests(unittest.TestCase):
    def test_judge_sees_document_and_section_but_no_ids(self):
        from app.rubric_judge import final_texts, rubric_input
        entries = [{'chunk_id': 'DOC-003-V2-C-00016', 'document': '宇树_B2遥控器使用说明_中文版.pdf',
                    'section_path': 'R1遥控器 / 技术规格', 'content': '参数=锂电池容量；规格=2500mAh'}]
        texts = final_texts(entries)
        self.assertEqual(texts, ['（出处：宇树_B2遥控器使用说明_中文版 · R1遥控器 / 技术规格）参数=锂电池容量；规格=2500mAh'])
        payload = rubric_input('问', '参考', '答', 'positive', None, texts)
        self.assertNotIn('DOC-', payload)
        self.assertIn('R1遥控器', payload)


class ReplayWithReplacedQuestionsTests(unittest.TestCase):
    """用户 2026-11-16 23:13：换掉 2 道题后，未换的题沿用旧回答和耗时，只给新题生成，全部用新判分重新打分。"""
    def setUp(self):
        import json
        from tests.test_judge_replay_v5 import JudgeReplayTests
        source, cases, snapshot, config, judge, chunks = JudgeReplayTests().example()
        old_q = snapshot['questions'][0]
        new_q = {'id': 'q-replaced', 'question': '新换的题？', 'reference_answer': '新答案。', 'test_category': 'positive', 'evidence': []}
        kept = {**old_q, 'id': 'q-kept-new-id'}  # 重新导入后题目 ID 会变，题面和参考答案不变
        self.snapshot = {**snapshot, 'id': 'gd-2', 'question_ids': [kept['id'], new_q['id']], 'questions': [kept, new_q]}
        source_snapshot = {**snapshot, 'question_ids': ['q-new', 'q-gone'],
                           'questions': [old_q, {'id': 'q-gone', 'question': '换下来的题？', 'reference_answer': '旧答案。', 'test_category': 'positive', 'evidence': []}]}
        self.source = {**source, 'dataset_snapshot_json': json.dumps(source_snapshot)}
        self.cases, self.config, self.judge, self.chunks = cases, config, judge, chunks

    def run_check(self, allow):
        from app.judge_replay import replay_eligibility
        from app.evaluation_contract import evaluation_identity
        judge = {**self.judge, 'evaluation_identity': evaluation_identity(self.snapshot, self.judge)}
        return replay_eligibility(self.source, self.cases, self.snapshot, self.config, judge, self.chunks, 'fp', allow_new_questions=allow)

    def test_kept_question_reuses_answer_and_new_question_generates(self):
        result = self.run_check(True)
        self.assertTrue(result['can_replay'], result['eligibility'])
        self.assertEqual(result['new_question_ids'], ['q-replaced'])
        self.assertEqual(result['generation_calls'], 1)
        self.assertEqual(set(result['executions']), {'q-kept-new-id'})

    def test_without_permission_changed_snapshot_is_blocked(self):
        self.assertFalse(self.run_check(False)['can_replay'])

    def test_profile_change_is_blocked(self):
        self.snapshot['questions'][1] = {**self.snapshot['questions'][1], 'test_category': 'negative', 'negative_subtype': 'clarify'}
        self.assertFalse(self.run_check(True)['can_replay'])


class MultiIssueTagTests(unittest.TestCase):
    """用户 2026-11-16 23:49：一道错题可以同时有检索、生成、安全、性能多个问题。"""
    def test_one_case_gets_every_observed_issue(self):
        from app.diagnostics import issue_tags
        case = {'test_category': 'ablation', 'evaluation_outcome': {'verdict': 'FAIL', 'failed_dimensions': ['correctness', 'completeness', 'faithfulness']},
                'judge_result': {'over_refusal': True}}
        analysis = {'evidence_checks': [{'candidate_hit': False, 'final_hit': False}]}
        keys = [t['key'] for t in issue_tags(case, analysis, 88000, 60000)]
        self.assertEqual(keys, ['retrieval_missing', 'incorrect_answer', 'completeness_gap', 'unsupported_content', 'over_refusal', 'slow_answer'])
        layers = {t['layer'] for t in issue_tags(case, analysis, 88000, 60000)}
        self.assertEqual(layers, {'检索层', '生成层', '性能'})

    def test_passing_case_only_gets_slow_tag(self):
        from app.diagnostics import issue_tags
        case = {'test_category': 'negative', 'evaluation_outcome': {'verdict': 'PASS'}, 'judge_result': {'behavior_correct': True, 'safety_violation': False}}
        self.assertEqual([t['key'] for t in issue_tags(case, {}, 70000, 60000)], ['slow_answer'])
        self.assertEqual(issue_tags(case, {}, 10000, 60000), [])

    def test_negative_safety_and_behavior(self):
        from app.diagnostics import issue_tags
        case = {'test_category': 'negative', 'evaluation_outcome': {'verdict': 'FAIL', 'failed_dimensions': ['safety']},
                'judge_result': {'behavior_correct': True, 'safety_violation': True}}
        self.assertEqual([t['key'] for t in issue_tags(case, {}, None, 60000)], ['safety_violation'])


class AgentFormatRepairTests(unittest.TestCase):
    def test_round_limit_policy_is_read_from_experiment(self):
        import inspect
        from app import optimization_cycle
        self.assertIn("max_rounds", inspect.getsource(optimization_cycle._run_staged))
        self.assertIn("round_limit", inspect.getsource(optimization_cycle._run_staged))

    def test_adjustments_and_strategy_name_are_repaired_not_rejected(self):
        from copy import deepcopy
        from test_task031f import InheritanceTests
        fixture = InheritanceTests(); fixture.setUp()
        candidate = fixture.response['candidates'][0]
        candidate['strategy_name'] = '格式不规范'
        candidate['adjustments'][0]['baseline_value'] = 99
        original = deepcopy(candidate['adjustments'])
        _, batch = fixture.prepare()
        reasoning = batch[0][2]
        self.assertRegex(reasoning['strategy_name'], r'^「.+」（.+优先）$')
        self.assertEqual(reasoning['adjustments'], [{**item, 'baseline_value':fixture.base[item['parameter']]}
                                                   for item in original])
        repairs = {item['field']:item['from'] for item in fixture.audit['normalized_fields'] if item['candidate']==0}
        self.assertEqual(repairs['strategy_name'], '格式不规范')
        self.assertEqual(repairs['adjustments'], original)
