"""D format/retry compatibility in temporary databases; no paid requests."""
import json
import unittest
from unittest.mock import patch
import test_evaluation_context as context
from app.optimization_cycle import claim_cycle


class CompositeRecoveryTests(unittest.TestCase):
    setUp = context.CompositeTests.setUp
    result = context.CompositeTests.result
    provider = context.CompositeTests.provider

    def decision(self):
        return self.store.experiment(self.experiment)['result']['composite']

    def test_unique_short_ids_and_reason_keys_are_normalized(self):
        with self.store.connection() as db:
            for candidate, label in ((self.winner, 'R3-C'), (self.other, 'R2-B')):
                full_id = self.experiment + '-' + label
                db.execute('update candidate_configs set id=? where id=?', (full_id, candidate['id']))
                candidate['id'] = full_id
            state = json.loads(db.execute('select result_json from experiments where id=?', (self.experiment,)).fetchone()[0])
            state['report_confirmation']['winner_id'] = self.winner['id']
            db.execute('update experiments set result_json=? where id=?', (json.dumps(state), self.experiment))
        provider = self.provider()
        value = json.loads(provider.complete.return_value)
        value.update(source_candidates=['R3-C', 'R2-B'], source_reasons={'R3-C':'保留赢家', 'R2-B':'补充查询改写'})
        raw = json.dumps(value)
        provider.complete.return_value = raw
        result = self.store.create_composite(self.experiment, provider)
        self.assertEqual(result['status'], 'generated', result)
        self.assertEqual(self.decision()['suggestion']['source_candidates'], [self.winner['id'], self.other['id']])
        self.assertEqual(self.decision()['attempts'][0]['provider_raw_text'], raw)
        self.assertEqual(self.decision()['attempts'][0]['parsed_json'], value)

    def test_ambiguous_short_id_is_rejected_and_audited(self):
        with self.store.connection() as db:
            db.execute('insert into candidate_configs select ?,experiment_id,status,config_json,reasoning_json,result_json,created_at from candidate_configs where id=?',
                       (self.experiment+'-R2-A', self.winner['id']))
        provider = self.provider()
        value = json.loads(provider.complete.return_value); value['source_candidates'] = ['A', 'B']
        provider.complete.return_value = json.dumps(value)
        result = self.store.create_composite(self.experiment, provider)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('歧义', result['reason'])
        self.assertEqual(result['provider_calls'], 3)
        self.assertEqual(len(result['attempts']), 3)
        self.assertFalse(self.store.candidate(self.experiment+'-D'))

    def test_string_sources_are_wrapped_without_old_two_source_requirement(self):
        provider = self.provider()
        value = json.loads(provider.complete.return_value); value['source_candidates'] = 'A'
        value['changes'][0]['source_candidates'] = 'B'
        provider.complete.return_value = json.dumps(value)
        result = self.store.create_composite(self.experiment, provider)
        self.assertEqual(result['status'], 'generated')
        normalized=self.decision()['attempts'][0]['normalized_suggestion']
        self.assertEqual(normalized['source_candidates'],[self.winner['id']])
        self.assertEqual(normalized['changes'][0]['source_candidates'],[self.other['id']])

    def test_validation_retry_receives_rejection_then_succeeds(self):
        provider = self.provider(); good = provider.complete.return_value
        bad = json.loads(good); bad['changes'][0]['source_candidates'] = ['unknown']
        provider.complete.side_effect = [json.dumps(bad), good]
        result = self.store.create_composite(self.experiment, provider)
        self.assertEqual(result['status'], 'generated', result)
        audit = self.decision()
        self.assertEqual(audit['provider_calls'], 2)
        self.assertIn('D来源', audit['attempts'][0]['validation_error'])
        self.assertIn('保存结果', audit['attempts'][0]['validation_error'])
        self.assertIn('不要求两个来源', provider.complete.call_args.args[0])
        retry = json.loads(provider.complete.call_args.args[1])
        self.assertEqual(retry['validation_rejection']['reason'], audit['attempts'][0]['validation_error'])
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget']['used'], 2)

    def test_invalid_json_retries_and_raw_reply_is_saved_before_next_call(self):
        provider = self.provider(); good = provider.complete.return_value
        replies = iter(['not json', good])
        def complete(*args, **kwargs):
            reply = next(replies)
            if reply == good:
                self.assertEqual(self.decision()['attempts'][0]['provider_raw_text'], 'not json')
            return reply
        provider.complete.side_effect = complete
        self.assertEqual(self.store.create_composite(self.experiment, provider)['status'], 'generated')

    def test_failed_record_can_be_reissued_without_touching_confirmation(self):
        with self.store.connection() as db:
            state = json.loads(db.execute('select result_json from experiments where id=?', (self.experiment,)).fetchone()[0])
            confirmation = state['report_confirmation']
            state['composite'] = {'status':'failed', 'reason':'D来源不属于已验证改善来源', 'provider_calls':1}
            db.execute('update experiments set result_json=? where id=?', (json.dumps(state), self.experiment))
        self.assertEqual(self.store.create_composite(self.experiment, self.provider())['status'], 'generated')
        self.assertEqual(self.decision()['previous_failures'][0]['reason'], 'D来源不属于已验证改善来源')
        self.assertEqual(self.store.experiment(self.experiment)['result']['report_confirmation'], confirmation)

    def test_decline_d_finishes_normally_without_retry(self):
        provider = self.provider(generate=False, diff={})
        result = self.store.create_composite(self.experiment, provider)
        self.assertEqual(result['status'], 'no_effective_composite')
        self.assertEqual(result['provider_calls'], 1)
        self.assertEqual(self.store.recommendation(self.experiment)['result']['recommended_candidate'], self.winner['id'])

    def test_confirmed_cycle_can_resume_d_only(self):
        state = claim_cycle(self.store, self.experiment)
        self.assertEqual(state['phase'], 'composite')
        self.assertEqual(self.store.experiment(self.experiment)['result']['report_confirmation']['winner_id'], self.winner['id'])

    def test_scheduled_failed_d_can_be_reissued(self):
        from app import paid_schedule as schedule
        with self.store.connection() as db:
            state = json.loads(db.execute('select result_json from experiments where id=?', (self.experiment,)).fetchone()[0])
            state['composite'] = {'status':'failed'}
            db.execute('update experiments set result_json=? where id=?', (json.dumps(state), self.experiment))
        with patch.object(schedule, 'wait_for_off_peak'), patch.object(self.store, 'create_composite', return_value={'status':'no_effective_composite'}):
            result = schedule.start_scheduled_composite(self.store, self.provider(), self.experiment)
            self.assertIn(result['status'], {'waiting','running','completed'})
            schedule._composite_workers[(str(self.store.database_path), self.experiment)].join(5)
