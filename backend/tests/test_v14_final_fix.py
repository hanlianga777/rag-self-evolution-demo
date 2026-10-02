"""Final integration regressions: disposable SQLite, Stub calls, virtual Corpus only."""
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from api_fixture import main
from app.full_text import CORPUS_LOCK
from app.golden_v2 import validate_golden_candidate
from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG
from app.retrieval import RetrievalUnavailable
from identity_fixture import completed_baseline


PROBE = {'question_quality': 30, 'golden_answer_quality': 30, 'evidence_support': 40}
QC = {'score': 90, 'priority': 'P2', 'reason': 'Stub QC'}
CHUNKS = [{'chunk_id': 'C1', 'document_id': 'D', 'page_start': 1, 'chunk_text': '设备A 电压：24V'}]


class FinalQualityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = GovernanceStore(Path(self.folder.name) / 'isolated.db')
        self.candidate = {'question': '设备A电压是多少？', 'reference_answer': '设备A的电压为24V',
                          'test_category': 'positive', 'construction_type': 'Fact', 'import_row': 2,
                          'evidence': [{'source_chunk_ids': ['C1'], 'page_start': 1}]}
        self.key = self.store.save_business_candidates([self.candidate], 'fixture.csv', 'fixture')[0]

    def test_i1_shared_normalized_boundaries_reach_probe_qc_and_reject_extra_facts(self):
        for source in ('ai_generated', 'business_import', 'pool', 'manual_edit'):
            payload = {**self.candidate, 'raw': {'source': source}}
            validation = validate_golden_candidate(payload, CHUNKS)
            self.assertTrue(validation['valid'], validation['blocking_errors'])
            with self.store.connection() as connection:
                connection.execute('UPDATE questions SET raw_json=? WHERE id=?', (json.dumps({**validation['normalized_candidate'], 'source': source}), self.key))
            retriever = type('Stub', (), {'search': lambda *_a, **_k: [{'chunk_id': 'C1', 'score': 1}],
                                         'full_text_probe': lambda *_: {'coverage': {'status': 'complete'}, 'matches': []}})()
            probe = self.store.run_probe(self.key, retriever, CHUNKS)
            self.assertTrue(probe['passed'], probe)
            self.assertEqual(self.store.record_qc(self.key, QC, 'passed')['status'], 'qc_passed')
        retriever.search = lambda *_a, **_k: []
        probe = self.store.run_probe(self.key, retriever, CHUNKS)
        self.assertEqual(probe['classification'], 'RETRIEVAL_INCOHERENT')
        self.assertEqual(probe['probe_details']['risk'], 'P1')
        for change in ({'reference_answer': '设备A电压24V，同时支持水下工作'},
                       {'evidence': [{'source_chunk_ids': ['C1'], 'page_start': 9}]},
                       {'construction_type': 'Bridge'}):
            with self.store.connection() as connection:
                payload = {**self.candidate, **change}
                connection.execute('UPDATE questions SET reference_answer=?, evidence_json=?, raw_json=? WHERE id=?',
                                   (payload['reference_answer'], json.dumps(payload['evidence']), json.dumps(payload), self.key))
            self.assertFalse(self.store.run_probe(self.key, retriever, CHUNKS)['passed'])

    def test_i2_delayed_probe_success_failure_cannot_overwrite_edited_or_new_passed_quality(self):
        for fail in (False, True):
            for newer_passed in (False, True):
                started, finish = threading.Event(), threading.Event()
                class Stub:
                    def search(_self, *_args, **_kwargs):
                        started.set(); self.assertTrue(finish.wait(3))
                        if fail:
                            raise RetrievalUnavailable('Stub retrieval failure', {'status': 'failed'})
                        return [{'chunk_id': 'C1', 'score': 1}]
                    def full_text_probe(_self, *_args):
                        return {'coverage': {'status': 'complete'}, 'matches': []}
                with ThreadPoolExecutor(max_workers=1) as workers:
                    future = workers.submit(self.store.run_probe, self.key, Stub(), CHUNKS)
                    self.assertTrue(started.wait(3))
                    current = self.store.question(self.key)
                    self.store.update_question(self.key, current['question'] + '请说明', current['reference_answer'], current['evidence'], 'fixture')
                    if newer_passed:
                        self.store.record_probe_result(self.key, PROBE)
                        self.store.record_qc(self.key, QC, 'passed')
                    before = self.store.question(self.key)
                    history = (self.store.probe_history(self.key), self.store.qc_history(self.key))
                    finish.set()
                    with self.assertRaisesRegex(ValueError, '过期'):
                        future.result(3)
                self.assertEqual(self.store.question(self.key), before)
                self.assertEqual((self.store.probe_history(self.key), self.store.qc_history(self.key)), history)

    def test_i2_delayed_qc_success_failure_depends_on_exact_probe_and_corpus(self):
        for priority in ('P0', 'P2'):
            for edit in (False, True):
                self.store.record_probe_result(self.key, PROBE)
                item, identity = self.store.capture_quality(self.key, qc=True)
                started, finish = threading.Event(), threading.Event()
                def delayed_qc():
                    class Stub:
                        def quality_check(_self, evaluated):
                            self.assertEqual(evaluated['question'], item['question'])
                            started.set(); self.assertTrue(finish.wait(3))
                            return {**QC, 'priority': priority}
                    return main._quality_check(self.store, Stub(), self.key)
                with ThreadPoolExecutor(max_workers=1) as workers:
                    future = workers.submit(delayed_qc); self.assertTrue(started.wait(3))
                    if edit:
                        self.store.update_question(self.key, item['question'] + '请说明', item['reference_answer'], item['evidence'], 'fixture')
                    self.store.record_probe_result(self.key, PROBE)
                    self.store.record_qc(self.key, QC, 'passed')
                    before = self.store.question(self.key)
                    finish.set()
                    with self.assertRaisesRegex(ValueError, '过期'):
                        future.result(3)
                self.assertEqual(self.store.question(self.key), before)
                self.assertEqual(self.store.qc_history(self.key)[0]['result']['priority'], 'P2')
        _, identity = self.store.capture_quality(self.key)
        _, qc_identity = self.store.capture_quality(self.key, qc=True)
        before = self.store.question(self.key)
        with patch('app.governance.current_manifest', return_value={'sources': {'D': 'new'}}):
            with self.assertRaisesRegex(ValueError, '过期'):
                self.store.record_probe_result(self.key, PROBE, execution=identity)
            with self.assertRaisesRegex(ValueError, '过期'):
                self.store.record_qc(self.key, QC, 'passed', execution=qc_identity)
        self.assertEqual(self.store.question(self.key), before)

    def test_i2_review_status_does_not_invalidate_captured_content(self):
        _, identity = self.store.capture_quality(self.key)
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET review_status='human_review_pending', stage='candidate', updated_at='new' WHERE id=?", (self.key,))
        self.assertEqual(self.store.record_probe_result(self.key, PROBE, execution=identity)['status'], 'passed')

    def test_i2_negative_judge_does_not_attach_old_a_judgment_to_new_b(self):
        candidate = {'question': '设备A额定电压是多少？', 'test_category': 'negative', 'construction_type': 'Ordinary',
                     'negative_subtype': 'insufficient_evidence', 'expected_behavior': 'insufficient_evidence', 'evidence': [], 'import_row': 2}
        key = self.store.save_business_candidates([candidate], 'fixture.csv', 'fixture')[0]
        started, finish = threading.Event(), threading.Event()
        stub = type('Stub', (), {'search': lambda *_a, **_k: [], 'full_text_probe': lambda *_: {'coverage': {'status': 'complete'}, 'matches': [{'content': '设备B 额定电压：48V'}]}})()
        def judge(question, *_args):
            self.assertEqual(question, candidate['question'])
            started.set(); self.assertTrue(finish.wait(3))
            return {'answerable': False, 'reason': 'Only equipment B has an answer'}
        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(self.store.run_probe, key, stub, [{'chunk_id': 'B', 'document_id': 'D', 'chunk_text': '设备B 额定电压：48V'}], judge)
            self.assertTrue(started.wait(3))
            self.store.update_question(key, '设备B额定电压是多少？', None, [], 'fixture')
            before = self.store.question(key); finish.set()
            with self.assertRaisesRegex(ValueError, '过期'): future.result(3)
        self.assertEqual(self.store.question(key), before)
        self.assertEqual(self.store.probe_history(key), [])
        self.assertFalse(self.store.approval_eligibility(key)['can_approve'])

    def test_i2_revision_version_and_superseded_identity_reject_late_result(self):
        for change in ('revision', 'superseded'):
            _, identity = self.store.capture_quality(self.key)
            with self.store.connection() as connection:
                if change == 'revision':
                    raw = self.store.question(self.key)['raw']; raw['revision_version'] = 2
                    connection.execute('UPDATE questions SET raw_json=? WHERE id=?', (json.dumps(raw), self.key))
                else: connection.execute("UPDATE questions SET stage='superseded' WHERE id=?", (self.key,))
            before = self.store.question(self.key)
            with self.assertRaisesRegex(ValueError, '过期'): self.store.record_probe_result(self.key, PROBE, execution=identity)
            self.assertEqual(self.store.question(self.key), before)

    def test_i1_legacy_missing_v2_metadata_keeps_factual_check_v2_proof_is_required(self):
        stub = type('Stub', (), {'search': lambda *_a, **_k: [{'chunk_id': 'C1', 'score': 1}],
                                'full_text_probe': lambda *_: {'coverage': {'status': 'complete'}, 'matches': []}})()
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET test_category='ablation', evidence_json=?, raw_json='{}' WHERE id=?",
                               (json.dumps([{'source_chunk_ids': ['C1']}]), self.key))
        legacy_chunks = [{'chunk_id': 'C1', 'text': '设备A 电压：24V'}]
        probe = self.store.run_probe(self.key, stub, legacy_chunks)
        self.assertTrue(probe['passed'])
        self.assertNotIn('candidate_legality', probe['programmatic']['checks'])
        for payload in ({**self.candidate, 'planner_version': 'topic-kmeans-v2', 'evidence': [{'source_chunk_ids': ['C1'], 'page_start': 9}]},
                        {**self.candidate, 'construction_type': 'Bridge'},
                        {**self.candidate, 'planner_version': 'topic-kmeans-v2', 'question': '设备B电压是多少？', 'entity': '设备B'}):
            with self.store.connection() as connection:
                connection.execute("UPDATE questions SET test_category='positive', question=?, evidence_json=?, raw_json=? WHERE id=?",
                                   (payload['question'], json.dumps(payload['evidence']), json.dumps(payload), self.key))
            chunks = [{**CHUNKS[0], 'entity': '设备A'}, {'chunk_id': 'C2', 'document_id': 'D', 'entity': '设备B', 'chunk_text': '设备B 电压：48V'}]
            probe = self.store.run_probe(self.key, stub, chunks)
            self.assertFalse(probe['passed'])
            self.assertFalse(probe['programmatic']['checks']['candidate_legality'])


