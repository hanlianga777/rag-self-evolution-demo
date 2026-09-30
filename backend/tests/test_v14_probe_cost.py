"""V1.4 fixture-only retrieval, raw parsed pages, activation and billing contracts."""
import copy
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import faiss
import numpy as np

from app.ai_service import AiService
from app.corpus import CorpusStore
from app.corpus_management import CorpusManager
from app.full_text import checksum, write_full_text, validate_bundle, search_full_text
from app.governance import GovernanceStore
from app.providers import DeepSeekProvider
from app.retrieval import VectorRetriever, RetrievalUnavailable, evidence_coverage
from app.telemetry import cost_report, estimate_cost, price_config, measure
from test_candidate_review_export import candidates


def raw_pages(text='设备电池额定电压为48V。', fingerprint=None):
    fingerprint = fingerprint or {'D': 'hash'}
    return {'artifact_schema_version': 1, 'corpus_fingerprint': fingerprint, 'parser_identity': 'fixture-parser',
            'coverage': {'status': 'complete', 'total_pages': 1, 'parsed_pages': 1},
            'pages': [{'document_id': 'D', 'page': 1, 'text': text, 'parser': 'fixture', 'text_checksum': checksum(text.encode()), 'source_fingerprint': fingerprint['D']}]}


def bundle(path, identity='old', texts=None):
    path.mkdir(parents=True)
    texts = texts or ['必须先确认状态']
    docs = [{'id': 'D', 'name': 'fixture.pdf', 'pages': 1, 'status': 'Indexed', 'source_fingerprint': identity}]
    chunks = [{'document_id': 'D', 'chunk_id': f'C{i}', 'chunk_text': text, 'embedding_status': 'Indexed'} for i, text in enumerate(texts, 1)]
    (path / 'documents.json').write_text(json.dumps(docs))
    (path / 'chunks.json').write_text(json.dumps(chunks))
    index = faiss.IndexFlatIP(2)
    index.add(np.asarray([[1., 0.]] * len(chunks), dtype='float32'))
    faiss.write_index(index, str(path / 'faiss.index'))
    write_full_text(path, {'sources': {'D': identity}}, docs, raw_pages(fingerprint={'D': identity})['pages'])
    return validate_bundle(path)


class ProbeCostTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def store(self):
        store = GovernanceStore(self.root / 'fixture.db')
        rows = store.save_mini_golden_candidates(candidates(), 'fixture')
        return store, rows

    def test_vp07_09_actual_single_pipeline_capped_candidates_and_multihop_all_hit(self):
        corpus = SimpleNamespace(chunks=lambda: [{'document_id': 'D', 'chunk_id': name, 'text': '必须先确认状态'} for name in 'ABC'])
        retriever = VectorRetriever(corpus)
        retriever.vector_candidates = Mock(return_value=[{'chunk_id': name, 'score': score} for name, score in [('A', .9), ('B', .6), ('C', .1)]])
        trace = {}
        result = retriever.retrieve('状态', {'candidate_k': 2, 'top_k': 1, 'hybrid_search': False, 'rerank': False, 'min_score': 0}, trace=trace)
        self.assertEqual(retriever.vector_candidates.call_count, 1)
        self.assertEqual([row['chunk_id'] for row in trace['candidates']], ['A', 'B'])
        self.assertEqual(trace['candidates'][1]['vector_raw'], .6)
        self.assertEqual([row['chunk_id'] for row in result], ['A'])
        coverage = evidence_coverage(trace, ['A', 'B'])
        self.assertTrue(coverage['final_context']['any_hit'])
        self.assertFalse(coverage['final_context']['all_hit'])
        self.assertEqual(coverage['final_context']['coverage'], .5)
        self.assertEqual(coverage['diagnostic_basis'], 'ranking_context_selection_failure')
        self.assertTrue(trace['timings'])
        self.assertEqual(trace['config']['candidate_k'], 2)

    def test_vp08_probe_valid_evidence_retained_and_missing_legacy_candidate_unknown(self):
        store, rows = self.store()
        retriever = VectorRetriever(SimpleNamespace(chunks=lambda: [{'document_id': 'D', 'chunk_id': 'C1', 'text': '必须先确认状态'}]))
        retriever.vector_candidates = Mock(return_value=[])
        retriever._bm25 = Mock(return_value={})
        probe = store.run_probe(rows[0]['id'], retriever, retriever.corpus.chunks())
        self.assertTrue(probe['passed'])
        self.assertEqual(probe['classification'], 'RETRIEVAL_INCOHERENT')
        self.assertEqual(probe['probe_details']['evidence_coverage']['diagnostic_basis'], 'retrieval_failure')
        self.assertEqual(store.probe_history(rows[0]['id'])[0]['probe_details'], probe['probe_details'])
        self.assertIsNone(evidence_coverage({'final': []}, ['C1'])['candidate_recall']['all_hit'])

    def test_vp11_14_raw_nonchunk_table_detected_related_only_and_judge_errors_uncertain(self):
        store, rows = self.store()
        key = rows[12]['id']
        with store.connection() as connection:
            connection.execute('UPDATE questions SET question=? WHERE id=?', ('设备电池额定电压是多少？', key))
        class Retriever:
            def search(self, *_args, **_kwargs): return []
            def full_text_probe(self, question): return search_full_text(question, raw_pages())
        calls = []
        def judge(question, hits, signals):
            calls.append(signals)
            self.assertIn('48V', signals['full_text_hits'][0]['content'])
            return {'answerable': True, 'reason': 'raw table answers question'}
        result = store.run_probe(key, Retriever(), [], judge)
        self.assertEqual(result['classification'], 'FAKE_NEGATIVE_RISK')
        self.assertEqual(len(calls), 1)
        result = store.run_probe(key, Retriever(), [], lambda *_: {'answerable': False, 'reason': 'related entity but necessary detail missing'})
        self.assertTrue(result['passed'])
        for judge in [lambda *_: 'malformed', lambda *_: (_ for _ in ()).throw(TimeoutError('fixture timeout'))]:
            result = store.run_probe(key, Retriever(), [], judge, fail_on_judge_error=True)
            self.assertFalse(result['passed'])
            self.assertEqual(result['probe_details']['question_validity'], 'needs_review')
        class Incomplete(Retriever):
            def full_text_probe(self, question):
                pages = raw_pages('unrelated')
                pages['coverage']['status'] = 'insufficient'
                return search_full_text(question, pages)
        self.assertFalse(store.run_probe(key, Incomplete(), [], None)['passed'])
        self.assertFalse(store.run_probe(key, SimpleNamespace(search=lambda *_args, **_kwargs: []), [], None)['passed'])

    def test_ds05_refuse_mixed_fulltext_fingerprint_and_checksum(self):
        active = self.root / 'index'
        bundle(active)
        text = json.loads((active / 'full_text.json').read_text())
        text['corpus_fingerprint'] = {'D': 'new'}
        (active / 'full_text.json').write_text(json.dumps(text))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            validate_bundle(active)
        manifest = json.loads((active / 'manifest.json').read_text())
        manifest['artifacts']['full_text.json'] = checksum((active / 'full_text.json').read_bytes())
        (active / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(RetrievalUnavailable):
            VectorRetriever(CorpusStore(active)).full_text_probe('query')

    def test_ds04_atomic_activation_and_failed_post_switch_restore_complete_bundle(self):
        active = self.root / 'index'
        bundle(active)
        retriever = VectorRetriever(CorpusStore(active))
        manager = CorpusManager(retriever, index_dir=active)
        stage = self.root / 'stage'; bundle(stage, 'new')
        with self.assertRaisesRegex(RuntimeError, 'fault'):
            manager.activate_bundle(stage, 'failure', after_activate=lambda: (_ for _ in ()).throw(RuntimeError('fault')))
        self.assertEqual(validate_bundle(active)['manifest']['sources'], {'D': 'old'})
        self.assertIsNone(retriever._index)
        self.assertTrue((self.root / 'index_versions' / 'failure').exists())
        stage = self.root / 'second'; bundle(stage, 'new')
        result = manager.activate_bundle(stage, 'success')
        self.assertEqual(validate_bundle(active)['manifest']['sources'], {'D': 'new'})
        self.assertTrue(Path(result['previous_bundle']).exists())

    def test_ds06_07_supplement_exact_unchanged_artifacts_and_refuse_parser_difference(self):
        active = self.root / 'index'; original = bundle(active)
        preserved = {name: (active / name).read_bytes() for name in ('documents.json', 'chunks.json', 'faiss.index')}
        manager = CorpusManager(VectorRetriever(CorpusStore(active)), index_dir=active)
        def parser(*_args, full_text_pages, **_kwargs):
            full_text_pages.extend(raw_pages(fingerprint={'D': 'old'})['pages'])
            return {**original['documents'][0], 'status': 'Parsed'}, [{**row, 'embedding_status': 'Pending'} for row in original['chunks']]
        with patch('app.corpus_management.discover_documents', return_value=[{'id': 'D'}]), patch('app.corpus_management.current_manifest', return_value={'sources': {'D': 'old'}}):
            result = manager.supplement_full_text(parser=parser, activate=True)
            self.assertTrue(result['result']['content_compatible'])
            self.assertEqual(result['result']['corpus_fingerprint'], {'D': 'old'})
            for name, data in preserved.items(): self.assertEqual((active / name).read_bytes(), data)
            old_target = active.resolve()
            def mismatch(*args, **kwargs):
                record, chunks = parser(*args, **kwargs)
                chunks[0]['chunk_text'] = 'changed'
                return record, chunks
            with self.assertRaisesRegex(ValueError, 'Chunk identity'):
                manager.supplement_full_text(parser=mismatch, activate=True)
            self.assertEqual(active.resolve(), old_target)
            with self.assertRaisesRegex(RuntimeError, 'parse fault'):
                manager.supplement_full_text(parser=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('parse fault')), activate=True)
            self.assertEqual(active.resolve(), old_target)
            self.assertTrue(list((self.root / 'index_versions').glob('*-building')))

    def test_supplement_audit_failure_rolls_back_and_preserves_previous_bundle(self):
        active = self.root / 'index'; original = bundle(active)
        manager = CorpusManager(VectorRetriever(CorpusStore(active)), index_dir=active)
        def parser(*_args, full_text_pages, **_kwargs):
            full_text_pages.extend(raw_pages(fingerprint={'D': 'old'})['pages'])
            return {**original['documents'][0], 'status': 'Parsed'}, original['chunks']
        update = manager._update
        def fail_completed(operation_id, **fields):
            if fields.get('status') == 'completed':
                raise OSError('audit fault')
            return update(operation_id, **fields)
        with patch('app.corpus_management.discover_documents', return_value=[{'id': 'D'}]), patch('app.corpus_management.current_manifest', return_value={'sources': {'D': 'old'}}), patch.object(manager, '_update', side_effect=fail_completed):
            with self.assertRaisesRegex(OSError, 'audit fault'):
                manager.supplement_full_text(parser=parser, activate=True)
        self.assertEqual(validate_bundle(active)['manifest']['sources'], {'D': 'old'})
        self.assertTrue(active.resolve().name.endswith('-previous'))
        self.assertEqual(list(manager._operations.values())[0]['status'], 'failed')

    def test_request_pins_index_chunks_manifest_across_activation_and_rollback(self):
        active = self.root / 'index'; bundle(active, texts=['old text'])
        retriever = VectorRetriever(CorpusStore(active))
        model = SimpleNamespace(encode=lambda *_args, **_kwargs: np.asarray([[1., 0.]], dtype='float32'))
        # Actual FAISS load/search; local embedding is an explicit Stub.
        import sys
        with patch.dict(sys.modules, {'sentence_transformers': SimpleNamespace(SentenceTransformer=lambda *_args, **_kwargs: model)}):
            trace = {}; retriever.retrieve('text', {'candidate_k': 1, 'top_k': 1}, trace=trace)
            self.assertEqual(trace['final'][0]['content'], 'old text')
            manager = CorpusManager(retriever, index_dir=active)
            stage = self.root / 'stage'; bundle(stage, 'new', texts=['new text'])
            entered, finished = threading.Event(), threading.Event()
            def activate():
                entered.set(); manager.activate_bundle(stage, 'new'); finished.set()
            with retriever.snapshot():
                thread = threading.Thread(target=activate); thread.start(); entered.wait(2)
                self.assertFalse(finished.is_set())
                current = {}; retriever.retrieve('text', {'candidate_k': 1, 'top_k': 1}, trace=current)
                self.assertEqual(current['corpus_fingerprint'], {'D': 'old'})
                self.assertEqual(current['final'][0]['content'], 'old text')
            thread.join(3); self.assertTrue(finished.is_set())
            trace = {}; retriever.retrieve('text', {'candidate_k': 1, 'top_k': 1}, trace=trace)
            self.assertEqual(trace['corpus_fingerprint'], {'D': 'new'})
            self.assertEqual(trace['final'][0]['content'], 'new text')

    def test_ct01_04_official_alias_cache_math_zero_and_missing_reasons(self):
        with patch.dict(os.environ, {'RAG_PRICE_CONFIG': ''}):
            usage = {'requested_model': 'deepseek-v4-flash', 'call_started_at': '2026-09-30T12:00:00+00:00', 'prompt_tokens': 100, 'completion_tokens': 20, 'prompt_cache_hit_tokens': 40, 'prompt_cache_miss_tokens': 60}
            result = cost_report('deepseek-v4-flash', [usage])
            self.assertEqual(result['amount'], .00002112)
            self.assertEqual(result['requested_model'], 'deepseek-v4-flash')
            self.assertEqual(result['currency'], 'USD')
            self.assertEqual(result['calls'][0]['billing_period'], 'off_peak')
            self.assertTrue(result['cost_config_version'])
            self.assertEqual(cost_report('unknown', [usage])['reason'], 'model_mismatch')
            self.assertEqual(cost_report('deepseek-v4-flash', [])['reason'], 'usage_missing')
            missing = {key: val for key, val in usage.items() if key not in ('prompt_cache_hit_tokens', 'prompt_cache_miss_tokens')}
            self.assertEqual(cost_report('deepseek-v4-flash', [missing])['reason'], 'cache_usage_missing_or_invalid')
            self.assertEqual(cost_report('deepseek-v4-flash', [{**usage, 'prompt_cache_miss_tokens': 59}])['reason'], 'cache_usage_inconsistent')
            self.assertEqual(cost_report('deepseek-v4-flash', [{**usage, **dict.fromkeys(['prompt_tokens', 'completion_tokens', 'prompt_cache_hit_tokens', 'prompt_cache_miss_tokens'], 0)}])['amount'], 0)
            self.assertIsNone(estimate_cost('deepseek-v4-flash', [missing]))
            historical = copy.deepcopy(result)
            with patch('app.telemetry.price_config', return_value=None): self.assertEqual(cost_report('deepseek-v4-flash', [usage])['reason'], 'price_unavailable')
            self.assertEqual(result, historical)

    def test_ct03_peak_ambiguity_weekend_and_verified_holiday_calendar(self):
        with patch.dict(os.environ, {'RAG_PRICE_CONFIG': ''}):
            usage = {'call_started_at': '2026-09-30T02:00:00Z', 'prompt_tokens': 10, 'completion_tokens': 1, 'prompt_cache_hit_tokens': 0}
            self.assertEqual(cost_report('deepseek-flash', [usage])['reason'], 'billing_period_ambiguous')
            self.assertEqual(cost_report('deepseek-flash', [{**usage, 'call_started_at': '2026-10-03T02:00:00Z'}])['calls'][0]['billing_period'], 'off_peak')
            config = price_config()
            invalid_path = self.root / 'invalid-period.json'
            for invalid_window in [None, [], [[True, 4]], [['1', 4]], [[4, 1]]]:
                invalid_path.write_text(json.dumps({**config, 'peak_hours_utc': invalid_window}))
                with patch.dict(os.environ, {'RAG_PRICE_CONFIG': str(invalid_path)}):
                    self.assertIsNone(price_config())
            config['verified_holiday_calendar'] = {'source_url': 'fixture://verified', 'checked_at': 'fixture', 'dates': {'2026-09-30': False}}
            with patch('app.telemetry.price_config', return_value=config):
                self.assertEqual(cost_report('deepseek-flash', [usage])['calls'][0]['billing_period'], 'peak')
                config['verified_holiday_calendar']['dates']['2026-09-30'] = True
                self.assertEqual(cost_report('deepseek-flash', [usage])['calls'][0]['billing_period'], 'off_peak')

    def test_ct03_reject_invalid_prices_and_keep_fixed_legacy_configuration(self):
        path = self.root / 'prices.json'
        base = {'model': 'fixture', 'currency': 'USD', 'source': 'fixture://official', 'effective_date': '2026-09-30', 'cache_billing': 'provider_hit_counter', 'input_per_million': 2, 'cached_input_per_million': 1, 'output_per_million': 4}
        with patch.dict(os.environ, {'RAG_PRICE_CONFIG': str(path)}):
            for invalid in [True, float('nan'), float('inf'), -1]:
                path.write_text(json.dumps({**base, 'input_per_million': invalid}))
                self.assertIsNone(price_config())
            path.write_text(json.dumps(base))
            self.assertEqual(estimate_cost('fixture', [{'prompt_tokens': 12, 'completion_tokens': 3, 'prompt_cache_hit_tokens': 2}])['amount'], .000034)
            base['cache_billing'] = 'uniform_input'; path.write_text(json.dumps(base))
            self.assertEqual(cost_report('fixture', [{'prompt_tokens': 12, 'completion_tokens': 3}])['amount'], .000036)

    def test_ct05_provider_nonstream_unknown_stream_first_content_and_nested_timing(self):
        provider = DeepSeekProvider(SimpleNamespace(configured=True, model='fixture', base_url='https://fixture.invalid', api_key='fixture', timeout_seconds=1))
        response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({'choices': [{'message': {'content': 'answer'}}], 'usage': {'prompt_tokens': 0, 'completion_tokens': 0}}).encode()
        with patch('urllib.request.urlopen', return_value=response):
            result = provider.complete_with_metrics('system', 'user')
        self.assertIsNone(result['ttft_ms'])
        self.assertEqual(result['input_tokens'], 0)
        self.assertIn('call_started_at', result['usage'])
        lines = [b'data: {"choices":[{"delta":{"role":"assistant"}}]}', b'data: {"choices":[{"delta":{"content":"answer"}}]}', b'data: [DONE]']
        response.__iter__ = Mock(side_effect=lambda: iter(lines))
        with patch('urllib.request.urlopen', return_value=response), patch('app.providers.time.perf_counter', side_effect=[1., 1.02, 1.08]):
            result = provider.complete_with_metrics('system', 'user', stream=True)
        self.assertEqual(result['ttft_ms'], 20)
        self.assertEqual(result['generation_ms'], 80)
        stages = []
        with measure(stages, 'total'):
            with measure(stages, 'generation', 'total'): pass
        self.assertEqual(stages[0]['parent'], 'total')
        self.assertEqual(len(stages), 2)

    def test_qa_uses_actual_retrieval_corpus_and_separates_judge_usage(self):
        active = self.root / 'index'; bundle(active)
        corpus = CorpusStore(active)
        provider = SimpleNamespace(settings=SimpleNamespace(configured=True, model='fixture'), complete_with_metrics=lambda *_args, **_kwargs: {'content': 'answer', 'ttft_ms': None, 'input_tokens': None, 'output_tokens': None, 'usage': {}}, judge=lambda *_: {'correctness': 4})
        service = AiService(SimpleNamespace(approved_aliases=lambda: {}, active_production=lambda: {'id': 'production', 'config': {}}), corpus, provider, False)
        service.retriever.vector_candidates = Mock(return_value=[{'chunk_id': 'C1', 'score': 1.}])
        with patch('app.ai_service.current_manifest', side_effect=AssertionError('must use indexed manifest')):
            answer = service.baseline_preview('状态')
        self.assertEqual(answer['corpus_fingerprint'], {'D': 'old'})
        self.assertEqual(answer['retrieval_trace']['corpus_fingerprint'], {'D': 'old'})
        self.assertEqual(answer['token_usage']['generation'], {})
        self.assertEqual(service.judge('q', 'a', 'a', 'positive')['stages'][0]['stage_name'], 'judge')

    def test_vp10_evaluation_stores_generation_evidence_and_separates_candidate_misses(self):
        from app.evaluation import EvaluationRunner
        execution = {'answer': 'wrong', 'latency_ms': 1, 'retrieval': [{'chunk_id': 'A'}],
                     'retrieval_trace': {'candidates': [{'chunk_id': 'A'}, {'chunk_id': 'B'}], 'final': [{'chunk_id': 'A'}]}}
        runtime = SimpleNamespace(answer=lambda *_: execution, judge=lambda *_: {'correctness': 0, 'completeness': 0, 'faithfulness': 1, 'behavior_pass': True, 'unsupported_claims': []})
        runner = EvaluationRunner(None, runtime)
        item = {'question': 'question', 'reference_answer': 'answer', 'test_category': 'positive', 'evidence': [{'source_chunk_ids': ['A', 'B']}], 'raw': {}}
        result = runner._case_result(item, {})
        self.assertIn('Ranking Failure', result['failure_tags'])
        self.assertNotIn('Retrieval Failure', result['failure_tags'])
        self.assertEqual(result['programmatic_metrics']['evidence_coverage']['final_context']['coverage'], .5)
        execution['retrieval_trace']['final'].append({'chunk_id': 'B'})
        execution['retrieval'].append({'chunk_id': 'B'})
        result = runner._case_result(item, {})
        self.assertIn('Generation Failure', result['failure_tags'])
        self.assertEqual(result['programmatic_metrics']['evidence_coverage']['diagnostic_basis'], 'final_evidence_available')
        execution.pop('retrieval_trace')
        result = runner._case_result(item, {})
        self.assertIsNone(result['programmatic_metrics']['evidence_coverage']['candidate_recall']['all_hit'])

    def test_planner_rejects_same_count_old_chunks_after_pointer_switch(self):
        from app.providers import ProviderUnavailable
        from api_fixture import main
        active = self.root / 'index'; old = bundle(active, texts=['设备 电压：48V'])
        corpus = CorpusStore(active)
        service = AiService(SimpleNamespace(), corpus, None, True)
        manager = CorpusManager(service.retriever, index_dir=active)
        with patch('app.ai_service.current_manifest', return_value={'sources': {'D': 'old'}}):
            self.assertEqual(service._indexed_embeddings(old['chunks']).shape, (1, 2))
        stage = self.root / 'stage'; new = bundle(stage, 'new', texts=['设备 电压：24V'])
        manager.activate_bundle(stage, 'new')
        with patch('app.ai_service.current_manifest', return_value={'sources': {'D': 'new'}}):
            with self.assertRaisesRegex(ProviderUnavailable, 'identity changed'):
                service._indexed_embeddings(old['chunks'])
            self.assertEqual(service._indexed_embeddings(new['chunks']).shape, (1, 2))
        # Endpoint acquisition holds the same lock through plan creation and persistence.
        observed = []
        def coverage_preview(_profile, chunks, embeddings):
            observed.append((chunks, embeddings.copy()))
            return {'plan_id': 'fixture'}
        with patch.object(main, 'corpus', corpus), patch.object(main, 'ai_service', service), patch.object(main.store, 'coverage_preview', side_effect=coverage_preview), patch('app.ai_service.current_manifest', return_value={'sources': {'D': 'new'}}):
            self.assertEqual(main.coverage_preview(main.GenerationRequest())['plan_id'], 'fixture')
        self.assertEqual(observed[0][0], new['chunks'])

    def test_answerability_provider_schema_requires_consistent_category_and_real_references(self):
        response = {'answerable': True, 'confidence': .9, 'reason': 'table supports answer', 'supporting_chunk_ids': [], 'category': 'direct', 'supporting_pages': [{'document_id': 'D', 'page': 1}]}
        provider = SimpleNamespace(settings=SimpleNamespace(model='fixture'), complete=lambda *_args, **_kwargs: json.dumps(response))
        service = AiService(None, None, provider, False)
        signals = {'full_text_hits': raw_pages()['pages']}
        self.assertTrue(service.answerability_check('question', [], signals)['answerable'])
        response['supporting_pages'][0]['page'] = 99
        from app.providers import ProviderUnavailable
        with self.assertRaises(ProviderUnavailable): service.answerability_check('question', [], signals)
        response.update(supporting_pages=[], answerable=False)
        with self.assertRaises(ProviderUnavailable): service.answerability_check('question', [], signals)
        response['category'] = 'entity_only'
        self.assertFalse(service.answerability_check('question', [], signals)['answerable'])
        response.update(category='insufficient_information', answerable=None)
        self.assertIsNone(service.answerability_check('question', [], signals)['answerable'])

    def test_fulltext_engine_support_is_distinct_from_active_readiness(self):
        active = self.root / 'index'; active.mkdir()
        store = CorpusStore(active)
        self.assertTrue(store.index_info()['full_text']['supported'])
        self.assertEqual(store.index_info()['full_text']['status'], 'not_collected')
        active.rmdir(); bundle(active)
        self.assertEqual(store.index_info()['full_text']['status'], 'ready')
        self.assertEqual(store.index_info()['corpus_fingerprint'], {'D': 'old'})
        (active / 'full_text.json').write_text('{}')
        self.assertEqual(store.index_info()['full_text']['status'], 'invalid')

    def test_snapshot_freeze_refuses_stale_run_and_preserves_existing_snapshot(self):
        store, rows = self.store()
        run_id = rows[0]['raw']['generation_run_id']
        with store.connection() as connection:
            connection.execute("UPDATE questions SET stage='golden', review_status='approved' WHERE id IN (SELECT id FROM questions WHERE raw_json LIKE ?)", ('%' + run_id + '%',))
            audit = store.generation_run(run_id)['artifacts']['hard_validation']
            audit['corpus_fingerprint'] = {'D': 'old'}
            connection.execute('INSERT OR REPLACE INTO golden_generation_artifacts (generation_run_id, coverage_plan_json, question_plan_json, hard_validation_json) VALUES (?,?,?,?)', (run_id, '[]', '[]', json.dumps(audit)))
        with patch.object(store, 'approval_eligibility', return_value={'can_approve': True}):
            with patch('app.corpus.current_manifest', return_value={'sources': {'D': 'new'}}):
                with self.assertRaisesRegex(ValueError, 'Corpus 已变化'): store.create_generation_snapshot(run_id)
                with self.assertRaisesRegex(ValueError, 'Corpus 已变化'): store.create_dataset_snapshot(rows, run_id)
            self.assertEqual(store.dataset_snapshots(), [])
            with patch('app.corpus.current_manifest', return_value={'sources': {'D': 'old'}}):
                frozen = store.create_generation_snapshot(run_id)
            before = store.dataset_snapshots()
            with patch('app.corpus.current_manifest', return_value={'sources': {'D': 'new'}}):
                self.assertEqual(store.create_generation_snapshot(run_id), frozen)
            self.assertEqual(store.dataset_snapshots(), before)
            with patch('app.corpus.current_manifest', side_effect=[{'sources': {'D': 'old'}}, {'sources': {'D': 'new'}}]):
                with self.assertRaisesRegex(ValueError, 'Corpus 已变化'):
                    store.review_generation_batch([row['id'] for row in rows], 'fixture reviewer', confirmed_manual_review=True)
            self.assertEqual(store.dataset_snapshots(), before)

    def test_r1_model_load_and_encoder_failure_persist_failed_probe_and_block_quality_api(self):
        import sys
        from fastapi.testclient import TestClient
        from api_fixture import main
        store, rows = self.store()
        run_id = rows[0]['raw']['generation_run_id']
        active = self.root / 'index'; bundle(active)
        corpus = CorpusStore(active)
        provider = Mock(settings=SimpleNamespace(configured=True, model='fixture'))
        service = AiService(store, corpus, provider, False)
        client = TestClient(main.app)
        with store.connection() as connection:
            connection.execute("UPDATE golden_generation_runs SET status='completed' WHERE id=?", (run_id,))
            connection.execute('UPDATE questions SET question=? WHERE id=?', ('未备案专利费用？', rows[12]['id']))
        for category, row in [('negative', rows[12]), ('positive', rows[0])]:
            for failure_stage in ('load', 'encode'):
                with self.subTest(category=category, failure_stage=failure_stage):
                    model = SimpleNamespace(encode=Mock(side_effect=RuntimeError('fixture encoder failure')))
                    constructor = Mock(side_effect=RuntimeError('fixture missing local embedding model')) if failure_stage == 'load' else Mock(return_value=model)
                    service.retriever.invalidate()
                    with patch.dict(sys.modules, {'sentence_transformers': SimpleNamespace(SentenceTransformer=constructor)}), patch.object(main, 'store', store), patch.object(main, 'corpus', corpus), patch.object(main, 'ai_service', service):
                        response = client.post(f"/api/governance/questions/{row['id']}/probe")
                        self.assertEqual(response.status_code, 200)
                        result = response.json()
                        self.assertFalse(result['passed'])
                        self.assertEqual(result['classification'], 'RETRIEVAL_EXECUTION_FAILED')
                        self.assertEqual(result['probe_details']['probe_execution_status'], 'failed')
                        self.assertEqual(result['probe_details']['question_validity'], 'needs_review')
                        trace = result['probe_details']['retrieval_trace']
                        self.assertEqual(trace['status'], 'failed')
                        self.assertIsNone(trace['candidates'])
                        self.assertIsNone(trace['final'])
                        self.assertEqual(trace['error']['error_type'], 'RuntimeError')
                        self.assertEqual(store.probe_history(row['id'])[0]['probe_details'], result['probe_details'])
                        self.assertEqual(client.post(f"/api/governance/questions/{row['id']}/qc").status_code, 409)
                        self.assertFalse(store.approval_eligibility(row['id'])['can_approve'])
                        with self.assertRaises(ValueError):
                            store.review_question(row['id'], 'approved', 'fixture', accept_qc_p0=True, reason='must not waive execution failure')
                        qa = client.post('/api/preview/baseline', json={'question': '未备案专利费用？'})
                        self.assertEqual(qa.status_code, 503)
                        self.assertEqual(qa.json()['detail']['code'], 'RETRIEVAL_EXECUTION_FAILED')
                    constructor.assert_called_with('BAAI/bge-small-zh-v1.5', local_files_only=True)
        provider.complete.assert_not_called()
        provider.complete_with_metrics.assert_not_called()

    def test_r1_successful_zero_hit_remains_completed_and_distinct_from_failure(self):
        import sys
        from app.policy import DEFAULT_PIPELINE_CONFIG
        store, rows = self.store()
        active = self.root / 'index'; bundle(active)
        corpus = CorpusStore(active)
        retriever = VectorRetriever(corpus)
        with store.connection() as connection:
            connection.execute('UPDATE questions SET question=? WHERE id=?', ('未备案专利费用？', rows[12]['id']))
        encode = Mock(return_value=np.asarray([[0., 1.]], dtype='float32'))
        with patch.dict(sys.modules, {'sentence_transformers': SimpleNamespace(SentenceTransformer=lambda *_args, **_kwargs: SimpleNamespace(encode=encode))}), patch('app.governance.DEFAULT_PIPELINE_CONFIG', {**DEFAULT_PIPELINE_CONFIG, 'metadata_filter': 'STRICT'}):
            result = store.run_probe(rows[12]['id'], retriever, corpus.chunks())
        self.assertGreater(encode.call_count, 0)
        self.assertTrue(result['passed'])
        self.assertEqual(result['classification'], 'NEGATIVE_VALID')
        self.assertEqual(result['probe_details']['probe_execution_status'], 'completed')
        self.assertEqual(result['probe_details']['retrieval_trace']['status'], 'collected')
        self.assertEqual(result['probe_details']['retrieval_trace']['final'], [])

    def test_r1_bm25_execution_failure_blocks_probe_and_evaluation_without_judge(self):
        import sys
        from app.evaluation import EvaluationRunner
        store, rows = self.store()
        active = self.root / 'index'; bundle(active)
        corpus = CorpusStore(active)
        provider = Mock(settings=SimpleNamespace(configured=True, model='fixture'))
        service = AiService(store, corpus, provider, False)
        service.judge = Mock(side_effect=AssertionError('Judge must not run after retrieval failure'))
        model = SimpleNamespace(encode=lambda *_args, **_kwargs: np.asarray([[1., 0.]], dtype='float32'))
        with patch.dict(sys.modules, {'sentence_transformers': SimpleNamespace(SentenceTransformer=lambda *_args, **_kwargs: model)}), patch.object(service.retriever, '_bm25', side_effect=RuntimeError('fixture lexical index failure')):
            probe = store.run_probe(rows[0]['id'], service.retriever, corpus.chunks())
            self.assertFalse(probe['passed'])
            trace = probe['probe_details']['retrieval_trace']
            self.assertEqual(trace['error']['stage'], 'retrieval_pipeline')
            self.assertEqual(trace['corpus_fingerprint'], {'D': 'old'})
            self.assertTrue(any(stage['stage_name'] == 'bm25' for stage in trace['timings']))
            evaluation_store = Mock()
            EvaluationRunner(evaluation_store, service).execute_baseline('fixture-run', [store.question(rows[0]['id'])], {})
            self.assertEqual(evaluation_store.finish_evaluation_run.call_args.args[1], 'failed')
            evaluation_store.record_evaluation_case.assert_not_called()
            evaluation_store.record_bad_case.assert_not_called()
            service.judge.assert_not_called()
        provider.complete_with_metrics.assert_not_called()
