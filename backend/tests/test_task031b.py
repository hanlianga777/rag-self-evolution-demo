"""Offline v2 chunking and v3 generation contracts; no provider requests."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import knowledge_pipeline as kp
from app.ai_service import AiService, generation_contract, generation_boundary
from app.context_budget import render_generation_context


class ChunkV2Tests(unittest.TestCase):
    document = {'id': 'D', 'name': '清洁机器人说明书.pdf'}

    def split(self, blocks):
        self.assertTrue(hasattr(kp, 'parent_child_v2'), 'v2 must be opt-in, leaving v1 intact')
        return kp.parent_child_v2(self.document, blocks, len)

    def test_noise_is_audited_titles_are_metadata_and_offsets_are_exact(self):
        blocks = [{'type': 'header', 'text': '品牌', 'page_idx': 0},
                  {'type': 'text', 'text': '第 1 页', 'page_idx': 0},
                  {'type': 'text', 'text': '保养', 'text_level': 1, 'page_idx': 0},
                  {'type': 'text', 'text': '每月一次', 'text_level': 2, 'page_idx': 0},
                  {'type': 'text', 'text': '先关闭电源，再进行清洁。' * 120, 'page_idx': 0},
                  {'type': 'text', 'text': '每年一次', 'text_level': 2, 'page_idx': 1},
                  {'type': 'text', 'text': '请联系官方售后检查。' * 90, 'page_idx': 1}]
        parents, children, parsed = self.split(blocks)
        self.assertEqual(len([p for p in parsed if p.get('drop_reason')]), 2)
        self.assertTrue(all(c['chunk_text'] not in {'保养', '每月一次', '每年一次', '品牌'} for c in children))
        self.assertTrue(any('保养 / 每月一次' in c['section_path'] for c in children))
        self.assertTrue(all(80 <= c['token_count'] <= 300 for c in children))
        for child in children:
            parent = next(p for p in parents if p['chunk_id'] == child['parent_chunk_id'])
            self.assertEqual(parent['chunk_text'][child['char_start']:child['char_end']], child['chunk_text'])
            self.assertIn('清洁机器人说明书.pdf · ', kp.child_embedding_text(child))
        self.assertTrue(all(p['token_count'] <= 1400 for p in parents))
        self.assertTrue(all(p['level_one_section'] == '保养' for p in parents))

    def test_never_cross_top_chapter_and_single_short_chapter_is_disclosed(self):
        blocks = []
        for title, body in [('甲章', '甲内容。' * 10), ('乙章', '乙内容。' * 500)]:
            blocks += [{'type': 'text', 'text': title, 'text_level': 1}, {'type': 'text', 'text': body}]
        parents, children, _ = self.split(blocks)
        self.assertTrue(parents[0]['short_chapter'])
        self.assertEqual(parents[0]['chunk_text'], '甲内容。' * 10)
        self.assertTrue(all(not ('甲内容' in p['chunk_text'] and '乙内容' in p['chunk_text']) for p in parents))

    def test_repetition_toc_and_table_rows(self):
        blocks = [{'type': 'text', 'text': '目录\n维护……3\n充电……4\n规格……5', 'page_idx': 0}]
        for page in range(1, 5):
            blocks += [{'type': 'text', 'text': '重复品牌', 'page_idx': page},
                       {'type': 'text', 'text': '操作正文。' * 40, 'page_idx': page}]
        blocks += [{'type': 'table', 'page_idx': 4, 'table_caption': ['技术规格'],
                    'table_body': '<table><tr><th>参数</th><th>规格</th></tr>' + ''.join(f'<tr><td>项目{i}</td><td>数值{i}</td></tr>' for i in range(80)) + '</table>'}]
        parents, children, parsed = self.split(blocks)
        reasons = [p.get('drop_reason') for p in parsed]
        self.assertIn('table_of_contents', reasons)
        self.assertEqual(reasons.count('repeated_short_line'), 4)
        table_children = [c for c in children if c.get('table')]
        self.assertGreater(len(table_children), 1)
        self.assertTrue(all('参数=' in c['chunk_text'] for c in table_children))
        self.assertTrue(all(c['token_count'] <= 300 for c in children))

    def test_parser_heading_mistakes_keep_steps_and_warning_labels_in_body(self):
        blocks = [{'type':'text','text':'安全操作','text_level':1},
                  {'type':'text','text':'危险','text_level':2},
                  {'type':'text','text':'请先断开电源。' * 20},
                  {'type':'text','text':'1. 按下停止按钮','text_level':2}]
        parents, children, _ = self.split(blocks)
        self.assertIn('危险\n请先断开电源。', parents[0]['chunk_text'])
        self.assertIn('1. 按下停止按钮', parents[0]['chunk_text'])
        self.assertFalse(any(c['chunk_text'].strip() == '危险' for c in children))

    def test_headerless_table_does_not_lose_first_data_row(self):
        blocks = [{'type':'table','table_body':'<table><tr><td>额定电压</td><td>50V</td></tr><tr><td>额定功率</td><td>100W</td></tr></table>'}]
        _, children, _ = self.split(blocks)
        self.assertIn('额定电压', children[0]['chunk_text'])
        self.assertIn('额定电压 | 50V', children[0]['chunk_text'])

    def test_conflicting_table_binding_fails_instead_of_cutting_a_row(self):
        blocks = [{'type':'text','text':'章节','text_level':1},
                  {'type':'text','text':'甲' * 300}, {'type':'text','text':'推荐清洁剂：' + '注' * 93},
                  {'type':'table','table_body':'<table><tr><th>参数</th><th>规格</th></tr>' +
                   ''.join('<tr><td>项目</td><td>' + '乙' * 88 + '</td></tr>' for _ in range(11)) + '</table>'}]
        with self.assertRaisesRegex(ValueError, 'table'):
            self.split(blocks)

    def test_toc_page_split_across_parser_blocks_is_removed(self):
        _, children, parsed = self.split([{'type':'text','text':line,'page_idx':0} for line in
                                           ('安全须知……2','操作说明……4','日常保养……8')])
        self.assertEqual(children, [])
        self.assertEqual([p.get('drop_reason') for p in parsed], ['table_of_contents'] * 3)

    def test_table_and_leading_explanation_share_parent(self):
        parents, _, _ = self.split([{'type':'text','text':'操作','text_level':1},
                                    {'type':'text','text':'操作正文。' * 230},
                                    {'type':'text','text':'推荐的清洁剂：'},
                                    {'type':'table','table_body':'<table><tr><th>适用范围</th><th>清洁剂</th></tr>' +
                                     ''.join('<tr><td>所有防水地板</td><td>CA50</td></tr>' for _ in range(25)) + '</table>'}])
        table_parent = next(p for p in parents if '适用范围=' in p['chunk_text'])
        self.assertIn('推荐的清洁剂：', table_parent['chunk_text'])

    def test_short_first_parent_rebalances_with_next_in_same_chapter(self):
        parents, _, _ = self.split([{'type':'text','text':'章节','text_level':1},
                                    {'type':'text','text':'说明。' * 100},
                                    {'type':'text','text':'操作。' * 433}])
        self.assertTrue(all(400 <= p['token_count'] <= 1400 for p in parents))

    def test_oversized_paragraph_rebalances_parent_tail(self):
        parents, children, _ = self.split([{'type':'text','text':'章节','text_level':1},
                                           {'type':'text','text':'这里是说明正文。' * 190}])
        self.assertTrue(all(400 <= p['token_count'] <= 1400 for p in parents))
        self.assertTrue(all(c['token_count'] <= 300 for c in children))

    def test_opt_in_build_embeds_heading_context_and_saves_denoise(self):
        import numpy as np
        import pymupdf
        from app.corpus import CorpusStore
        class Parser:
            def parse(inner, path, identifier):
                return [{'type':'header','text':'页眉品牌'},
                        {'type':'text','text':'维护','text_level':1},
                        {'type':'text','text':'请关闭电源之后清洁设备。' * 100}], b'fixture'
        class Embedder:
            def embed(inner, texts, dimension):
                self.assertTrue(all(t.startswith('清洁机器人说明书.pdf · 维护\n') for t in texts))
                return np.ones((len(texts), dimension), dtype='float32') / dimension ** .5
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = pymupdf.open(); pdf.new_page(); pdf.save(root/'source.pdf'); pdf.close()
            document = {**self.document, '_source_path':str(root/'source.pdf')}
            staging, _ = kp.KnowledgePipeline(root/'index', None).build(
                [document], {}, parser=Parser(), embedder=Embedder(), counter=len, chunk_version='parent-child-v2')
            manifest = json.loads((staging/'manifest.json').read_text())
            self.assertEqual(manifest['knowledge_config']['chunk_strategy'], 'parent-child-v2')
            self.assertEqual(manifest['knowledge_config']['child_tokens'], 300)
            detail = CorpusStore(staging).detail('D')
            self.assertEqual(detail['denoise'][0]['reason'], 'parser_header')
            self.assertEqual(detail['category'], '清洁机器人说明书')
            self.assertTrue(all('页眉品牌' not in c['chunk_text'] for c in detail['chunks']))

    def test_category_inference_and_manual_override(self):
        self.assertTrue(hasattr(kp, 'document_category'))
        for name, category in [('清洁机器人.pdf','清洁机器人说明书'), ('B2四足机器人.pdf','巡检机器人说明书'),
                               ('B2遥控器.pdf','遥控器说明书'), ('电池充电器.pdf','电池与充电器说明书'), ('x.pdf','其他')]:
            self.assertEqual(kp.document_category({'name': name, 'product': None}), category)
        self.assertEqual(kp.document_category({'name':'清洁机器人.pdf', 'category':'其他'}), '其他')


class PromptV3Tests(unittest.TestCase):
    def test_literal_prompt_hash_and_default_contract(self):
        task = Path(__file__).resolve().parents[2] / '指挥'
        paths = list((task/'队列').glob('031b-*.md')) + list((task/'历史任务').glob('031b-*.md'))
        literal = re.search(r'```\n(你是机器人设备的官方客服助手.*?)\n```', paths[0].read_text(), re.S)[1]
        self.assertEqual(generation_contract()['generation_prompt_version'], 'generation-vnext-3')
        self.assertEqual(generation_boundary('generation-vnext-3'), literal)
        self.assertEqual(generation_contract()['generation_boundary_sha256'], '10dfcf4cb390f55e7c7e209dd3ff29a744f0f06fa859d2b1841c7fce1bc0dd8f')
        self.assertEqual(generation_contract()['generation_boundary_sha256'], hashlib.sha256(literal.encode()).hexdigest())

    def test_numbering_and_answer_mapping_follow_retrieval_order(self):
        entries = [{'chunk_id':'C9', 'content':'甲证据'}, {'chunk_id':'C3', 'content':'乙证据'}]
        context = render_generation_context(entries)
        self.assertIn('[1]', context)
        self.assertIn('[2]', context)
        self.assertLess(context.index('[1]'), context.index('甲证据'))
        self.assertLess(context.index('[2]'), context.index('乙证据'))
        class Provider:
            settings = SimpleNamespace(configured=True, model='mock')
            def complete_with_metrics(inner, system, user, **kwargs):
                self.assertIn(generation_boundary('generation-vnext-3'), system)
                return {'content':'先做乙事项。[2] 再做甲事项。[1][2] 无效标号[0][9]。', 'ttft_ms':0, 'input_tokens':0, 'output_tokens':0}
        for target in ('baseline', 'sandbox_candidate', 'online'):
            service = AiService(object(), object(), Provider(), False)
            service.retriever = SimpleNamespace(retrieve=lambda *a, **kw: entries)
            result = service.answer('问题', {'run_target':target})
            self.assertEqual(result['citation_markers'], {'[2]':1, '[1]':0})
            self.assertEqual(result['retrieval'][result['citation_markers']['[2]']]['chunk_id'], 'C3')
            self.assertEqual(result['generation_prompt_version'], 'generation-vnext-3')

    def test_new_evaluation_version_and_legacy_rows_round_trip(self):
        from app.governance import GovernanceStore
        from test_round0_identity import BaselineConfigTests
        runner = BaselineConfigTests().runtime_store()
        snapshot, _, config, judge = runner.baseline_inputs()
        self.assertEqual(judge['generation_prompt_version'], 'generation-vnext-3')
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory)/'fixture.db')
            with store.connection() as connection:
                connection.execute('INSERT INTO dataset_versions VALUES (?, ?, ?, ?, ?)',
                                   (snapshot['id'], 'approved', 'fixture', json.dumps(snapshot), 'offline'))
            judge['baseline_version'] = store.active_production()['id']
            run_id = store.create_baseline_run(snapshot, config, judge)
            self.assertEqual(store.evaluation_run(run_id)['judge']['generation_prompt_version'], 'generation-vnext-3')
            # Read old stored JSON without version migration or rewriting it.
            for version in ('generation-vnext-1', 'generation-vnext-2'):
                with store.connection() as connection:
                    connection.execute('UPDATE evaluation_runs SET judge_json=? WHERE id=?', (json.dumps(generation_contract(version)), run_id))
                self.assertEqual(store.evaluation_run(run_id)['judge'], generation_contract(version))

    def test_old_generation_contracts_keep_their_hash(self):
        self.assertEqual(generation_contract('generation-vnext-1')['generation_boundary_sha256'], 'd1fa3c13186c04fb95bd01be6615f25c6a59dbdd766290a108c4bfac78456ea2')
        self.assertEqual(generation_contract('generation-vnext-2')['generation_boundary_sha256'], 'ecc0a21cfb29dca1febb48f3c4f46f128cb12f8b94a8409b9ded08db427715af')


sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))


class StatisticsTests(unittest.TestCase):
    def test_frozen_golden_selection_ignores_latest_unrelated_run(self):
        import sqlite3
        from task031b_chunk_statistics import load_frozen_golden
        with sqlite3.connect(':memory:') as connection:
            connection.execute('CREATE TABLE dataset_versions(id TEXT, status TEXT, snapshot_json TEXT)')
            questions = [{'id':str(i)} for i in range(50)]
            snapshot = {'id':'frozen50','question_ids':[q['id'] for q in questions],'questions':questions}
            connection.execute('INSERT INTO dataset_versions VALUES (?,?,?)', ('frozen50','approved',json.dumps(snapshot)))
            connection.execute('INSERT INTO dataset_versions VALUES (?,?,?)', ('other','approved','{}'))
            self.assertEqual(load_frozen_golden(connection,'frozen50'), snapshot)
            with self.assertRaisesRegex(ValueError,'50'):
                load_frozen_golden(connection,'other')

    def test_no_saved_quote_cannot_pass_literal_evidence_check(self):
        from task031b_chunk_statistics import evidence_audit
        audit = evidence_audit({'id':'empty','questions':[{'id':'q'}]}, [], [], [], [], {})
        self.assertFalse(audit['all_source_quotes_exact'])
