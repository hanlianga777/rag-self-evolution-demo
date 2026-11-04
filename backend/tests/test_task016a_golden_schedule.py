"""Disposable Golden price-window checks. Provider responses are local stubs."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from api_fixture import main
from app import paid_schedule as schedule
from app.read_view import generation_progress, revision_progress
import test_generation_partial_slots as generation_fixture
import test_revision_workflow as revision_fixture


OFF = datetime(2026, 11, 4, 0, 59, tzinfo=timezone.utc)
PEAK = datetime(2026, 11, 4, 1, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 4, 4, tzinfo=timezone.utc)


class GoldenScheduleTests(unittest.TestCase):
    setUp = generation_fixture.PartialGenerationTests.setUp
    complete = generation_fixture.PartialGenerationTests.complete
    passed_probe = generation_fixture.PartialGenerationTests.passed_probe

    def test_new_generation_waits_at_peak_without_provider_calls(self):
        key = self.store.start_generation_run('mock-provider', 'mini')
        with patch.object(schedule, 'utc_now', return_value=PEAK), \
             patch.object(main, '_run_quality_rerun'), \
             patch.object(schedule.time, 'sleep', side_effect=SystemExit('offline restart')):
            with self.assertRaises(SystemExit):
                main._run_mini_generation(key, self.store, self.service, self.corpus)
        self.provider.complete.assert_not_called()
        self.assertTrue(generation_progress(self.store, key)['artifacts']['hard_validation']['price_pause']['paused'])

    def test_next_slot_pauses_and_restart_reuses_completed_slot(self):
        clock = [OFF]
        original = self.provider.complete.side_effect
        def complete(*args, **kwargs):
            result = original(*args, **kwargs)
            clock[0] = PEAK
            return result
        self.provider.complete.side_effect = complete
        key = self.store.start_generation_run('mock-provider', 'mini')
        with patch.object(schedule, 'utc_now', side_effect=lambda: clock[0]), \
             patch.object(main, '_run_quality_rerun'), \
             patch.object(schedule.time, 'sleep', side_effect=SystemExit('offline restart')):
            with self.assertRaises(SystemExit):
                main._run_mini_generation(key, self.store, self.service, self.corpus)
        self.assertEqual(self.calls, ['Q01'])
        self.assertEqual(len(self.store.generation_run(key)['question_ids']), 1)
        self.provider.complete.side_effect = original
        with patch.object(schedule, 'utc_now', return_value=AFTER), \
             patch.object(main, '_run_quality_rerun'):
            main._run_mini_generation(key, self.store, self.service, self.corpus)
        self.assertEqual(self.calls.count('Q01'), 1)
        self.assertEqual(len(self.calls), 20)
        self.assertFalse(generation_progress(self.store, key)['artifacts']['hard_validation']['price_pause']['paused'])

    def test_quality_finishes_current_probe_and_qc_before_pausing_next_question(self):
        self.service.quality_check.return_value = {'score': 95, 'priority': 'P2', 'reason': 'fixture'}
        generated = self.service.generate_mini_golden(self.chunks)
        key = self.store.start_generation_run('mock-provider', 'mini')
        rows = self.store.save_mini_golden_candidates(generated['valid_slots'], 'mock-provider',
            coverage_plan=generated['coverage_plan'], hard_validation=generated['hard_validation'], run_id=key)
        ids = [row['id'] for row in rows[:2]]
        self.store.update_quality_rerun(key, {'status': 'running', 'stage': 'probe', 'slots': {}, 'total': 2})
        clock, probes = [OFF], []
        def probe(question_id, *args, **kwargs):
            probes.append(question_id)
            clock[0] = PEAK
            return self.passed_probe(question_id)
        with patch.object(schedule, 'utc_now', side_effect=lambda: clock[0]), \
             patch.object(schedule.time, 'sleep', side_effect=SystemExit('offline restart')), \
             patch.object(self.store, 'run_probe', side_effect=probe):
            with self.assertRaises(SystemExit):
                main._run_quality_rerun(key, ids, self.store, self.service, self.corpus)
        self.assertEqual(probes, ids[:1])
        self.assertEqual(len(self.store.qc_history(ids[0])), 1)
        self.assertEqual(len(self.store.qc_history(ids[1])), 0)
        with patch.object(schedule, 'utc_now', return_value=AFTER), \
             patch.object(self.store, 'run_probe', side_effect=probe):
            main._run_quality_rerun(key, ids, self.store, self.service, self.corpus)
        self.assertEqual(probes, ids)
        self.assertEqual(self.service.quality_check.call_count, 2)


class RevisionScheduleTests(unittest.TestCase):
    setUp = revision_fixture.RevisionWorkflowTests.setUp

    def test_revision_waits_without_material_or_generation_calls_and_is_visible(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        key = self.ids[0]
        run = self.store.start_revision(key, 'ai_regenerate', '修复原题', False, {}, self.chunks)
        service = SimpleNamespace(model='fixture', select_revision_material=Mock(), generate_revision_drafts=Mock())
        corpus = SimpleNamespace(chunks=lambda: self.chunks)
        with patch.object(schedule, 'utc_now', return_value=PEAK), \
             patch.object(schedule.time, 'sleep', side_effect=SystemExit('offline restart')):
            with self.assertRaises(SystemExit):
                main._prepare_revision(run['id'], self.store, service, corpus)
        service.select_revision_material.assert_not_called()
        service.generate_revision_drafts.assert_not_called()
        self.assertTrue(revision_progress(self.store, run['id'])['price_pause']['paused'])


if __name__ == '__main__': unittest.main()
