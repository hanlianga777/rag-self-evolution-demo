"""Round 0 isolated, offline pipeline contract tests."""
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_isolation = tempfile.TemporaryDirectory(prefix='round0-pipeline-')
_env = {key: str(Path(_isolation.name) / name) for key, name in {
    'RAG_DEMO_DB_PATH': 'test.db', 'RAG_DEMO_ENV_PATH': 'empty.env',
    'RAG_DEMO_INDEX_DIR': 'index', 'RAG_DEMO_DOCUMENTS_DIR': 'documents',
    'RAG_DEMO_UPLOADS_DIR': 'uploads'}.items()}
with patch.dict(os.environ, _env):
    from app.policy import DEFAULT_PIPELINE_CONFIG, validate_candidate_config, search_space_contract
    from app.retrieval import VectorRetriever, prepare_decomposed_queries
    from app.context_budget import budget_context, render_generation_context, count_context_tokens


class Round0PolicyTests(unittest.TestCase):
    def test_new_defaults_and_historical_absence(self):
        self.assertEqual(DEFAULT_PIPELINE_CONFIG['generation_thinking'], 'max')
        self.assertNotIn('query_decompose', DEFAULT_PIPELINE_CONFIG)
        self.assertIs(DEFAULT_PIPELINE_CONFIG['retrieval_max_tokens'], False)
        old = {k: v for k, v in DEFAULT_PIPELINE_CONFIG.items()
               if k not in {'generation_thinking', 'query_decompose', 'retrieval_max_tokens'}}
        before = deepcopy(old)
        self.assertTrue(validate_candidate_config(old)['valid'])
        self.assertEqual(old, before)

    def test_strict_types(self):
        for key, value in [('query_decompose', 1), ('retrieval_max_tokens', True),
                           ('retrieval_max_tokens', 8192.0), ('retrieval_max_tokens', 1),
                           ('generation_thinking', 'medium')]:
            with self.subTest(key=key, value=value):
                self.assertFalse(validate_candidate_config({**DEFAULT_PIPELINE_CONFIG, key: value})['valid'])
        for limit in (False, 8192, 4096):
            self.assertTrue(validate_candidate_config({**DEFAULT_PIPELINE_CONFIG, 'retrieval_max_tokens': limit})['valid'])
        self.assertNotIn('query_decompose', search_space_contract())


class Round0DecomposeTests(unittest.TestCase):
    def test_bounds_dedup_and_original_constraints(self):
        question = 'B2关机后如何充电和存放，禁止拆机？'
        queries, trace = prepare_decomposed_queries(question, ['充电？', '充电？', '存放？', 'B3拆机？', '继续？'])
        self.assertLessEqual(len(queries), 3)
        self.assertEqual(len(queries), len(set(queries)))
        self.assertTrue(all(question in query for query in queries))
        self.assertNotIn('B3拆机？', trace['subquestions'])
        self.assertTrue(trace['discarded'])

    def test_opposite_permission_hints_discarded(self):
        queries, trace = prepare_decomposed_queries('B2维护事项？', ['允许拆机？', '禁止拆机？'])
        self.assertEqual(queries, [])
        self.assertEqual(len(trace['discarded']), 2)

    def test_retrieve_searches_and_merges_real_subquery_sources(self):
        chunks = [dict(chunk_id=f'C{i}', document_id='D', product='B2', chunk_text=text)
                  for i, text in enumerate(['充电', '存放'])]
        retriever = VectorRetriever(SimpleNamespace(chunks=lambda: chunks))
        queries, _ = prepare_decomposed_queries('B2充电和存放？', ['充电？', '存放？'])
        calls = []
        def search(query, limit, **kwargs):
            calls.append(query)
            return [{'chunk_id': 'C1' if query.endswith('存放？') else 'C0', 'score': .8}]
        config = {**DEFAULT_PIPELINE_CONFIG, 'query_decompose': True}
        trace = {}
        with patch.object(retriever, 'vector_candidates', side_effect=search):
            hits = retriever.retrieve('B2充电和存放？', config, queries=queries, trace=trace)
        self.assertEqual(calls, ['B2充电和存放？', *queries])
        self.assertEqual({h['chunk_id'] for h in hits}, {'C0', 'C1'})
        self.assertEqual(len(trace['query_sources']), 3)
        self.assertEqual(len({h['chunk_id'] for h in trace['candidates']}), 2)

    def test_off_preserves_query_behavior(self):
        chunks = [dict(chunk_id='C', document_id='D', chunk_text='说明')]
        retriever = VectorRetriever(SimpleNamespace(chunks=lambda: chunks))
        trace = {}
        with patch.object(retriever, 'vector_candidates', return_value=[{'chunk_id': 'C', 'score': 1}]):
            retriever.retrieve('原问题', DEFAULT_PIPELINE_CONFIG, trace=trace)
        self.assertEqual(trace['queries'], ['原问题'])
        self.assertNotIn('query_sources', trace)


class Round0BudgetTests(unittest.TestCase):
    def entries(self):
        return [dict(chunk_id='C1', parent_chunk_id='P1', matched_child_ids=['C1'], document_id='D',
                     product='B2', version='1', section='充电', parent_page_start=1, parent_page_end=2,
                     content='操作步骤。' * 200),
                dict(chunk_id='C2', document_id='D', product='B2', page_start=3, page_end=3,
                     content='禁止危险操作。' * 6000)]

    def test_off_no_truncation_no_mutation(self):
        entries = self.entries(); before = deepcopy(entries)
        selected, trace = budget_context(entries, False)
        self.assertEqual(selected, before)
        self.assertEqual(entries, before)
        self.assertTrue(trace['generation_allowed'])
        self.assertIsNone(trace['tokens_before'])

    def test_on_whole_blocks_exact_context_trace_and_fail_closed(self):
        entries = self.entries(); before = deepcopy(entries)
        selected, trace = budget_context(entries, 8192)
        self.assertEqual(selected, [entries[0]])
        self.assertEqual(entries, before)
        self.assertEqual(selected[0]['content'], before[0]['content'])
        self.assertEqual(selected[0]['matched_child_ids'], ['C1'])
        self.assertEqual(trace['tokens_after'], count_context_tokens(render_generation_context(selected)))
        self.assertLessEqual(trace['tokens_after'], 8192)
        self.assertFalse(trace['generation_allowed'])
        self.assertFalse(trace['context_complete'])
        self.assertEqual(trace['excluded'][0]['chunk_id'], 'C2')
        self.assertIn(trace['count_method'], ('deepseek_v4_official_local', '字符数估算 token'))

    def test_on_full_context_keeps_generation(self):
        selected, trace = budget_context(self.entries()[:1], 8192)
        self.assertEqual(len(selected), 1)
        self.assertTrue(trace['generation_allowed'])

    def test_budget_rejects_invalid_input(self):
        for value in (True, 0, 8192.0, '8192'):
            with self.assertRaises(ValueError): budget_context(self.entries(), value)

    def test_off_does_not_load_tokenizer(self):
        with patch('app.context_budget._tokenizer', side_effect=AssertionError('must not load')):
            self.assertTrue(budget_context(self.entries(), False)[1]['generation_allowed'])

    def test_missing_tokenizer_estimates_on(self):
        with patch('app.context_budget.TOKENIZER_ARCHIVE', Path(_isolation.name) / 'absent.zip'):
            from app.context_budget import _tokenizer
            _tokenizer.cache_clear()
            try:
                self.assertIn('估算', budget_context(self.entries(), 8192)[1]['count_method'])
            finally: _tokenizer.cache_clear()
