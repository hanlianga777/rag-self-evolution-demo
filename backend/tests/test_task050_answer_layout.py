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