class FinalCorpusWriteTests(unittest.TestCase):
    def fixture(self, name):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        store = GovernanceStore(Path(folder.name) / 'isolated.db')
        baseline = completed_baseline(store)
        event = store.record_monitoring_event(question='Fixture', answer='Stub', bad_case=True, severity='critical', determinable=True)
        trigger = store.optimization_trigger_for_event(event['id'])['id']
        if name == 'confirm':
            work = lambda: store.confirm_optimization_trigger(trigger, 'fixture')
        elif name == 'claim':
            work = lambda: store.claim_agent_generation(baseline)
        elif name == 'save':
            experiment, *_ = store.claim_agent_generation(baseline)
            work = lambda: store.save_agent_round(experiment, [(f'R1-{label}', {}, {'round': 1, 'candidate_label': label}) for label in 'ABC'], {'source': 'Stub'})
        else:
            experiment = store.create_experiment(baseline, 'direct_release')
            store.save_candidate(experiment, 'A', DEFAULT_PIPELINE_CONFIG, {'candidate_label': 'A'})
            evaluation = completed_baseline(store, target=None)
            store.finish_candidate(experiment + '-A', 'evaluated', {'qualification': {'qualified': True}, 'gates': {'passed': True}, 'regression': {'passed': True}, 'evaluation_run_id': evaluation})
            # Only this lock-interleaving fixture bypasses unrelated release proof;
            # API lifecycle and RL-05 still exercise real release guards.
            self.addCleanup(patch.stopall)
            patch.object(store, 'release_gate_error', return_value=None).start()
            work = lambda: store.publish_candidate(experiment + '-A', 'fixture')
        return store, trigger, work

    def test_i3_all_four_writes_serialize_activation_after_guard_until_commit(self):
        for name in ('publish', 'confirm', 'claim', 'save'):
            with self.subTest(name=name):
                store, _, work = self.fixture(name)
                corpus = {'sources': None}
                from app.corpus import current_manifest
                corpus['sources'] = current_manifest()['sources']
                attempted, changed = threading.Event(), threading.Event()
                held = []
                def activate():
                    acquired = CORPUS_LOCK.acquire(blocking=False)
                    held.append(not acquired)
                    if acquired: CORPUS_LOCK.release()
                    attempted.set()
                    with CORPUS_LOCK: corpus['sources'] = {'D': 'activated'}
                    changed.set()
                original = store.require_current_baseline
                worker = None
                def guard(*args, **kwargs):
                    nonlocal worker
                    result = original(*args, **kwargs)
                    worker = threading.Thread(target=activate); worker.start()
                    self.assertTrue(attempted.wait(3))
                    self.assertEqual(held, [True], name)
                    self.assertFalse(changed.is_set())
                    return result
                with patch('app.governance.current_manifest', side_effect=lambda: corpus), patch.object(store, 'require_current_baseline', side_effect=guard):
                    try: work()
                    finally:
                        if worker: worker.join(3)
                self.assertTrue(changed.is_set())
                with store.connection() as connection:
                    table = {'publish': 'production_versions', 'confirm': 'approvals', 'claim': 'experiments', 'save': 'candidate_configs'}[name]
                    self.assertGreater(connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0], 0)

    def test_i3_activation_first_rejects_without_partial_writes(self):
        for name in ('publish', 'confirm', 'claim', 'save'):
            with self.subTest(name=name):
                store, trigger, work = self.fixture(name)
                tables = ('approvals', 'production_versions', 'experiments', 'candidate_configs', 'agent_traces', 'optimization_triggers')
                def rows():
                    with store.connection() as connection:
                        return {table: [tuple(row) for row in connection.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in tables}
                before = rows()
                with CORPUS_LOCK, patch('app.governance.current_manifest', return_value={'sources': {'D': 'activated'}}):
                    with self.assertRaisesRegex(ValueError, 'Corpus'):
                        work()
                self.assertEqual(rows(), before)
                self.assertEqual(store.optimization_trigger(trigger)['status'], 'pending_human_confirm')

    def test_m6_additive_nullable_columns_allow_confirm_claim_atomic_abc(self):
        store, trigger, _ = self.fixture('confirm')
        with store.connection() as connection:
            connection.execute('ALTER TABLE experiments ADD COLUMN compatible_extra TEXT')
            connection.execute('ALTER TABLE candidate_configs ADD COLUMN compatible_extra TEXT')
        context = store.confirm_optimization_trigger(trigger, 'fixture')['optimization_run_id']
        self.assertEqual(store.claim_agent_generation(store.experiment(context)['baseline_run_id'], trigger)[0], context)
        store.save_agent_round(context, [(f'R1-{label}', {}, {'round': 1}) for label in 'ABC'], {})
        self.assertEqual(len(store.experiment(context)['candidates']), 3)
