"""Offline regression tests for conservative denoising and evidence anchoring."""
import sys
from pathlib import Path
import unittest

from app.knowledge_pipeline import parent_child_v2, child_embedding_text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from task031b_chunk_statistics import evidence_audit


class DenoiseAndPathTests(unittest.TestCase):
    def test_headers_footers_require_content_evidence_and_footnotes_always_survive(self):
        blocks = [{'type': kind, 'text': text, 'page_idx': page} for kind, text, page in [
            ('header', 'KIRA B 50', 0), ('footer', '第 1 页', 0), ('header', '***', 0),
            ('header', '请勿将电池扔进垃圾桶', 0), ('footer', '1. 按下暂停按钮', 0),
            ('footer', '充电线设备舱的门', 0), ('header', '不明短行', 0),
            ('page_number', '1', 0), ('footer', '版权声明', 0), ('footer', '版权声明', 1),
            ('page_footnote', '摇杆定义', 0), ('page_footnote', '摇杆定义', 1),
            ('page_footnote', '12', 1), ('header', '只出现一次', 9)]]
        parents, _, parsed = parent_child_v2({'id':'D', 'name':'说明书.pdf', 'product':'KIRA B 50', 'pages':10}, blocks, len)
        body = '\n'.join(p['chunk_text'] for p in parents)
        for text in ('请勿将电池扔进垃圾桶', '1. 按下暂停按钮', '充电线设备舱的门', '不明短行', '只出现一次', '版权声明', '12'):
            self.assertIn(text, body)
        self.assertEqual(body.count('摇杆定义'), 2)
        self.assertEqual([p['text'] for p in parsed if p.get('drop_reason')], ['KIRA B 50', '第 1 页', '***', '1'])

    def test_repeated_header_is_removed_only_above_thirty_percent(self):
        for count, expected in ((3, 0), (4, 4)):
            with self.subTest(count=count):
                blocks = [{'type':'header','text':'重复页眉','page_idx':i} for i in range(count)]
                _, _, parsed = parent_child_v2({'id':'D','name':'文档','pages':10}, blocks, len)
                self.assertEqual(sum(bool(p.get('drop_reason')) for p in parsed), expected)

    def test_repeated_safety_headers_and_toc_footnotes_are_kept(self):
        blocks = [{'type':'header','text':'请勿将电池扔进垃圾桶','page_idx':i} for i in range(4)]
        blocks += [{'type':'text','text':'目录\n甲……1\n乙……2\n丙……3'},
                   {'type':'page_footnote','text':'安全操作步骤','text_level':1}]
        parents, _, parsed = parent_child_v2({'id':'D','name':'文档','pages':10}, blocks, len)
        self.assertEqual(sum(p['chunk_text'].count('请勿将电池扔进垃圾桶') for p in parents), 4)
        self.assertIn('安全操作步骤', '\n'.join(p['chunk_text'] for p in parents))
        self.assertFalse(parsed[-1].get('heading_only'))

    def test_child_start_path_and_merged_tail_remain_in_document_order(self):
        blocks = [{'type':'text','text':'操作元件','text_level':1},
                  {'type':'text','text':'正面','text_level':2}, {'type':'text','text':'甲。' * 130},
                  {'type':'text','text':'清洁剂','text_level':2}, {'type':'text','text':'乙。' * 20}]
        parents, children, _ = parent_child_v2({'id':'D','name':'说明书'}, blocks, len)
        self.assertEqual(parents[0].get('chapter'), '操作元件')
        self.assertEqual(parents[0]['subsections'], ['正面','清洁剂'])
        self.assertEqual(parents[0]['section_path'], '操作元件')
        cross = next(c for c in children if len(c['section_paths']) == 2)
        self.assertEqual(cross['section_path'], '操作元件 / 正面')
        self.assertEqual(cross['section_paths'], ['操作元件 / 正面','操作元件 / 清洁剂'])
        self.assertTrue(child_embedding_text(cross).startswith('说明书 · 操作元件 / 正面\n'))


class EvidenceNormalizationTests(unittest.TestCase):
    def audit(self, quote, body='先关闭电源。\n再清洁设备。', path='保养 / 每月一次', heading='每月一次'):
        parent = {'chunk_id':'P', 'document_id':'D', 'chunk_text':body}
        cut = body.index('\n') + 1
        children = [{'chunk_id':f'C{i}', 'document_id':'D', 'parent_chunk_id':'P',
                     'char_start':a, 'char_end':b, 'chunk_text':body[a:b],
                     'section_path':path, 'section_paths':[path]} for i,(a,b) in enumerate(((0,cut),(cut,len(body))))]
        snapshot = {'id':'G','questions':[{'id':'q','business_requirements':{'sources':[{'quote':quote,'document_id':'D','chunk_id':'old'}]}}]}
        result = evidence_audit(snapshot, [{'chunk_id':'OP','chunk_text':quote}],
                                [{'chunk_id':'old','parent_chunk_id':'OP'}], [parent], children,
                                {'D':[{'text':heading,'heading_only':True}]})
        return result['questions'][0]['quotes'][0]

    def test_private_use_whitespace_and_heading_normalization_cross_children(self):
        result = self.audit('每月一次\n先关闭电源。\ue258\n\t再清洁设备。\U000f0000\U00100000')
        self.assertTrue(result['exact_in_child_or_contiguous_children'])
        self.assertEqual(result['parent_spans'][0]['child_ids'], ['C0','C1'])
        self.assertEqual(result['normalization']['removed_private_use_count'], 3)
        self.assertEqual(result['normalization']['removed_heading_lines'], ['每月一次'])
        self.assertTrue(result['normalization']['headings_verified'])

    def test_heading_line_whitespace_is_normalized_before_title_comparison(self):
        result = self.audit('  每月 \t 一次 \t\n先关闭电源。\n再清洁设备。', path='保养 / 每月 一次', heading='每月 一次')
        self.assertTrue(result['exact_in_child_or_contiguous_children'])

    def test_new_picture_description_cannot_be_skipped_to_force_a_match(self):
        result = self.audit('先关闭电源。\n再清洁设备。', body='先关闭电源。\n1 电源开关\n再清洁设备。')
        self.assertFalse(result['exact_in_child_or_contiguous_children'])

    def test_heading_must_be_in_matched_child_paths_and_body_must_be_literal(self):
        self.assertFalse(self.audit('每月一次\n先关闭电源。\n再清洁设备。', path='其他章节')['exact_in_child_or_contiguous_children'])
        self.assertFalse(self.audit('先关闭电源。\n再维修设备。')['exact_in_child_or_contiguous_children'])
        self.assertFalse(self.audit('每月一次')['exact_in_child_or_contiguous_children'])
        self.assertFalse(self.audit('请按每月一次要求操作。')['exact_in_child_or_contiguous_children'])
