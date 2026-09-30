"""P0 identity and atomic Agent checks; all data lives in disposable SQLite."""
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from api_fixture import main
from app.corpus import current_manifest
from app.governance import GovernanceStore
from app.optimization import OptimizationAgent
from app.policy import DEFAULT_PIPELINE_CONFIG
from test_optimization_contract import FixedProvider, drafts


from identity_fixture import completed_baseline

class CurrentIdentityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = GovernanceStore(Path(directory.name) / 'demo.db')
        self.baseline = completed_baseline(self.store)
        self.previous = main.store
        main.store = self.store
        self.addCleanup(setattr, main, 'store', self.previous)
        self.client = TestClient(main.app)

    def trigger(self):
        event = self.store.record_monitoring_event(question='安全问题', answer='错误', bad_case=True, severity='critical', determinable=True)
        return self.store.optimization_trigger_for_event(event['id'])['id']

    def test_current_identity_excludes_latest_sandbox_and_old_experiment(self):
        old = self.store.create_experiment(self.baseline)
        newer = completed_baseline(self.store)
        completed_baseline(self.store, 'sandbox_candidate')
        for path in ('overview', 'optimization', 'pipeline', 'evaluation', 'monitoring'):
            result = self.client.get('/api/' + path).json()
            self.assertEqual(result['current_baseline_id'], newer, path)
            self.assertIsNone(result['current_experiment_id'], path)
        self.assertEqual(self.client.get('/api/optimization').json()['status'], 'not_run')
        self.assertEqual(self.store.experiment(old)['baseline_run_id'], self.baseline)
        self.assertEqual(self.store.active_production()['id'], 'baseline-v1')

    def test_missing_target_uses_positive_evidence_and_rejects_unknown_history(self):
        legacy = completed_baseline(self.store, None)
        self.assertEqual(self.store.current_baseline_identity()['current_baseline_id'], legacy)
        with self.store.connection() as connection:
            connection.execute("UPDATE evaluation_runs SET judge_json='{}' WHERE id=?", (legacy,))
        self.assertEqual(self.store.current_baseline_identity()['current_baseline_id'], self.baseline)
        candidate = completed_baseline(self.store, None)
        experiment = self.store.create_experiment(self.baseline)
        self.store.save_candidate(experiment, 'R1-A', DEFAULT_PIPELINE_CONFIG, {'round': 1})
        self.store.finish_candidate(experiment + '-R1-A', 'evaluated', {'evaluation_run_id': candidate})
        self.assertEqual(self.store.current_baseline_identity()['current_baseline_id'], self.baseline)

    def test_confirm_is_transactional_idempotent_and_round_zero_starts_round_one(self):
        trigger = self.trigger()
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: self.store.confirm_optimization_trigger(trigger, 'reviewer'), range(2)))
        self.assertEqual(results[0]['optimization_run_id'], results[1]['optimization_run_id'])
        context = results[0]['optimization_run_id']
        self.assertEqual(self.store.experiment(context)['result']['round'], 0)
        provider = FixedProvider(json.dumps(drafts()))
        generated = OptimizationAgent(self.store, provider).generate(self.baseline, trigger)
        self.assertEqual(provider.prompt["monitoring_context"]["trigger"]["id"], trigger)
        self.assertEqual(provider.prompt["monitoring_context"]["event"]["question"], "安全问题")
        self.assertEqual(provider.prompt["monitoring_context"]["event"]["source"]["production_version_id"], "baseline-v1")
        self.assertEqual(generated["result"]["monitoring_context"], provider.prompt["monitoring_context"])
        self.assertEqual(generated['id'], context)
        self.assertEqual({row['reasoning']['round'] for row in generated['candidates']}, {1})
        with self.store.connection() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM approvals WHERE gate='monitoring_trigger'").fetchone()[0], 1)
        with self.assertRaisesRegex(ValueError, '全部完成 Sandbox'):
            OptimizationAgent(self.store, FixedProvider(json.dumps(drafts()))).generate(self.baseline, trigger)

    def test_invalid_corpus_keeps_trigger_pending_and_blocks_release_guards(self):
        trigger = self.trigger()
        with patch('app.governance.current_manifest', return_value={'sources': ['changed']}):
            identity = self.store.current_baseline_identity()
            self.assertIsNone(identity['current_baseline_id'])
            self.assertIn('Corpus', identity['baseline_unavailable_reason'])
            with self.assertRaisesRegex(ValueError, 'Corpus'):
                self.store.confirm_optimization_trigger(trigger, 'reviewer')
            with self.assertRaisesRegex(ValueError, 'Corpus'):
                self.store.require_current_baseline(self.baseline)
        self.assertEqual(self.store.optimization_trigger(trigger)['status'], 'pending_human_confirm')
        self.assertIsNone(self.store.optimization_trigger(trigger)['optimization_run_id'])

    def test_new_golden_invalidates_old_baseline(self):
        with self.store.connection() as connection:
            snapshot = {'question_ids': ['Q2'], 'questions': [{'id': 'Q2'}], 'corpus_fingerprint': current_manifest()['sources']}
            connection.execute("INSERT INTO dataset_versions VALUES ('GD-new', 'approved', 'human_review', ?, '2099')", (json.dumps(snapshot),))
        self.assertIsNone(self.store.current_baseline_identity()['current_baseline_id'])
        self.assertIn('Baseline', self.store.current_baseline_identity()['baseline_unavailable_reason'])

    def test_failed_first_round_reuses_context_and_unknown_experiment_is_readable(self):
        trigger = self.trigger()
        context = self.store.confirm_optimization_trigger(trigger, 'reviewer')['optimization_run_id']
        for response in ('{bad', json.dumps({**drafts(), 'candidates': drafts()['candidates'][:2]})):
            with self.assertRaises(ValueError):
                OptimizationAgent(self.store, FixedProvider(response)).generate(self.baseline, trigger)
            self.assertEqual(self.store.experiment(context)['candidates'], [])
        generated = OptimizationAgent(self.store, FixedProvider(json.dumps(drafts()))).generate(self.baseline, trigger)
        self.assertEqual(generated['id'], context)
        with self.assertRaisesRegex(ValueError, '不存在|不属于'):
            OptimizationAgent(self.store, FixedProvider(json.dumps(drafts()))).generate(self.baseline, experiment_id='missing')

    def test_concurrent_generate_claim_and_provider_has_no_database_write_lock(self):
        entered, release = threading.Event(), threading.Event()
        store = self.store
        class SlowProvider(FixedProvider):
            def complete(self, *args, **kwargs):
                # A write can commit while Provider is waiting.
                with store.connection() as connection:
                    connection.execute("INSERT INTO tool_calls(experiment_id, tool_name, status, result_json, created_at) VALUES ('test', 'test', 'completed', '{}', 'now')")
                entered.set()
                release.wait(3)
                return super().complete(*args, **kwargs)
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(OptimizationAgent(self.store, SlowProvider(json.dumps(drafts()))).generate, self.baseline)
            self.assertTrue(entered.wait(2))
            with self.assertRaisesRegex(ValueError, '生成中'):
                OptimizationAgent(self.store, FixedProvider(json.dumps(drafts()))).generate(self.baseline)
            release.set()
            generated = first.result(3)
        self.assertEqual(len(generated['candidates']), 3)
        with self.store.connection() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM experiments').fetchone()[0], 1)

    def test_confirmed_assessed_monitoring_event_starts_without_baseline_bad_cases(self):
        with self.store.connection() as connection:
            connection.execute('DELETE FROM bad_cases WHERE run_id=?', (self.baseline,))
            connection.execute('UPDATE evaluation_case_results SET result_json=? WHERE run_id=?', (json.dumps({'passed': True}), self.baseline))
        self.store.finish_evaluation_run(self.baseline, 'completed', {'gates': {'passed': True}})
        frozen_baseline = self.store.evaluation_run(self.baseline)
        provider = FixedProvider(json.dumps(drafts()))
        with self.assertRaisesRegex(ValueError, '没有真实 Bad Case'):
            OptimizationAgent(self.store, provider).generate(self.baseline)
        self.assertIsNone(provider.prompt)
        self.assertIsNone(self.store.latest_experiment())
        event = self.store.record_monitoring_event(question='生产安全问题', answer='生产错误', bad_case=False, severity='ordinary', determinable=False)
        self.store.assess_monitoring_event(event['id'], bad_case=True, severity='critical')
        trigger = self.store.optimization_trigger_for_event(event['id'])
        with self.assertRaisesRegex(ValueError, '已确认、已判定'):
            OptimizationAgent(self.store, provider).generate(self.baseline, trigger_id=trigger['id'])
        self.assertIsNone(self.store.latest_experiment())
        context = self.store.confirm_optimization_trigger(trigger['id'], 'reviewer')['optimization_run_id']
        response = drafts()
        for candidate in response['candidates']:
            candidate['target_bad_cases'] = [event['id']]
        provider = FixedProvider(json.dumps(response))
        generated = OptimizationAgent(self.store, provider).generate(self.baseline, experiment_id=context)
        self.assertEqual(generated['id'], context)
        self.assertEqual({row['reasoning']['round'] for row in generated['candidates']}, {1})
        self.assertEqual(len(generated['candidates']), 3)
        self.assertEqual(provider.prompt['bad_cases'], [])
        self.assertEqual(provider.prompt['monitoring_target_event_ids'], [event['id']])
        self.assertEqual(provider.prompt['monitoring_context']['event']['id'], event['id'])
        self.assertEqual(generated['result']['source_bad_case_ids'], [])
        self.assertEqual(generated['result']['monitoring_target_event_ids'], [event['id']])
        self.assertTrue(all(row['reasoning']['monitoring_target_event_ids'] == [event['id']] for row in generated['candidates']))
        self.assertEqual(self.store.bad_case_rows(), [])
        self.assertEqual(self.store.evaluation_case_results(self.baseline), [{'question_id': 'Q1', 'passed': True}])
        self.assertEqual(self.store.evaluation_run(self.baseline), frozen_baseline)

    def test_monitoring_only_rejects_invented_or_baseline_target(self):
        with self.store.connection() as connection:
            connection.execute('DELETE FROM bad_cases WHERE run_id=?', (self.baseline,))
        trigger = self.trigger()
        context = self.store.confirm_optimization_trigger(trigger, 'reviewer')['optimization_run_id']
        event_id = self.store.optimization_trigger(trigger)['event_id']
        for target in ('invented-MON-id', 'Q1', 'BC-other-run-Q1'):
            response = drafts()
            for candidate in response['candidates']:
                candidate['target_bad_cases'] = [event_id]
            response['candidates'][1]['target_bad_cases'] = [target]
            with self.assertRaisesRegex(ValueError, 'target_bad_cases'):
                OptimizationAgent(self.store, FixedProvider(json.dumps(response))).generate(self.baseline, trigger)
            self.assertEqual(self.store.experiment(context)['candidates'], [])
            self.assertEqual(self.store.experiment(context)['result']['allowed_values'], [event_id])
        self.assertEqual(self.store.bad_case_rows(), [])

    def test_preview_endpoint_preserves_production_source_across_answer_switch(self):
        from app.ai_service import AiService
        previous_production = self.store.active_production()
        previous_fingerprint = current_manifest()['sources']
        store = self.store
        class SwitchingQaService(AiService):
            def answer(self, question, config):
                with store.connection() as connection:
                    connection.execute("UPDATE production_versions SET config_json=? WHERE status='active'", (json.dumps({'top_k': 6}),))
                    connection.execute("UPDATE production_versions SET id='production-after-answer' WHERE status='active'")
                return {'answer': '原生产配置生成的回答', 'retrieval': [], 'sources': [], 'mode': 'local', 'model': 'stub', 'latency_ms': 1}
        service = SwitchingQaService(self.store, main.corpus, FixedProvider('{}'), True)
        old_service = main.ai_service
        main.ai_service = service
        self.addCleanup(setattr, main, 'ai_service', old_service)
        response = self.client.post('/api/preview', json={'question': '生产问题'})
        self.assertEqual(response.status_code, 200)
        qa = response.json()['baseline']
        self.assertEqual(qa['version'], previous_production['id'])
        self.assertEqual(qa['config'], previous_production['config'])
        self.assertEqual(qa['corpus_fingerprint'], previous_fingerprint)
        event = self.store.monitoring_events()[0]
        self.assertEqual(event['source'], {'production_version_id': previous_production['id'], 'production_config': previous_production['config'], 'corpus_fingerprint': previous_fingerprint})
        self.assertEqual(event['answer'], '原生产配置生成的回答')
        self.assertEqual(self.store.active_production()['id'], 'production-after-answer')

    def test_provider_failure_and_stale_baseline_result_leave_no_candidates(self):
        trigger = self.trigger()
        context = self.store.confirm_optimization_trigger(trigger, 'reviewer')['optimization_run_id']
        provider = FixedProvider(json.dumps(drafts()))
        with patch.object(provider, 'complete', side_effect=RuntimeError('Provider unavailable')):
            with self.assertRaisesRegex(ValueError, 'Provider unavailable'):
                OptimizationAgent(self.store, provider).generate(self.baseline, trigger)
        self.assertEqual(self.store.experiment(context)['status'], 'failed')
        store = self.store
        class ChangedBaselineProvider(FixedProvider):
            def complete(self, *args, **kwargs):
                completed_baseline(store)
                return super().complete(*args, **kwargs)
        with self.assertRaisesRegex(ValueError, '当前 Baseline'):
            OptimizationAgent(self.store, ChangedBaselineProvider(json.dumps(drafts()))).generate(self.baseline, trigger)
        self.assertEqual(self.store.experiment(context)['candidates'], [])
        self.assertEqual(self.store.experiment(context)['status'], 'failed')

    def test_monitoring_uses_frozen_qa_source_after_production_changes(self):
        source = {'production_version_id': 'old-production', 'production_config': {'top_k': 6}, 'corpus_fingerprint': {'DOC': 'old'}}
        event = self.store.record_monitoring_event(question='生产问题', answer='回答', bad_case=False, severity='ordinary', determinable=False, metrics={'latency_ms': 12}, source=source)
        persisted = self.store.monitoring_events()[0]
        self.assertEqual(persisted['source'], source)
        self.assertEqual(persisted['metrics'], {'latency_ms': 12})
        self.assertEqual(event['source'], source)

    def test_monitoring_prerequisites_return_readable_conflict_and_keep_pending(self):
        trigger = self.trigger()
        with self.store.connection() as connection:
            connection.execute("UPDATE dataset_versions SET status='invalidated' WHERE status='approved'")
        response = self.client.post(f'/api/monitoring/triggers/{trigger}/confirm', json={'decision': 'approved'})
        self.assertEqual(response.status_code, 409)
        self.assertIn('有效 Baseline', response.json()['detail'])
        self.assertEqual(self.store.optimization_trigger(trigger)['status'], 'pending_human_confirm')
        self.assertIsNone(self.store.optimization_trigger(trigger)['optimization_run_id'])

    def test_candidate_comparison_cannot_borrow_previous_baseline_candidates(self):
        from app.ai_service import AiService
        experiment = self.store.create_experiment(self.baseline)
        self.store.save_candidate(experiment, 'R1-A', DEFAULT_PIPELINE_CONFIG, {'round': 1})
        self.store.finish_candidate(experiment + '-R1-A', 'evaluated', {'qualification': {'qualified': True}})
        newer = completed_baseline(self.store)
        service = AiService(self.store, main.corpus, FixedProvider('{}'), True)
        result = service.candidate_preview('问题')
        self.assertEqual(result['status'], 'not_run')
        self.assertEqual(result['current_baseline_id'], newer)
        self.assertIsNone(result['current_experiment_id'])

    def test_storage_failure_rolls_back_entire_candidate_batch(self):
        trigger = self.trigger()
        context = self.store.confirm_optimization_trigger(trigger, 'reviewer')['optimization_run_id']
        with self.store.connection() as connection:
            connection.execute("CREATE TRIGGER fail_second BEFORE INSERT ON candidate_configs WHEN NEW.id LIKE '%-B' BEGIN SELECT RAISE(ABORT, 'forced failure'); END")
        with self.assertRaises(ValueError):
            OptimizationAgent(self.store, FixedProvider(json.dumps(drafts()))).generate(self.baseline, trigger)
        self.assertEqual(self.store.experiment(context)['candidates'], [])
        with self.store.connection() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM agent_traces WHERE status='completed'").fetchone()[0], 0)
        self.assertEqual(self.store.experiment(context)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
