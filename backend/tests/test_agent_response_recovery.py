"""Offline response contract checks: no network and no fabricated model fields."""
import json
import unittest
from copy import deepcopy
import test_optimization_contract as contracts
drafts=contracts.drafts


class ResponseTests(unittest.TestCase):
    setUp=contracts.OptimizationContractTests.setUp
    run_drafts=contracts.OptimizationContractTests.run_drafts

    def test_zero_to_three_without_insufficient_reason(self):
        for count in range(4):
            with self.subTest(count=count):
                response=drafts();response['candidates']=response['candidates'][:count]
                experiment,trace,audit,_,raw=self.run_drafts(response)
                self.assertEqual(len(experiment['candidates']),count)
                self.assertEqual(trace['status'],'completed')
                self.assertNotIn('insufficient_evidence',audit)
                self.assertEqual(audit['provider_raw_text'],raw)
                self.assertEqual(audit['response_status'],'accepted' if count else 'empty')

    def test_partial_keeps_valid_and_records_bad_types_unknown_ids_and_duplicate_configs(self):
        for mutate in [lambda c:c['target_bad_cases'].append('unknown'),
                       lambda c:c['config_diff'].update(top_k='6'),
                       lambda c:c['config_diff'].update(top_k=True),
                       lambda c:c.update(root_cause_evidence=[{}]),
                       lambda c:c['evidence_assertions'][0].update(observation={}),
                       lambda c:c.update(config_diff={'top_k':6})]:
            response=drafts();mutate(response['candidates'][1])
            experiment,trace,audit,_,_=self.run_drafts(response)
            self.assertEqual(trace['status'],'completed')
            self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']],['A','C'])
            self.assertEqual(audit['rejected_candidates'][0]['id'],'B')
            self.assertTrue(audit['rejected_candidates'][0]['reason'])

    def test_labels_and_aliases_are_not_silently_rewritten(self):
        response=drafts();response['candidates'].append({**deepcopy(response['candidates'][0]),'id':'D'})
        experiment,trace,audit,_,_=self.run_drafts(response)
        self.assertEqual(len(experiment['candidates']),3)
        self.assertEqual(audit['rejected_candidates'][0]['id'],'D')
        response=drafts();response['candidates'][1]['id']='A'
        experiment,trace,audit,_,_=self.run_drafts(response)
        self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']],['C'])
        self.assertEqual(len(audit['rejected_candidates']),2)
        response=drafts();response['candidates'][1]['target_bad_cases'].append('BC-EVAL-test-Q1')
        experiment,trace,audit,_,_=self.run_drafts(response)
        self.assertEqual(len(experiment['candidates']),2)
        self.assertIn('重复引用',audit['rejected_candidates'][0]['reason'])

    def test_all_invalid_is_not_success(self):
        response=drafts()
        for c in response['candidates']:c['config_diff']={'top_k':'6'}
        experiment,trace,audit,_,_=self.run_drafts(response)
        self.assertEqual(trace['status'],'failed');self.assertFalse(experiment['candidates'])
        self.assertEqual(len(audit['rejected_candidates']),3)

    def test_only_descriptive_metadata_is_optional(self):
        response=drafts();response['candidates']=response['candidates'][:1]
        response['candidates'][0].pop('target_group')
        experiment,trace,audit,_,_=self.run_drafts(response)
        self.assertEqual(trace['status'],'completed');self.assertEqual(len(experiment['candidates']),1)
        self.assertIsNone(experiment['candidates'][0]['reasoning']['target_group'])
        self.assertNotIn('target_group',audit['parsed_candidates'][0])

    def test_duplicate_json_keys_nonfinite_and_invalid_envelope_are_rejected(self):
        from app.optimization import prepare_response
        for raw in ['{"candidates":[],"candidates":[]}','{"candidates":[],"extra":NaN}','[]','{"candidates":{}}']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                prepare_response(raw,{},[],[],0,1,['A','B','C'],None,[],{})


class RecoveryTests(unittest.TestCase):
    setUp=contracts.OptimizationContractTests.setUp
    run_drafts=contracts.OptimizationContractTests.run_drafts
    def failed_source(self):
        from pathlib import Path
        from app.governance import _json
        response=drafts();response['candidates']=response['candidates'][:1]
        experiment,trace,audit,_,_=self.run_drafts(response)
        audit.update(token_usage=[{'status':'ok','provider':'FIXTURE','prompt_tokens':12}],
                     cost_estimation={'status':'FIXTURE','amount':0.123},validation_error='FIXTURE old schema failure')
        with self.store.connection() as connection:
            connection.execute('DELETE FROM candidate_configs WHERE experiment_id=?',(experiment['id'],))
            connection.execute("UPDATE experiments SET status='failed',result_json=? WHERE id=?",(_json(audit),experiment['id']))
            connection.execute("UPDATE agent_traces SET status='failed',result_json=?,error_message='FIXTURE' WHERE id=?",(_json(audit),trace['id']))
        return trace['id'],Path(self.directory.name)/'recovery-backup.db'

    def test_transactional_recovery_preserves_failure_usage_and_candidate_semantics(self):
        from app.agent_recovery import recover_saved_response
        trace_id,backup=self.failed_source()
        with self.store.connection() as c:
            before=dict(c.execute('SELECT * FROM agent_traces WHERE id=?',(trace_id,)).fetchone())
            source=dict(c.execute('SELECT * FROM experiments WHERE id=?',(before['experiment_id'],)).fetchone())
        plan=recover_saved_response(self.store,trace_id)
        self.assertFalse(backup.exists())
        recovered=recover_saved_response(self.store,trace_id,apply=True,expected_binding=plan['binding'],backup_path=backup)
        self.assertTrue(backup.exists());self.assertEqual(recovered['status'],'recovered')
        new=self.store.experiment(recovered['experiment_id'])
        original=json.loads(before['result_json'])
        self.assertEqual(new['result']['provider_raw_text'],original['provider_raw_text'])
        self.assertEqual(new['result']['parsed_json'],original['parsed_json'])
        self.assertNotIn('insufficient_evidence',new['result'])
        for field in ('token_usage','cost_estimation'):self.assertEqual(new['result'][field],original[field])
        self.assertEqual(new['candidates'][0]['config']['top_k'],6)
        with self.store.connection() as c:
            self.assertEqual(dict(c.execute('SELECT * FROM agent_traces WHERE id=?',(trace_id,)).fetchone()),before)
            self.assertEqual(dict(c.execute('SELECT * FROM experiments WHERE id=?',(source['id'],)).fetchone()),source)
        self.assertEqual(recover_saved_response(self.store,trace_id,apply=True)['status'],'already_recovered')

    def test_stale_binding_and_insert_failure_leave_no_recovery(self):
        from app.agent_recovery import recover_saved_response
        from unittest.mock import patch
        trace_id,backup=self.failed_source();plan=recover_saved_response(self.store,trace_id)
        with self.assertRaises(ValueError):recover_saved_response(self.store,trace_id,apply=True,expected_binding='stale',backup_path=backup)
        self.assertFalse(backup.exists())
        with self.store.connection() as c:
            c.execute("CREATE TRIGGER fail_recovery BEFORE INSERT ON candidate_configs BEGIN SELECT RAISE(ABORT,'FIXTURE rollback'); END")
            count=c.execute('SELECT count(*) FROM experiments').fetchone()[0]
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            recover_saved_response(self.store,trace_id,apply=True,expected_binding=plan['binding'],backup_path=backup)
        with self.store.connection() as c:self.assertEqual(c.execute('SELECT count(*) FROM experiments').fetchone()[0],count)
