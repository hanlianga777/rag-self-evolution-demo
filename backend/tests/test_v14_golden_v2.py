"""V1.4 GV01..12 / VP01..06,15..17 / DS01..03: offline fixtures only."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from fastapi.testclient import TestClient
from api_fixture import main
from app.ai_service import AiService
from app.business_import import parse_import, COLUMNS
from app.golden_v2 import build_plan, cluster_vectors, match_pool, validate_golden_candidate
from app.governance import GENERATION_PROFILES, GovernanceStore


class GoldenV2Tests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = GovernanceStore(Path(self.folder.name) / 'isolated.db')
        self.chunks = [{'chunk_id': f'C{i:03d}', 'document_id': 'D', 'document_name': 'manual.pdf', 'page_start': 1, 'chunk_text': '断电后维护设备。'} for i in range(160)]
        self.vectors = np.repeat(np.eye(4, dtype='float32'), 40, axis=0)
        self.profile = {'name': 'mini', **GENERATION_PROFILES['mini']}

    def plan(self):
        return self.store.coverage_preview('mini', self.chunks, self.vectors)

    def candidates(self, plan):
        result = []
        for index, slot in enumerate(plan['slots']):
            negative = slot['evaluation_group'] == 'negative'
            result.append({'question': f"设备场景{index}的维护方法是什么？", 'test_category': slot['evaluation_group'], 'construction_type': 'Ordinary', 'reference_answer': None if negative else '断电后维护设备。', 'evidence': [] if negative else [{'source_chunk_ids': slot['material_chunk_ids']}], 'ablation_attribute': slot['ablation_attribute'], 'negative_subtype': slot.get('negative_subtype'), 'expected_behavior': slot.get('expected_behavior'), 'import_row': index + 2})
        return result

    def test_gv01_04_boundaries_repeatability_profiles_and_merge(self):
        with self.assertRaisesRegex(ValueError, '无法规划'):
            build_plan([], [], self.profile)
        for n in (1, 2, 3, 5):
            plan = build_plan(self.chunks[:n], self.vectors[:n], self.profile)
            self.assertGreaterEqual(plan['final_k'], 1)
            self.assertEqual(sum(c['size'] for c in plan['clusters']), n)
        groups, merges = cluster_vectors(np.eye(5, dtype='float32'), 5)
        self.assertTrue(merges)
        self.assertEqual(sum(map(len, groups)), 5)
        self.assertEqual((groups, merges), cluster_vectors(np.eye(5, dtype='float32'), 5))
        first, second = self.plan(), self.plan()
        self.assertEqual(first, second)
        for name, profile in GENERATION_PROFILES.items():
            plan = build_plan(self.chunks, self.vectors, {'name': name, **profile})
            self.assertEqual(len(plan['slots']), profile['expected_count'])
            for group in ('positive', 'ablation', 'negative'):
                self.assertEqual(sum(s['evaluation_group'] == group for s in plan['slots']), profile[group + '_count'])

    def test_gv05_07_gaps_unused_material_and_honest_fallback(self):
        plan = build_plan(self.chunks, self.vectors, {**self.profile, 'positive_count': 1, 'ablation_count': 0, 'negative_count': 0, 'expected_count': 1})
        self.assertEqual(sum(g['reason'] == 'no_answerable_evidence_slots' for g in plan['gaps']), 3)
        plan = build_plan(self.chunks, self.vectors, self.profile, usage={'C000': 20})
        self.assertNotIn('C000', [s['material_chunk_ids'][0] for s in plan['slots']])
        self.assertEqual(plan['construction_audit']['planned'], {'Ordinary': 20})
        self.assertTrue(all(not s['reused'] for s in plan['slots']))
        one = build_plan(self.chunks[:1], self.vectors[:1], self.profile)
        self.assertEqual(one['reuse_statistics']['reused_slots'], 19)

    def test_equal_twenty_topics_use_all_anchor_capacity_and_separate_evidence(self):
        chunks = [{'chunk_id': f'C{i:04d}', 'document_id': 'D', 'chunk_text': '普通维护材料'} for i in range(800)]
        plan = build_plan(chunks, np.repeat(np.eye(20, dtype='float32'), 40, axis=0), self.profile)
        self.assertEqual(plan['final_k'], 20)
        self.assertEqual(len(plan['coverage']['anchor_topics']), 20)
        self.assertEqual(len(plan['coverage']['evidence_topics']), 12)
        self.assertEqual(sum(g['reason'] == 'no_answerable_evidence_slots' for g in plan['gaps']), 8)
        self.assertTrue(all(c['anchor_quota'] == 1 for c in plan['clusters']))

    def test_specialty_priority_budget_and_bridge_nodes(self):
        chunks = [dict(self.chunks[0], chunk_text='设备A 电压：24V\n设备A 容量：10Ah'), dict(self.chunks[1], chunk_text='设备B 电压：12V'), dict(self.chunks[2], chunk_text='设备B 容量：5Ah')]
        plan = build_plan(chunks, np.ones((3, 2)), self.profile)
        specials = [s for s in plan['slots'] if s['construction_type'] != 'Ordinary']
        self.assertEqual(specials[0]['construction_type'], 'Aggregation')
        self.assertLessEqual(len(specials), 2)
        bridge = build_plan(chunks[1:], np.ones((2, 2)), self.profile)
        self.assertEqual(bridge['slots'][0]['construction_type'], 'Bridge')
        self.assertEqual(len(bridge['slots'][0]['evidence_chunk_ids']), 2)

    def test_gv08_12_pool_topic_gaps_and_stale_plan(self):
        plan = self.plan()
        candidates = self.candidates(plan)
        for item in candidates:
            if item['evidence']:
                item['evidence'][0]['source_chunk_ids'] = ['C000']
        ids = self.store.save_business_candidates(candidates, 'fixture.csv', 'hash')
        preview = self.store.preview_pool_run('mini', ids, self.chunks, plan['plan_id'], question_embedder=lambda _: [1, 0, 0, 0])
        self.assertFalse(preview['valid'])
        self.assertTrue(preview['quota_valid'])
        self.assertTrue(preview['gaps'])
        self.assertIn('available_candidates', preview['gaps'][0])
        with self.assertRaisesRegex(ValueError, 'Coverage Plan'):
            self.store.create_pool_run('mini', ids, self.chunks, plan['plan_id'], question_embedder=lambda _: [1, 0, 0, 0])
        changed = [dict(c) for c in self.chunks]
        changed[0]['chunk_text'] += '改变'
        with self.assertRaisesRegex(ValueError, '已失效'):
            self.store.resolve_coverage_plan('mini', changed, plan['plan_id'])

    def test_gv09_10_11_maximum_matching_and_new_unapproved_versions(self):
        plan = self.plan()
        candidates = self.candidates(plan)
        embeddings = {candidate['question']: next(c['center'] for c in plan['clusters'] if c['cluster_id'] == slot['topic_cluster']) for candidate, slot in zip(candidates, plan['slots'])}
        ids = self.store.save_business_candidates(candidates, 'fixture.csv', 'hash')
        before = self.store.questions()
        embed = embeddings.__getitem__
        preview = self.store.preview_pool_run('mini', ids, self.chunks, plan['plan_id'], question_embedder=embed)
        reverse = self.store.preview_pool_run('mini', list(reversed(ids)), self.chunks, plan['plan_id'], question_embedder=embed)
        self.assertTrue(preview['valid'], preview['gaps'])
        self.assertEqual(preview['matching'], reverse['matching'])
        for result in preview['validations'].values():
            if result['normalized_candidate']['test_category'] == 'negative':
                self.assertEqual(result['evidence_locations'], [])
                self.assertFalse(result['coverage_match']['anchor']['is_evidence'])
        run = self.store.create_pool_run('mini', ids, self.chunks, plan['plan_id'], question_embedder=embed)
        self.assertEqual(run['artifacts']['hard_validation']['frozen_plan'], plan)
        self.store.update_quality_rerun(run['id'], {'status': 'running'}, start=True)
        self.assertTrue(all(self.store.question(key)['review_status'] == 'human_review_pending' for key in run['question_ids']))
        self.assertEqual([self.store.question(q['id']) for q in before], before)
        with self.assertRaises(ValueError):
            self.store.create_generation_snapshot(run['id'])
        # A greedy match fails; an augmenting path must displace flexible A.
        validations = {'A': {'valid': True, 'normalized_candidate': {'test_category': 'positive'}, 'coverage_match': {'eligible_slot_ids': ['Q01', 'Q02']}}, 'B': {'valid': True, 'normalized_candidate': {'test_category': 'positive'}, 'coverage_match': {'eligible_slot_ids': ['Q01']}}}
        tiny = {**plan, 'profile': {'positive_count': 2}, 'slots': plan['slots'][:2]}
        self.assertEqual(match_pool(tiny, validations)['matching'], {'Q01': 'B', 'Q02': 'A'})

    def test_vp01_06_shared_validation_locations_paraphrase_construction(self):
        chunks = [{'chunk_id': 'C1', 'document_id': 'D', 'document_name': 'manual.pdf', 'page_start': 1, 'chunk_text': '设备A 电压：24V'}, {'chunk_id': 'C2', 'document_id': 'D', 'page_start': 2, 'chunk_text': '设备A 容量：10Ah'}]
        candidate = {'question': '设备A电压是多少？', 'reference_answer': '设备A的电压为24V', 'test_category': 'positive', 'construction_type': 'Fact', 'evidence': [{'source_chunk_ids': ['C1'], 'evidence_key_points': ['设备A 电压：24V'], 'page_start': 1}]}
        result = validate_golden_candidate(candidate, chunks)
        self.assertTrue(result['valid'], result['blocking_errors'])
        self.assertEqual(result['blocking_errors'], AiService._candidate_errors(candidate, chunks, set()))
        self.assertEqual(result['evidence_locations'][0]['char_start'], 0)
        for evidence in ([{'source_chunk_ids': ['OTHER']}], [{'source_chunk_ids': ['C1'], 'page_start': 9}], [{'source_chunk_ids': ['C1'], 'evidence_key_points': ['不存在的原文']}]):
            self.assertFalse(validate_golden_candidate({**candidate, 'evidence': evidence}, chunks)['valid'])
        self.assertFalse(validate_golden_candidate({**candidate, 'reference_answer': '设备A电压24V，同时支持水下工作'}, chunks)['valid'])
        self.assertFalse(validate_golden_candidate({**candidate, 'construction_type': 'Bridge', 'evidence': [{'source_chunk_ids': ['C1', 'C2']}]}, chunks)['valid'])
        bridge = {**candidate, 'construction_type': 'Bridge', 'reference_answer': '设备A 电压：24V；设备A 容量：10Ah', 'evidence': [{'source_chunk_ids': ['C1', 'C2']}]}
        self.assertTrue(validate_golden_candidate(bridge, chunks)['valid'])
        plan = build_plan(chunks, np.eye(2), self.profile)
        related = validate_golden_candidate(bridge, chunks, plan)['coverage_match']['related_clusters']
        self.assertEqual(set(related), set(plan['chunk_clusters'].values()))
        aggregate = {**candidate, 'construction_type': 'Aggregation', 'evidence': [{'source_chunk_ids': ['C1', 'C2']}], 'reference_answer': '24V'}
        self.assertFalse(validate_golden_candidate(aggregate, chunks)['valid'])
        self.assertTrue(validate_golden_candidate({**candidate, 'test_category': 'ablation', 'ablation_attribute': 'colloquial', 'question': '设备A电压到底是多少呀？'}, chunks)['valid'])
        output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=COLUMNS); writer.writeheader(); writer.writerow({'Question': candidate['question'], 'Reference Answer': candidate['reference_answer'], 'Evaluation Group': 'positive', 'Question Type': 'Fact', 'Evidence': '设备A 电压：24V', 'Document': 'manual.pdf'})
        imported = parse_import(output.getvalue().encode(), 'fixture.csv', chunks, [])
        self.assertEqual(imported['valid_count'], 1)
        self.assertEqual(imported['rows'][0]['validation']['validator_version'], result['validator_version'])

    def test_vp15_17_frozen_generation_keeps_19_slots_and_bounded_refill(self):
        plan = self.plan()
        provider = Mock()
        provider.settings.configured = True
        provider.settings.model = 'offline-stub'
        failing, calls = {'Q01'}, []
        def complete(_system, payload, **kwargs):
            data = json.loads(payload)
            slot = data['coverage_slot']; calls.append(slot)
            return json.dumps({'question': f"设备{slot}如何维护？", 'reference_answer': ('错误事实99V' if slot in failing else '断电后维护设备。') if data['category'] != 'negative' else None}, ensure_ascii=False)
        provider.complete.side_effect = complete
        corpus = Mock(); corpus.chunks.return_value = self.chunks
        service = AiService(self.store, corpus, provider, False)
        centers = {slot['slot']: next(c['center'] for c in plan['clusters'] if c['cluster_id'] == slot['topic_cluster']) for slot in plan['slots']}
        import re
        service.negative_topic_embedding = lambda question: centers[re.search(r'Q\d+', question).group()]
        service.quality_check = Mock(return_value={'priority': 'P2', 'reason': 'fixture'})
        run_id = self.store.start_generation_run('offline-stub', coverage_plan=plan)
        main._run_mini_generation(run_id, self.store, service, corpus)
        partial = self.store.generation_run(run_id)
        self.assertEqual(partial['status'], 'needs_regeneration')
        self.assertEqual(len(partial['question_ids']), 19)
        self.assertEqual(calls.count('Q01'), 2)
        with self.assertRaises(ValueError): self.store.create_generation_snapshot(run_id)
        ids = list(partial['question_ids'])
        failing.clear(); calls.clear()
        self.store.claim_regeneration(run_id, plan['corpus_fingerprint'])
        with patch.object(self.store, 'run_probe', return_value={'status': 'passed'}), patch.object(self.store, 'record_qc'):
            main._run_mini_generation(run_id, self.store, service, corpus, regenerate=True)
        run = self.store.generation_run(run_id)
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(calls, ['Q01'])
        self.assertTrue(set(ids).issubset(run['question_ids']))
        self.assertEqual(run['artifacts']['hard_validation']['frozen_plan'], plan)
        key = run['question_ids'][0]
        item = self.store.question(key)
        with self.store.connection() as conn:
            conn.execute("UPDATE questions SET probe_status='probe_passed', qc_status='qc_passed', review_status='approved' WHERE id=?", (key,))
        changed = self.store.update_question(key, item['question'] + '请说明。', item['reference_answer'], item['evidence'], 'fixture', chunks=self.chunks)
        self.assertEqual((changed['probe_status'], changed['qc_status'], changed['review_status']), ('probe_pending', 'qc_pending', 'human_review_pending'))
        self.assertEqual(self.store.review_history(key)[0]['decision'], 'invalidated')

    def test_two_document_text_evidence_normalizes_idempotently_and_scope_mismatch_blocks(self):
        chunks = [{'chunk_id': 'L', 'document_id': 'left', 'product': 'ModelA', 'page_start': 1, 'chunk_text': 'ModelA 电压：24V'}, {'chunk_id': 'R', 'document_id': 'right', 'product': 'ModelB', 'page_start': 9, 'chunk_text': 'ModelB 容量：10Ah'}]
        candidate = {'question': 'ModelA电压和ModelB容量分别是多少？', 'reference_answer': '24V；10Ah', 'test_category': 'positive', 'evidence': [{'document_id': 'left', 'page_start': 1, 'evidence_key_points': ['ModelA 电压：24V']}, {'document_id': 'right', 'page_start': 9, 'evidence_key_points': ['ModelB 容量：10Ah']}]}
        first = validate_golden_candidate(candidate, chunks)
        self.assertTrue(first['valid'], first['blocking_errors'])
        self.assertEqual([e['source_chunk_ids'] for e in first['normalized_candidate']['evidence']], [['L'], ['R']])
        second = validate_golden_candidate(first['normalized_candidate'], chunks)
        self.assertTrue(second['valid'], second['blocking_errors'])
        self.assertEqual(first['evidence_locations'], second['evidence_locations'])
        wrong = {**candidate, 'question': 'ModelB电压是多少？', 'reference_answer': '24V', 'evidence': [{'source_chunk_ids': ['L']}]}
        self.assertFalse(validate_golden_candidate(wrong, chunks)['valid'])

    def test_review_bridge_proof_uses_necessary_connected_answer_nodes(self):
        chunks = [{'chunk_id': 'C1', 'document_id': 'D', 'chunk_text': '设备A 电压：24V'}, {'chunk_id': 'C2', 'document_id': 'D', 'chunk_text': '设备A 容量：10Ah'}, {'chunk_id': 'C3', 'document_id': 'D', 'chunk_text': '设备B 重量：20kg'}]
        candidate = {'question': '设备A电压和设备B重量是多少？', 'reference_answer': '24V；20kg', 'test_category': 'positive', 'construction_type': 'Bridge', 'evidence': [{'source_chunk_ids': ['C1', 'C2', 'C3']}]}
        result = validate_golden_candidate(candidate, chunks)
        self.assertFalse(result['valid'])
        self.assertEqual(result['construction_checks']['supporting_nodes'], ['C1', 'C3'])
        self.assertFalse(result['construction_checks']['connected'])
        valid = {**candidate, 'question': '设备A电压和容量分别多少？', 'reference_answer': '24V；10Ah', 'evidence': [{'source_chunk_ids': ['C1', 'C2']}]}
        self.assertTrue(validate_golden_candidate(valid, chunks)['valid'])
        self.assertFalse(validate_golden_candidate({**valid, 'evidence': candidate['evidence']}, chunks)['valid'])
        chain = [{'chunk_id': 'origin', 'document_id': 'D', 'chunk_text': 'ModelA 电池：PACK-X'}, {'chunk_id': 'target', 'document_id': 'D', 'chunk_text': 'PACK-X 电压：48V'}]
        linked = {'question': 'ModelA的电池电压是多少？', 'reference_answer': '48V', 'test_category': 'positive', 'construction_type': 'Bridge', 'evidence': [{'source_chunk_ids': ['origin', 'target']}]}
        result = validate_golden_candidate(linked, chain)
        self.assertTrue(result['valid'], result['blocking_errors'])
        self.assertEqual(result['construction_checks']['relations'][0]['relation'], 'entity_reference')
        planned = build_plan(chain, [[1., 0.], [1., 0.]], self.profile)
        self.assertEqual(planned['slots'][0]['requirements']['bridge']['relation'], 'entity_reference')

    def test_review_declared_import_scope_preview_confirm_and_normalized_metadata(self):
        chunks = [{'chunk_id': 'C1', 'document_id': 'D', 'document_name': 'manual.pdf', 'product': 'ModelA', 'version': 'v1', 'chunk_text': 'ModelA 电压：24V'}]
        def csv_data(product, version):
            output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=COLUMNS); writer.writeheader()
            writer.writerow({'Question': '电压是多少？', 'Reference Answer': '24V', 'Evaluation Group': 'positive', 'Evidence': 'ModelA 电压：24V', 'Document': 'manual.pdf', 'Product': product, 'Version': version})
            return output.getvalue().encode()
        with patch.object(main, 'store', self.store), patch.object(main.corpus, 'chunks', return_value=chunks), patch.object(main.ai_service, '_indexed_embeddings', return_value=np.ones((1, 2))), patch.object(main.ai_service.provider, 'complete', side_effect=AssertionError('Provider forbidden')):
            client = TestClient(main.app); headers = {'Origin': 'http://127.0.0.1:5174'}
            before = len(self.store.questions())
            for product, version in [('ModelB', 'v1'), ('ModelA', 'v2')]:
                preview = client.post('/api/governance/imports?filename=scope.csv', content=csv_data(product, version), headers=headers)
                self.assertEqual(preview.json()['valid_count'], 0)
                self.assertIn('scope mismatch', str(preview.json()['rows'][0]['errors']))
                confirm = client.post('/api/governance/imports?filename=scope.csv&confirm=true', content=csv_data(product, version), headers=headers)
                self.assertEqual(confirm.status_code, 422)
                self.assertEqual(len(self.store.questions()), before)
            preview = client.post('/api/governance/imports?filename=scope.csv', content=csv_data('ModelA', 'v1'), headers=headers)
            self.assertEqual(preview.json()['valid_count'], 1)
            confirm = client.post('/api/governance/imports?filename=scope.csv&confirm=true', content=csv_data('ModelA', 'v1'), headers=headers)
            self.assertEqual(confirm.status_code, 200)
            saved = self.store.question(confirm.json()['question_ids'][0])
            self.assertEqual((saved['raw']['product'], saved['raw']['version']), ('ModelA', 'v1'))
            self.assertTrue(validate_golden_candidate(saved, chunks)['valid'])

    def test_similarity_reuses_local_embedding_without_download(self):
        from types import SimpleNamespace
        model = Mock(); model.encode.return_value = np.array([[1., 0.]])
        factory = Mock(return_value=model)
        service = AiService(self.store, Mock(), Mock(), True)
        with patch.dict('sys.modules', {'sentence_transformers': SimpleNamespace(SentenceTransformer=factory)}):
            self.assertEqual(service.revision_similarity('问题A', '问题B'), 1.)
        self.assertEqual(factory.call_count, 1)
        self.assertTrue(factory.call_args.kwargs['local_files_only'])
        self.assertEqual(model.encode.call_count, 2)

    def test_review_direct_edit_duplicate_semantic_policy_and_peer_race(self):
        chunks = self.chunks[:1]
        candidates = [{'question': question, 'test_category': 'positive', 'reference_answer': '断电后维护设备。', 'evidence': [{'source_chunk_ids': ['C000']}], 'import_row': index} for index, question in enumerate(('设备A如何维护？', '设备B要怎样保养？'))]
        first, second = self.store.save_business_candidates(candidates, 'duplicates.csv', 'hash')
        original = self.store.question(second)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.store.update_question(second, candidates[0]['question'], candidates[1]['reference_answer'], candidates[1]['evidence'], 'fixture', chunks=chunks)
        self.assertEqual(self.store.question(second), original)
        calls = []
        def similar(a, b):
            calls.append((a, b)); return .99
        with self.assertRaisesRegex(ValueError, 'near duplicate'):
            self.store.update_question(second, '如何维护设备A呢？', candidates[1]['reference_answer'], candidates[1]['evidence'], 'fixture', chunks=chunks, similarity=similar)
        self.assertEqual(len(calls), 1)
        updated = self.store.update_question(second, '断电后保养有哪些注意事项？', candidates[1]['reference_answer'], candidates[1]['evidence'], 'fixture', chunks=chunks, similarity=lambda a, b: .1)
        self.assertEqual((updated['probe_status'], updated['qc_status'], updated['review_status']), ('probe_pending', 'qc_pending', 'human_review_pending'))
        self.assertTrue(updated['raw']['validation']['valid'])
        raced = False
        def mutate_peer(a, b):
            nonlocal raced
            if not raced:
                raced = True
                with self.store.connection() as conn:
                    conn.execute('UPDATE questions SET question=? WHERE id=?', ('维护步骤已更改', first))
            return .1
        with self.assertRaisesRegex(ValueError, '已变化'):
            self.store.update_question(second, '保养前如何准备？', candidates[1]['reference_answer'], candidates[1]['evidence'], 'fixture', chunks=chunks, similarity=mutate_peer)
        self.assertEqual(self.store.question(second)['question'], updated['question'])

    def test_ds01_03_migration_legacy_adapter_and_preview_no_mutation(self):
        with self.store.connection() as conn:
            before = [tuple(row) for row in conn.execute('SELECT * FROM dataset_versions')]
            production = [tuple(row) for row in conn.execute('SELECT * FROM production_versions')]
        self.store.migrate(); self.store.migrate(); self.plan()
        with self.store.connection() as conn:
            self.assertEqual(before, [tuple(row) for row in conn.execute('SELECT * FROM dataset_versions')])
            self.assertEqual(production, [tuple(row) for row in conn.execute('SELECT * FROM production_versions')])
        legacy = self.store.questions()[0]
        self.assertEqual(legacy['construction_provenance'], 'not_collected')
        self.assertIsNone(legacy['construction_type'])

    def test_api_preview_payload_and_gap_contract_without_provider(self):
        plan = self.plan()
        ids = self.store.save_business_candidates(self.candidates(plan), 'fixture.csv', 'hash')
        with patch.object(main, 'store', self.store), patch.object(main.corpus, 'chunks', return_value=self.chunks), patch.object(main.ai_service, '_indexed_embeddings', return_value=self.vectors), patch.object(main.ai_service, 'negative_topic_embedding', return_value=[1, 0, 0, 0]), patch.object(main.ai_service.provider, 'complete', side_effect=AssertionError('Provider forbidden')):
            client = TestClient(main.app)
            headers = {'Origin': 'http://127.0.0.1:5174'}
            preview = client.post('/api/governance/coverage-preview', json={'profile': 'mini'}, headers=headers)
            self.assertEqual(preview.status_code, 200)
            result = client.post('/api/governance/generation-runs/from-pool/preview', json={'profile': 'mini', 'plan_id': plan['plan_id'], 'question_ids': ids}, headers=headers)
            self.assertEqual(result.status_code, 200)
            self.assertFalse(result.json()['valid'])
            self.assertTrue(result.json()['gaps'])
