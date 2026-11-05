"""Offline response contract checks: no network and no fabricated model fields."""
import json
import unittest
from copy import deepcopy
import test_optimization_contract as contracts
drafts=contracts.drafts


class ResponseTests(unittest.TestCase):
    setUp=contracts.OptimizationContractTests.setUp
    run_drafts=contracts.OptimizationContractTests.run_drafts

    def test_only_complete_abc_round_is_accepted(self):
        for count in range(4):
            with self.subTest(count=count):
                response=drafts();response['candidates']=response['candidates'][:count]
                experiment,trace,audit,_,raw=self.run_drafts(response)
                self.assertEqual(len(experiment['candidates']),3 if count==3 else 0)
                self.assertEqual(trace['status'],'completed' if count==3 else 'analysis_exhausted')
                self.assertEqual(audit['provider_raw_text'],raw)
                if count<3:
                    self.assertIn('每轮必须恰好提供A/B/C三套方案',audit['validation_error'])
                    self.assertEqual(experiment['evaluation_budget']['used'],0)

    def test_invalid_candidate_rejects_entire_round_with_reason(self):
        for mutate in [lambda c:c['target_bad_cases'].append('unknown'),
                       lambda c:c['config_diff'].update(min_score='0.1'),
                       lambda c:c['config_diff'].update(min_score=True)]:
            with self.subTest(mutate=mutate):
                response=drafts();mutate(response['candidates'][1])
                experiment,trace,audit,_,_=self.run_drafts(response)
                self.assertEqual(trace['status'],'analysis_exhausted')
                self.assertFalse(experiment['candidates'])
                self.assertEqual(audit['rejected_candidates'][0]['id'],'B')
                self.assertTrue(audit['rejected_candidates'][0]['reason'])
                self.assertEqual(experiment['evaluation_budget']['used'],0)

    def test_labels_and_aliases_are_not_silently_rewritten(self):
        for mutation in ('extra_label','duplicate_label','duplicate_target','shared_parameter'):
            with self.subTest(mutation=mutation):
                response=drafts()
                if mutation=='extra_label':response['candidates'].append({**deepcopy(response['candidates'][0]),'id':'D'})
                elif mutation=='duplicate_label':response['candidates'][1]['id']='A'
                elif mutation=='duplicate_target':response['candidates'][1]['target_bad_cases'].append('BC-EVAL-test-Q1')
                else:response['candidates'][1]['config_diff']['top_k']=6
                experiment,trace,audit,_,raw=self.run_drafts(response)
                self.assertEqual(trace['status'],'analysis_exhausted')
                self.assertFalse(experiment['candidates'])
                self.assertEqual(audit['provider_raw_text'],raw)
                if mutation=='duplicate_target':self.assertIn('重复引用',audit['rejected_candidates'][0]['reason'])

    def test_all_invalid_is_not_success(self):
        response=drafts()
        for c in response['candidates']:
            key=next(k for k in c['config_diff'] if k!='generation_thinking')
            c['config_diff'][key]='6'
        experiment,trace,audit,_,_=self.run_drafts(response)
        self.assertEqual(trace['status'],'analysis_exhausted');self.assertFalse(experiment['candidates'])
        self.assertEqual(len(audit['rejected_candidates']),3)

    def test_only_descriptive_metadata_is_optional(self):
        response=drafts()
        response['candidates'][0].pop('target_group')
        # Historical root labels/assertions are audit metadata, not admission gates.
        response['candidates'][1].update(root_cause_evidence=[{}])
        response['candidates'][1]['evidence_assertions'][0]['observation']={}
        experiment,trace,audit,_,_=self.run_drafts(response)
        self.assertEqual(trace['status'],'completed');self.assertEqual(len(experiment['candidates']),3)
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
        response=drafts()
        experiment,trace,audit,_,_=self.run_drafts(response)
        # Single-pass Agent input annotations must also be saved in this historical fixture.
        with self.store.connection() as connection:
            for row in audit['all_bad_case_audit']:
                case={k:v for k,v in row['result'].items() if k not in {'run_id','question_id'}}
                connection.execute('UPDATE bad_cases SET result_json=? WHERE id=?',(_json(case),row['id']))
        audit.update(token_usage=[{'status':'ok','provider':'FIXTURE','prompt_tokens':12}],
                     cost_estimation={'status':'FIXTURE','amount':0.123},validation_error='FIXTURE old schema failure')
        with self.store.connection() as connection:
            connection.execute('DELETE FROM candidate_configs WHERE experiment_id=?',(experiment['id'],))
            connection.execute("UPDATE experiments SET status='failed',result_json=? WHERE id=?",(_json(audit),experiment['id']))
            connection.execute("UPDATE agent_traces SET status='failed',result_json=?,error_message='FIXTURE' WHERE id=?",(_json(audit),trace['id']))
        return trace['id'],Path(self.directory.name)/'recovery-backup.db'

    def test_transactional_recovery_preserves_failure_usage_and_candidate_semantics(self):
        from app.agent_recovery import recover_saved_response
        from pathlib import Path
        import os
        trace_id,backup=self.failed_source()
        oldest=Path(self.directory.name)/'recovery-20261001.db';oldest.write_bytes(b'old')
        recent=Path(self.directory.name)/'recovery-20261031.db';recent.write_bytes(b'recent')
        os.utime(oldest,(1,1));os.utime(recent,(2,2))
        with self.store.connection() as c:
            before=dict(c.execute('SELECT * FROM agent_traces WHERE id=?',(trace_id,)).fetchone())
            source=dict(c.execute('SELECT * FROM experiments WHERE id=?',(before['experiment_id'],)).fetchone())
        plan=recover_saved_response(self.store,trace_id)
        self.assertFalse(backup.exists())
        recovered=recover_saved_response(self.store,trace_id,apply=True,expected_binding=plan['binding'],backup_path=backup)
        self.assertTrue(backup.exists());self.assertEqual(recovered['status'],'recovered')
        self.assertFalse(oldest.exists());self.assertTrue(recent.exists())
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
