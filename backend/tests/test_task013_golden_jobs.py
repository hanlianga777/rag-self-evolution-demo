"""Task 013: disposable/offline recovery checks; never use the formal database."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from api_fixture import main
from app.golden_v2 import build_plan
from app.governance import GENERATION_PROFILES
from app.followups import FollowupJobs


class GoldenRecoveryTests(unittest.TestCase):
    def test_missing_section_uses_content_instead_of_pdf_filename(self):
        chunks = [{'chunk_id': 'C1', 'document_id': 'D', 'document_name': 'source-2026.pdf',
                   'chunk_text': '# 安全与维护\n设备断电后维护。'}]
        plan = build_plan(chunks, np.ones((1, 2)), {'name': 'mini', **GENERATION_PROFILES['mini']})
        self.assertEqual(plan['clusters'][0]['label'], '安全与维护')
        self.assertEqual(plan['clusters'][0]['chunk_ids'], ['C1'])

    def test_missing_representative_heading_does_not_pick_repeated_local_step(self):
        from app.golden_v2 import topic_label
        chunks = [{'document_name': 'manual.pdf', 'chunk_text': '59802530 (02/24)'}]
        chunks += [{'section_path': '3. 输入密码', 'chunk_text': '3. 输入密码'}] * 3
        chunks += [{'section_path': heading, 'chunk_text': heading} for heading in
                   ('设备运行', '开启/关闭遥控器', '播放路线', '紧急停机按钮', '对接站', '快速指南')]
        self.assertEqual(topic_label(chunks), '设备运行与操作')

    def test_probe_reason_fields_keep_content_and_recall_separate(self):
        from app.golden_v2 import probe_reason_fields
        result = {'reason': 'Evidence exists but the production pipeline did not recall it',
                  'probe_details': {'question_validity': 'valid', 'classification': 'RETRIEVAL_INCOHERENT',
                                    'retrieval_coherent': False}}
        fields = probe_reason_fields(result)
        self.assertEqual(fields['question_validity_reason'], '题目有效，原始证据支持参考答案')
        self.assertEqual(fields['retrieval_observation'], '当前 Pipeline 未完整召回题目证据')
        self.assertEqual(result['probe_details']['classification'], 'RETRIEVAL_INCOHERENT')

    def test_followup_restart_reuses_saved_case_and_does_not_stop_on_old_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = FollowupJobs(SimpleNamespace(database_path=Path(directory) / 'test.db'), None)
            path = jobs.path('source', 'low'); path.parent.mkdir(parents=True)
            existing = {'cases': {'Q01': {'scored_result': {'passed': True}, 'attempts': [
                {'status': 'error', 'error': 'old network timeout'}]}}, 'complete': False,
                '_job': {'status': 'running', 'pid': -1}}
            path.write_text(json.dumps(existing))
            seen = []
            def calibration(_runner, _source, _cases, _group, state, save):
                seen.extend(state['cases']); save(); state['complete'] = True
            with patch('app.followups.read_baseline', return_value=({'judge': {}}, [])), \
                 patch('app.followups.calibration_plan', return_value={}), \
                 patch('app.followups.comparison_rows', return_value=[{'题号': 'Q01'}]), \
                 patch('app.followups.run_calibration', side_effect=calibration):
                jobs._run('source', 'low')
            result = json.loads(path.read_text())
            self.assertEqual(seen, ['Q01'])
            self.assertEqual(result['_job']['status'], 'completed')
            self.assertEqual(result['cases'], existing['cases'])

    def test_live_followup_lock_is_not_overwritten_by_recovery(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            jobs = FollowupJobs(SimpleNamespace(database_path=Path(directory) / 'test.db'), None)
            path = jobs.path('source', 'review'); path.parent.mkdir(parents=True)
            original = json.dumps({'cases': {}, 'complete': False, '_job': {'status': 'running', 'pid': -1}})
            path.write_text(original)
            with path.with_suffix('.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                jobs._run('source', 'review')
            self.assertEqual(path.read_text(), original)


class GoldenSlotCheckpointTests(unittest.TestCase):
    from test_generation_partial_slots import PartialGenerationTests as _fixture
    setUp = _fixture.setUp
    complete = _fixture.complete

    def test_generation_request_saved_before_slot_insert_is_reused_after_crash(self):
        from app.evaluation_stage import perform_stage, checkpoint_request
        checkpoints = {}; requests = []; crash = [True]
        original = self.provider.complete.side_effect
        def complete(system, payload, **kwargs):
            data = json.loads(payload)
            def rpc():
                requests.append(data['coverage_slot'])
                return original(system, payload, **kwargs)
            return checkpoint_request('DeepSeek', 'offline-stub', 'complete', payload, rpc)
        self.provider.complete.side_effect = complete
        def stage(slot, attempt, action):
            cp = checkpoints.setdefault((slot, attempt), {'attempts': []})
            return perform_stage(cp, 'generation', action, slot + ':' + str(attempt), automatic=False,
                                 check_stop=lambda: None, on_state=lambda *a, **kw: None)
        def progress(event):
            if event.get('candidate') and crash[0]:
                crash[0] = False
                raise KeyboardInterrupt('restart after result, before slot insert')
        with self.assertRaisesRegex(KeyboardInterrupt, 'restart after result'):
            self.service.generate_mini_golden(self.chunks, on_progress=progress, stage_runner=stage)
        result = self.service.generate_mini_golden(self.chunks, stage_runner=stage)
        self.assertEqual(len(result['valid_slots']), 20)
        self.assertEqual(requests.count('Q01'), 1)
        self.assertEqual(len(requests), 20)

    def test_full_generation_probe_qc_with_faults_and_large_rpc_payloads(self):
        from collections import Counter
        from http.client import IncompleteRead
        import sqlite3
        from app.evaluation_stage import checkpoint_request
        from app.providers import ProviderAPIError, ProviderTimeout
        calls = Counter(); failed = set()
        original = self.provider.complete.side_effect
        errors = {'Q02': ProviderTimeout('offline timeout'), 'Q03': IncompleteRead(b'partial'),
                  'Q04': ProviderAPIError('offline 500', status_code=500),
                  'Q05': ProviderAPIError('offline 429', status_code=429)}
        def complete(system, payload, **kwargs):
            slot = json.loads(payload)['coverage_slot']
            def rpc():
                if slot in errors and slot not in failed:
                    failed.add(slot); raise errors[slot]
                calls['generation:' + slot] += 1
                result = json.loads(original(system, payload, **kwargs))
                result['_raw_padding'] = '材料' * 40000
                return json.dumps(result, ensure_ascii=False)
            return checkpoint_request('DeepSeek', 'offline-stub', 'complete', payload, rpc)
        self.provider.complete.side_effect = complete
        def probe(key, *_a, **_kw):
            def rpc():
                calls['probe:' + key] += 1
                return {'raw_material': '原文' * 30000}
            checkpoint_request('Alibaba', 'offline-embedding', 'embedding', key, rpc)
            _, identity = self.store.capture_quality(key)
            return self.store.record_probe_result(key, {'question_quality': 30, 'golden_answer_quality': 30,
                'evidence_support': 40, 'reason': 'offline evidence',
                'probe_details': {'probe_execution_status': 'completed'}}, execution=identity)
        def qc(item):
            def rpc():
                calls['qc:' + item['id']] += 1
                return {'score': 95, 'priority': 'P2', 'reason': '离线说明' * 3000, 'ablation_valid': True}
            return checkpoint_request('DeepSeek', 'offline-stub', 'qc', item['id'], rpc)
        self.service.quality_check.side_effect = qc
        original_record = self.store.record_qc
        locked = set()
        def record(key, *args, **kwargs):
            if not locked:
                locked.add(key); raise sqlite3.OperationalError('database is locked')
            return original_record(key, *args, **kwargs)
        run_id = self.store.start_generation_run('offline-stub', 'mini')
        with patch.object(self.store, 'run_probe', side_effect=probe), \
             patch.object(self.store, 'record_qc', side_effect=record), \
             patch('app.evaluation_stage.time.sleep'):
            main._run_mini_generation_work(run_id, self.store, self.service, self.corpus)
        run = self.store.generation_run(run_id, qualification=False)
        self.assertEqual(run['status'], 'completed', run['artifacts']['hard_validation'].get('error'))
        state = run['artifacts']['hard_validation']['quality_rerun']
        self.assertEqual(len(run['question_ids']), 20)
        self.assertEqual(state['technical_failed'], 0)
        self.assertEqual(state['qc_passed'], 20)
        self.assertTrue(all(count == 1 for count in calls.values()), calls)
        self.assertEqual(sum(calls.values()), 60)
        self.assertTrue(self.store.job_checkpoints(run_id))


class BaselineReviewStressTests(unittest.TestCase):
    from test_baseline_resume import ResumeTests as _fixture
    setUp = _fixture.setUp
    tearDown = _fixture.tearDown

    def test_full_real_review_orchestration_with_faults_preserves_formal_score(self):
        from collections import Counter
        from copy import deepcopy
        from http.client import IncompleteRead
        import sqlite3
        import threading
        from app.evaluation import EvaluationRunner
        from app.evaluation_stage import checkpoint_request
        from app.providers import ProviderAPIError, ProviderInvalidResponse, ProviderTimeout
        with self.store.connection() as connection:
            snapshot = json.loads(connection.execute("SELECT snapshot_json FROM dataset_versions WHERE id='fixture-golden'").fetchone()[0])
            original = snapshot['questions']
            snapshot['questions'] = [{**original[index % 4], 'id': f'Q{index+1}', 'question': f'Q{index+1}'} for index in range(50)]
            snapshot['question_ids'] = [item['id'] for item in snapshot['questions']]
            connection.execute("UPDATE dataset_versions SET snapshot_json=? WHERE id='fixture-golden'", (json.dumps(snapshot),))
        run_id, items, config = self.runner.start_baseline()
        for index, item in enumerate(items):
            self.store.record_evaluation_case(run_id, item['id'], {'passed': index >= 10})
        self.store.finish_evaluation_run(run_id, 'completed', {'evaluation_complete': True, 'completed': 50,
            'technical_failed': 0, 'overall_score': 80, 'gates': {'passed': False}})
        before = deepcopy(self.store.evaluation_run(run_id)); cases = self.store.evaluation_case_results(run_id)
        calls = Counter(); faults = set(); judge_errors = Counter(); corrections = []
        release = threading.Event(); lock_threads = []; timers = []
        def hold_database():
            ready = threading.Event()
            def hold():
                from contextlib import closing
                with closing(sqlite3.connect(self.store.database_path)) as connection:
                    connection.execute('BEGIN IMMEDIATE'); ready.set(); release.wait(10); connection.rollback()
            thread = threading.Thread(target=hold); thread.start(); lock_threads.append(thread)
            self.assertTrue(ready.wait(3))
            timer = threading.Timer(6.2, release.set); timer.start(); timers.append(timer)
        errors = {'Q1': ProviderTimeout('offline timeout'), 'Q2': IncompleteRead(b'partial'),
                  'Q3': ProviderAPIError('offline 500', status_code=500),
                  'Q4': ProviderAPIError('offline 429', status_code=429)}
        def answer(question, actual_config):
            def rpc():
                if question in errors and question not in faults:
                    faults.add(question); raise errors[question]
                calls['generation:' + question] += 1
                if question == 'Q1' and not lock_threads:
                    hold_database()
                material = {'chunk_id': 'offline-material', 'content': '离线原文' * 8000}
                return {'answer': '离线回答' * 2000, 'retrieval': [material],
                        'retrieval_trace': {'final': [material], 'candidates': [material]}}
            return checkpoint_request('DeepSeek', 'offline-stub', 'generation', {'question': question, 'config': actual_config}, rpc)
        def score(_runner, item, execution, **kwargs):
            def rpc():
                if item['id'] == 'Q5' and judge_errors[item['id']] < 3:
                    judge_errors[item['id']] += 1
                    error = ProviderInvalidResponse('answer quote is missing or not located')
                    error.raw_provider_response = '{"offline_invalid_quote":true}'
                    raise error
                calls['judge:' + item['id']] += 1
                if item['id'] == 'Q5':
                    corrections.append(kwargs.get('judge_correction'))
                return {'passed': True, 'reason': '离线复核' * 2000}
            return checkpoint_request('DeepSeek', 'offline-stub', 'judge', {'question': item['id']}, rpc, reuse=False)
        jobs = FollowupJobs(self.store, self.runtime)
        try:
            with patch.object(self.runtime, 'answer', side_effect=answer), \
                 patch.object(EvaluationRunner, 'score_execution', score), \
                 patch('app.evaluation_stage.time.sleep'):
                jobs._run(run_id, 'review')
        finally:
            release.set()
            for thread in lock_threads: thread.join(3)
            for timer in timers: timer.cancel()
        result = jobs.progress(run_id, 'review')
        self.assertEqual(result['status'], 'completed', result.get('error'))
        self.assertEqual(result['completed'], 20)
        self.assertEqual(result['technical_failed'], 0)
        self.assertEqual(sum(value for key, value in calls.items() if key.startswith('generation:')), 20)
        self.assertEqual(sum(value for key, value in calls.items() if key.startswith('judge:')), 20)
        self.assertEqual(judge_errors['Q5'], 3)
        self.assertTrue(corrections[0], 'Judge correction must include prior invalid response')
        after = self.store.evaluation_run(run_id)
        review = after['result'].pop('baseline_review')
        self.assertTrue(review['complete'])
        saved_result = json.loads(after.pop('result_json')); saved_result.pop('baseline_review')
        self.assertEqual(saved_result, json.loads(before.pop('result_json')))
        self.assertEqual(after, before)
        self.assertEqual(self.store.evaluation_case_results(run_id), cases)
        path = jobs.path(run_id, 'review')
        self.assertNotIn('cases', json.loads(path.read_text()))
        self.assertLess(path.stat().st_size, 20_000)
        with self.store.connection() as connection:
            summary = json.loads(connection.execute('SELECT result_json FROM evaluation_runs WHERE id=?', (run_id,)).fetchone()[0])
        self.assertNotIn('cases', summary['baseline_review'])
        self.assertEqual(len([key for key in self.store.job_checkpoints(run_id) if key.startswith('review:')]), 10)


class GoldenPendingWorkerTests(unittest.TestCase):
    from test_candidate_review_export import CandidateReviewExportTests as _fixture
    setUp = _fixture.setUp
    join_workers = _fixture.join_workers

    def test_created_revision_is_recoverable_before_worker_claim(self):
        row = self.rows[0]
        run = self.store.start_revision(row['id'], 'manual_edit', '离线检查', False,
            {row['id']: {'question': '离线修订问题'}}, main.corpus.chunks())
        self.assertTrue(run.get('auto_resume'))
        self.assertIsNone(run['worker_thread'])
        self.store.interrupt_revision_runs()
        self.assertEqual(self.store.revision_run(run['id'])['status'], 'queued')

    def test_new_generation_and_quality_have_pending_owner_marker(self):
        self.store.update_quality_rerun(self.run_id, {'status': 'running'}, start=True)
        audit = self.store.generation_run(self.run_id, qualification=False)['artifacts']['hard_validation']['quality_rerun']
        self.assertTrue(audit.get('auto_resume'))
        self.assertIsNone(audit['worker_thread'])
        self.store.update_quality_rerun(self.run_id, {'status': 'completed'})
        key = self.store.start_generation_run('offline-stub')
        audit = self.store.generation_run(key, qualification=False)['artifacts']['hard_validation']
        self.assertTrue(audit.get('auto_resume'))
        self.assertIsNone(audit['worker_thread'])

    def test_same_process_pending_claim_expires(self):
        import os
        import time
        owner = {'execution_owner_pid': os.getpid(), 'worker_thread': None, 'worker_claimed_at': time.time()}
        self.assertTrue(main._golden_owner_alive(owner))
        owner['worker_claimed_at'] -= 11
        self.assertFalse(main._golden_owner_alive(owner))


class GoldenAuditStorageTests(unittest.TestCase):
    def test_fiftieth_slot_write_does_not_rewrite_prior_raw_audits(self):
        from app.governance import GovernanceStore
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'test.db')
            run_id = store.start_generation_run('offline-stub', 'medium')
            import time
            audits = {}; sizes = []; elapsed = []
            for index in range(1, 51):
                slot = f'Q{index:02d}'
                audits[slot] = [{'raw_response': '离线原文' * 15000, 'validation_error': None}]
                started = time.perf_counter()
                store.persist_generation_attempt(run_id, None, audits, slot=slot, attempt=1,
                                                 model='offline-stub', slot_complete=True)
                elapsed.append(round((time.perf_counter() - started) * 1000, 3))
                with store.connection() as connection:
                    value = connection.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?', (run_id,)).fetchone()[0]
                sizes.append(len(value.encode()))
            print('GOLDEN_AUDIT_METRICS', json.dumps({'q1_progress_bytes': sizes[0], 'q50_progress_bytes': sizes[-1],
                'q1_ms': elapsed[0], 'q50_ms': elapsed[-1], 'per_slot_raw_bytes': len(json.dumps(audits['Q01'], ensure_ascii=False).encode())}))
            self.assertLess(sizes[-1], sizes[0] * 3, sizes)
            self.assertNotIn('slot_audit', json.loads(value))
            self.assertEqual(store.generation_artifacts(run_id)['slot_audit'], audits)
            self.assertEqual(len([key for key in store.job_checkpoints(run_id) if key.startswith('slot_audit:')]), 50)


class CalibrationSourceStorageTests(unittest.TestCase):
    from test_baseline_resume import ResumeTests as _fixture
    setUp = _fixture.setUp
    tearDown = _fixture.tearDown

    def test_readonly_source_digest_uses_logical_saved_checkpoints(self):
        from scripts.judge_calibration import read_baseline
        from app.judge_replay import source_digest
        key, items, _ = self.runner.start_baseline()
        self.store.update_evaluation_progress(key, {'checkpoints': {'Q1': {'execution': {'answer': 'offline'}, 'attempts': []}}})
        for item in items:
            self.store.record_evaluation_case(key, item['id'], {'passed': True})
        self.store.finish_evaluation_run(key, 'completed', {'evaluation_complete': True, 'completed': 4, 'technical_failed': 0})
        logical = self.store.evaluation_run(key)
        source, cases = read_baseline(self.store.database_path, key)
        self.assertEqual(source['result'], logical['result'])
        self.assertEqual(source_digest(source, cases), source_digest(logical, cases))


class RevisionCheckpointRecoveryTests(unittest.TestCase):
    def test_manual_validation_restart_returns_to_unapplied_validation(self):
        run = {'id': 'revision', 'status': 'validating', 'stage': 'hard_validation', 'mode': 'manual_edit'}
        prepared = []
        def prepare(_key, _chunks, **kwargs):
            self.assertEqual(run['status'], 'queued'); prepared.append(True)
        store = SimpleNamespace(revision_run=lambda _key: run,
            update_revision=lambda _key, **values: run.update(values), prepare_revision=prepare)
        main._prepare_revision('revision', store, SimpleNamespace(revision_similarity=None), SimpleNamespace(chunks=lambda: []))
        self.assertTrue(prepared)
        self.assertNotEqual(run['status'], 'failed')

    def test_saved_material_selection_reply_is_not_paid_again_after_write_failure(self):
        import sqlite3
        from app.evaluation_stage import checkpoint_request
        run = {'id': 'revision', 'mode': 'ai_regenerate', 'status': 'queued', 'stage': 'queued'}
        checkpoints = {}; calls = []; fail = [True]; prepared = []
        def update(_key, **values):
            if 'material_selection' in values and fail[0]:
                fail[0] = False; raise sqlite3.OperationalError('database is locked')
            run.update(values)
        store = SimpleNamespace(revision_run=lambda _key: run, update_revision=update,
            job_checkpoint=lambda _run, key: checkpoints.get(key),
            save_job_checkpoint=lambda _run, key, value: checkpoints.update({key: value}),
            prepare_revision=lambda *args, **kwargs: prepared.append(True))
        def select(_run, _chunks):
            def request():
                calls.append(True); return {'Q1': {'chunk_ids': ['C1']}}
            return checkpoint_request('DeepSeek', 'offline-stub', 'select', {'question': 'Q1'}, request)
        service = SimpleNamespace(select_revision_material=select, model='offline-stub', revision_similarity=None)
        with patch.object(main, '_generate_revision_with_weak_keyword_repair', return_value={'Q1': {}}):
            main._prepare_revision('revision', store, service, SimpleNamespace(chunks=lambda: []))
            main._prepare_revision('revision', store, service, SimpleNamespace(chunks=lambda: []))
        self.assertTrue(prepared)
        self.assertEqual(len(calls), 1)
