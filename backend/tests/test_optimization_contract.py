"""Fixed-provider checks for the V1.3 Optimization Agent contract."""

import json
import tempfile
import unittest
from pathlib import Path

from identity_fixture import completed_baseline
from app.governance import GovernanceStore
from app.optimization import OptimizationAgent
from app.policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, EXCLUDED_AUTOMATIC_PARAMETERS, search_space_contract, validate_candidate_config


def trace_case(root='Retrieval'):
    from diagnostic_fixture import retrieval_case, generation_case
    if root=='Retrieval':
        case,chunks=retrieval_case()
        required=case['programmatic_metrics']['evidence_coverage']['required_chunk_ids']
        case['standard_evidence']=[c['chunk_text'] for c in chunks if c['chunk_id'] in required]
    else:
        case=generation_case(root)
        case.update(standard_evidence=['操作前关闭设备。'],judge_result={'verdict':'FAIL','reason':'fixture failure'})
        for stage in ('candidates','final'):
            case['programmatic_metrics']['retrieval_trace'][stage]=[{'chunk_id':'c','content':'操作前关闭设备。'}]
    return case


def drafts():
    result = {"root_cause_cluster": "coverage", "observed_evidence": ["Q1"], "candidates": [
        {"id": "A", "hypothesis": "depth", "why": "more evidence", "target_bad_cases": ["Q1"], "config_diff": {"top_k": 6}, "risk": "latency"},
        {"id": "B", "hypothesis": "noise", "why": "filter", "target_bad_cases": ["Q1"], "config_diff": {"min_score": 0.1}, "risk": "recall"},
        {"id": "C", "hypothesis": "coverage", "why": "more candidates", "target_bad_cases": ["Q1"], "config_diff": {"candidate_k": 24}, "risk": "latency"},
    ]}
    for candidate in result['candidates']:
        candidate.update(intervention_direction='candidate_recall' if candidate['id']=='C' else 'context_selection', evidence_assertions=[{'target_id':'Q1','observation':'recall_missing' if candidate['id']=='C' else 'ranking_omission'}], parameter_dependencies=[], target_group='fixture检索组', root_cause='Retrieval', root_cause_evidence=candidate['target_bad_cases'], expected_improvement='fixture预期覆盖')
    for row,direction in zip(result['candidates'],('排序与过滤','效率（降档 + 检索补偿）','检索召回增强')):
        row['direction']=direction
    result['candidates'][1]['config_diff']['generation_thinking']='high'
    return result


class FixedProvider:
    def __init__(self, response):
        self.response = response
        self.prompt = None

    def complete(self, system, prompt, **kwargs):
        self.prompt = json.loads(prompt)
        assert kwargs["json_mode"] is True
        assert "config_diff" in system
        return self.response


class OptimizationContractTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        from datetime import datetime, timezone
        from diagnostic_fixture import retrieval_case
        clock=patch('app.paid_schedule.utc_now',return_value=datetime(2026,11,3,16,tzinfo=timezone.utc))
        clock.start();self.addCleanup(clock.stop)
        self.corpus_patch=patch('app.diagnostics._current_corpus',return_value=(retrieval_case()[1],{'corpus':'one'}))
        self.corpus_patch.start();self.addCleanup(self.corpus_patch.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GovernanceStore(Path(self.directory.name) / "demo.db")
        completed_baseline(self.store, run_id="EVAL-test")
        self.store.record_bad_case("EVAL-test", "Q1", "Retrieval", "ordinary", trace_case())

    def run_drafts(self, result):
        # Each response is an independent first round; incomplete real rounds remain blocked.
        self.store = GovernanceStore(Path(self.directory.name) / f"contract-{len(list(Path(self.directory.name).glob('*.db')))}.db")
        completed_baseline(self.store, run_id="EVAL-test")
        self.store.record_bad_case("EVAL-test","Q1","Retrieval","ordinary",trace_case())
        raw = json.dumps(result, ensure_ascii=False)
        provider = FixedProvider(raw)
        try:
            experiment = OptimizationAgent(self.store, provider).generate("EVAL-test")
        except ValueError:
            experiment = self.store.latest_experiment()
        with self.store.connection() as connection:
            trace = connection.execute("SELECT * FROM agent_traces WHERE experiment_id=? ORDER BY id DESC LIMIT 1", (experiment["id"],)).fetchone()
        return experiment, dict(trace), json.loads(trace["result_json"]), provider, raw

    def test_valid_a_b_c_and_prompt_share_policy_values(self):
        experiment, trace, audit, provider, raw = self.run_drafts(drafts())
        self.assertEqual(trace["status"], "completed")
        self.assertEqual(len(experiment["candidates"]), 3)
        self.assertEqual(experiment["candidates"][0]["reasoning"]["proposal"], "more evidence")
        self.assertEqual(experiment["candidates"][0]["reasoning"]["observed_evidence"], ["Q1"])
        self.assertEqual(audit["provider_raw_text"], raw)
        self.assertEqual(provider.prompt['bad_cases'][0]['diagnosis_category'],'检索层问题')
        self.assertTrue(provider.prompt['bad_cases'][0]['reason'])
        self.assertNotIn("all_bad_case_audit",provider.prompt)
        self.assertIn("all_bad_case_audit",audit)
        self.assertIsNone(provider.prompt["goal"]["failed_gates"])
        self.assertEqual(provider.prompt["allowed_parameter_values"], search_space_contract())
        self.assertEqual(set(provider.prompt["allowed_parameter_values"]), set(ALLOWED_SEARCH_SPACE))
        self.assertNotIn("excluded_automatic_parameters",provider.prompt)
        self.assertEqual({key: provider.prompt["allowed_parameter_values"]["multi_query"][key] for key in ("type", "allowed")}, {"type": "boolean false or integer", "allowed": [False, 2, 4, 6]})

    def test_targets_require_current_persisted_ids_and_audit_unknown_references(self):
        for target in ('invented-case-id', 'Baseline 有一题失败', 'Q-other-run'):
            result = drafts()
            result['candidates'][1]['target_bad_cases'] = [target]
            experiment, trace, audit, _, _ = self.run_drafts(result)
            self.assertEqual(trace['status'], 'analysis_exhausted')
            self.assertEqual(experiment['candidates'], [])
            rejected=audit['rejected_candidates'][0]
            self.assertEqual(rejected['id'], 'B')
            self.assertEqual(rejected['field'], 'target_bad_cases')
            self.assertEqual(rejected['actual_value'], [target])
            self.assertEqual(set(rejected['allowed_values']), {'Q1', 'BC-EVAL-test-Q1'})
        result = drafts()
        result['candidates'][0]['target_bad_cases'] = ['BC-EVAL-test-Q1']
        result['candidates'][0]['root_cause_evidence'] = ['BC-EVAL-test-Q1']
        result['candidates'][0]['evidence_assertions'][0]['target_id']='BC-EVAL-test-Q1'
        experiment, trace, _, _, _ = self.run_drafts(result)
        self.assertEqual(trace['status'], 'completed')
        self.assertEqual(experiment['candidates'][0]['reasoning']['observed_evidence'], ['BC-EVAL-test-Q1'])

    def test_prompt_forwards_persisted_gate_and_budget_context_with_identity(self):
        gates = {'passed': False, 'gates': [{'id': 'latency_p99_seconds', 'actual': 12, 'threshold': 10, 'status': 'FAIL', 'passed': False}, {'id': 'positive_correctness', 'actual': 95, 'threshold': 90, 'status': 'PASS', 'passed': True}]}
        self.store.finish_evaluation_run('EVAL-test', 'completed', {'gates': gates})
        provider = FixedProvider(json.dumps(drafts()))
        generated = OptimizationAgent(self.store, provider).generate('EVAL-test')
        self.assertEqual(generated['baseline_run_id'],'EVAL-test')
        self.assertEqual(provider.prompt['goal']['failed_gates'],[gates['gates'][0]])
        self.assertEqual(generated['evaluation_budget']['used'],0)
        self.assertEqual(provider.prompt['bad_cases'][0]['question_id'],'Q1')
        for candidate in generated['candidates']:
            self.store.finish_candidate(candidate['id'], 'failed', {})
        retry = FixedProvider('{bad')
        with self.assertRaises(ValueError):
            OptimizationAgent(self.store, retry).generate('EVAL-test', experiment_id=generated['id'])
        self.assertEqual(self.store.experiment(generated['id'])['evaluation_budget']['used'],3)
        self.assertEqual(retry.prompt['goal']['failed_gates'], [gates['gates'][0]])

    def test_bad_candidate_k_rejects_round_and_preserves_full_raw_trace(self):
        result=drafts();result['candidates'][2]['config_diff']['candidate_k']='32'
        experiment,trace,audit,_,raw=self.run_drafts(result)
        self.assertEqual(trace['status'],'analysis_exhausted')
        self.assertEqual(experiment['candidates'],[])
        self.assertEqual(audit['provider_raw_text'],raw)
        rejected=audit['rejected_candidates'][0]
        self.assertEqual(rejected['field'],'candidate_k')
        self.assertEqual(rejected['actual_value'],'32')
        self.assertIn('format_retry',audit)
        self.assertEqual(experiment['evaluation_budget']['used'],0)

    def test_insufficient_evidence_cannot_persist_partial_round(self):
        for count in (0,1,2):
            response=drafts();response['candidates']=response['candidates'][:count]
            response['insufficient_evidence']='insufficient'
            experiment,trace,audit,_,_=self.run_drafts(response)
            self.assertEqual(trace['status'],'analysis_exhausted')
            self.assertEqual(experiment['candidates'],[])
            self.assertIn('format_retry',audit)

    def test_no_confirmed_target_persists_insufficient_without_provider(self):
        self.store.record_bad_case('EVAL-test','Q1','Unknown','ordinary',{'primary_root_cause':'Unknown','diagnosis':{'status':'disputed'}})
        provider=FixedProvider('must not be called')
        result=OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertIsNone(provider.prompt)
        self.assertEqual(result['candidates'],[])
        self.assertFalse(result['result']['provider_called'])
        self.assertEqual(result['result']['generation_status'],'insufficient_evidence')

    def test_cross_stage_changes_are_allowed_and_raw_audit_is_retained(self):
        response=drafts();response['candidates'][1]['config_diff']['prompt_strategy']='Tiered'
        experiment,trace,audit,_,raw=self.run_drafts(response)
        self.assertEqual(trace['status'],'completed')
        self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']],['A','B','C'])
        self.assertEqual(audit['rejected_candidates'],[])
        self.assertEqual(audit['provider_raw_text'],raw)

    def test_strict_types_and_discrete_values(self):
        for field, value, valid in (
            ("top_k", True, False), ("top_k", False, False), ("top_k", 4, True),
            ("candidate_k", True, False), ("multi_query", False, True),
            ("multi_query", 2, True), ("multi_query", 4, True), ("multi_query", 6, True),
            ("multi_query", True, False), ("multi_query", 0, False), ("multi_query", "4", False),
            ("min_score", False, False), ("hybrid_alpha", True, False),
            ("metadata_filter", "OFF", False), ("metadata_filter", False, False), ("metadata_filter", "INVALID", False),
        ):
            with self.subTest(field=field, value=value):
                check = validate_candidate_config({**DEFAULT_PIPELINE_CONFIG, field: value})
                self.assertEqual(check["valid"], valid)
                if not valid:
                    self.assertEqual(check["issues"][0]["field"], field)

    def test_hybrid_off_and_dependency(self):
        result = drafts()
        result["candidates"][0]["config_diff"] = {"hybrid_search": False}
        result["candidates"][0].update(intervention_direction="candidate_recall", evidence_assertions=[{"target_id":"Q1","observation":"recall_missing"}])
        experiment, trace, _, _, _ = self.run_drafts(result)
        self.assertEqual(trace["status"], "completed")
        self.assertNotIn("hybrid_alpha", experiment["candidates"][0]["config"])

        result = drafts()
        result["candidates"][0]["config_diff"] = {"hybrid_search": False, "hybrid_alpha": 0.5}
        _, trace, audit, _, _ = self.run_drafts(result)
        self.assertEqual(trace["status"], "analysis_exhausted")
        self.assertEqual(audit["rejected_candidates"][0]["field"], "hybrid_alpha")

    def test_cross_field_duplicate_and_excluded_checks(self):
        for diff in ({'candidate_k':4,'top_k':6},{'top_k':6,'temperature':.8},{'top_k':6,'new_parameter':1}):
            response=drafts();response['candidates'][0]['config_diff']=diff
            experiment,trace,audit,_,_=self.run_drafts(response)
            self.assertEqual(trace['status'],'analysis_exhausted')
            self.assertEqual(experiment['candidates'],[])
        response=drafts();response['candidates'][1]['config_diff']={'top_k':6,'generation_thinking':'high'}
        experiment,trace,audit,_,_=self.run_drafts(response)
        self.assertEqual(trace['status'],'analysis_exhausted')
        self.assertIn('共用参数',audit['validation_error'])

    def test_json_parse_failure_retains_raw_text(self):
        provider = FixedProvider("{broken")
        with self.assertRaises(ValueError):
            OptimizationAgent(self.store, provider).generate("EVAL-test")
        experiment = self.store.latest_experiment()
        self.assertEqual(experiment["result"]["provider_raw_text"], "{broken")
        self.assertIsNone(experiment["result"]["parsed_json"])
        self.assertEqual(experiment["result"]["validation_stage"], "json_parse")

    def test_root_cause_is_derived_from_saved_diagnosis(self):
        result=drafts();result['candidates'][1]['root_cause']='Generation'
        experiment,trace,audit,provider,raw=self.run_drafts(result)
        self.assertEqual(trace['status'],'completed')
        self.assertEqual(audit['rejected_candidates'],[])
        self.assertEqual([c['reasoning']['root_cause'] for c in experiment['candidates']],['Retrieval']*3)
        self.assertEqual(provider.prompt['bad_cases'][0]['diagnosis_category'],'检索层问题')

    def test_round2_uses_temporary_saved_results_and_new_configuration(self):
        generated=OptimizationAgent(self.store,FixedProvider(json.dumps(drafts()))).generate('EVAL-test')
        for c in generated['candidates']:self.store.finish_candidate(c['id'],'failed',{})
        response=drafts()
        for row in response['candidates']:row['hypothesis']+=' second round'
        response['candidates'][0]['config_diff']={'query_rewrite':True}
        response['candidates'][1]['config_diff']={'generation_thinking':'low','hyde':True}
        response['candidates'][2]['config_diff']={'prompt_strategy':'Tiered'}
        response['candidates'][2]['direction']='回答策略'
        result=OptimizationAgent(self.store,FixedProvider(json.dumps(response))).generate('EVAL-test',experiment_id=generated['id'])
        new=[c for c in result['candidates'] if c['reasoning'].get('round')==2]
        self.assertEqual(len(new),3)
        self.assertEqual(new[0]['config']['query_rewrite'],True)

    def test_generation_target_allows_retrieval_parameters(self):
        self.store.record_bad_case('EVAL-test','Q1','Generation','ordinary',trace_case('Generation'))
        self.store.record_bad_case('EVAL-test','Q-unknown','Unknown','ordinary',{'primary_root_cause':'Unknown'})
        provider=FixedProvider(json.dumps(drafts()))
        result=OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual(len(result['candidates']),3)
        self.assertEqual([row['question_id'] for row in provider.prompt['bad_cases']],['Q1'])
        self.assertEqual(result['candidates'][0]['reasoning']['root_cause'],'Generation')

    def test_evaluation_audit_is_local_only_not_strategy_input(self):
        self.store.record_bad_case('EVAL-test','Q-risk','Unknown','ordinary',{'failure_tags':['Evidence Pending Review'],'primary_root_cause':'Unknown','diagnosis':{'status':'disputed','reason':'fixture matcher dispute'}})
        provider=FixedProvider(json.dumps(drafts()))
        OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual(len(provider.prompt['bad_cases']),1)
        self.assertNotIn('all_bad_case_audit',provider.prompt)
        audit=self.store.experiment(self.store.latest_experiment()['id'])['result']
        with self.store.connection() as connection:
            audit=json.loads(connection.execute('SELECT result_json FROM agent_traces ORDER BY id DESC LIMIT 1').fetchone()[0])
        self.assertEqual(len(audit['all_bad_case_audit']),2)
        self.assertNotIn('Q-risk',[r['question_id'] for r in provider.prompt['bad_cases']])
        risk=next(row for row in audit['all_bad_case_audit'] if row['question_id']=='Q-risk')
        self.assertNotIn('confidence',risk['diagnostic_view'])
        self.assertEqual(risk['diagnostic_view']['analysis_category'],'insufficient_evidence')
        self.assertFalse(risk['diagnostic_view']['target_eligible'])

    def test_live_owner_survives_import_cleanup_and_old_callbacks(self):
        from unittest.mock import patch
        experiment, *_ = self.store.claim_agent_generation('EVAL-test')
        claim = self.store.experiment(experiment)['result'].get('agent_generation')
        self.store.interrupt_agent_generations()
        self.assertEqual(self.store.experiment(experiment)['status'], 'generating')
        self.assertTrue(claim)
        self.store.save_agent_trace(experiment, 'failed', {}, 'current failure', generation_token=claim['token'])
        self.store.claim_agent_generation('EVAL-test', experiment_id=experiment)
        current = self.store.experiment(experiment)['result']['agent_generation']
        self.store.save_agent_trace(experiment, 'failed', {}, 'late failure', generation_token=claim['token'])
        self.assertEqual(self.store.experiment(experiment)['status'], 'generating')
        with self.assertRaises(ValueError):
            self.store.save_agent_round(experiment, [], {}, generation_token=claim['token'])
        self.store.save_agent_round(experiment, [], {}, generation_token=current['token'])
        self.store.save_agent_trace(experiment, 'failed', {}, 'late same-token failure', generation_token=current['token'])
        self.assertEqual(self.store.experiment(experiment)['status'], 'completed')
        self.store.claim_agent_generation('EVAL-test', experiment_id=experiment)
        with patch('app.governance.os.kill', side_effect=ProcessLookupError):
            self.store.interrupt_agent_generations()
        self.assertEqual(self.store.experiment(experiment)['status'], 'generating')
        self.assertIn('agent_interruption',self.store.experiment(experiment)['result'])

    def test_persistence_response_reuse_revalidates_without_second_provider_call(self):
        import hashlib
        from unittest.mock import patch
        provider = FixedProvider(json.dumps(drafts()))
        provider.request_summary = lambda system,user,**kwargs: {'request_sha256':hashlib.sha256((system+user).encode()).hexdigest()}
        real_complete = provider.complete
        calls = []
        def complete(*args, **kwargs):
            from app.telemetry import record_usage
            calls.append(True)
            record_usage({'provider': 'Stub', 'status': 'ok'})
            return real_complete(*args, **kwargs)
        provider.complete = complete
        with patch.object(self.store, 'save_agent_round', side_effect=ValueError('persistence interrupted')):
            with self.assertRaises(ValueError): OptimizationAgent(self.store,provider).generate('EVAL-test')
        result = OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(result['candidates']), 3)
        self.assertIn('response_reuse',result['result'])

    def test_raw_response_survives_worker_exit_before_validation(self):
        import hashlib
        from unittest.mock import patch
        from app.telemetry import record_usage
        provider=FixedProvider(json.dumps(drafts()))
        provider.request_summary=lambda system,user,**kw: {'request_sha256':hashlib.sha256((system+user).encode()).hexdigest()}
        complete=provider.complete
        calls=[]
        def respond(*args,**kwargs):
            calls.append(True);record_usage({'provider':'Stub','status':'ok'})
            return complete(*args,**kwargs)
        provider.complete=respond
        with patch('app.optimization.prepare_response',side_effect=KeyboardInterrupt('worker exited')):
            with self.assertRaises(KeyboardInterrupt):OptimizationAgent(self.store,provider).generate('EVAL-test')
        experiment=self.store.latest_experiment()
        with self.store.connection() as connection:
            connection.execute("UPDATE experiments SET status='failed' WHERE id=?",(experiment['id'],))
        result=OptimizationAgent(self.store,provider).generate('EVAL-test',experiment_id=experiment['id'])
        self.assertEqual(len(calls),1)
        self.assertEqual(len(result['candidates']),3)

    def test_rpc_response_checkpoint_survives_exit_before_complete_returns(self):
        import hashlib
        from app.evaluation_stage import checkpoint_request
        from app.telemetry import record_usage
        provider=FixedProvider(json.dumps(drafts()))
        provider.request_summary=lambda system,user,**kw: {'request_sha256':hashlib.sha256((system+user).encode()).hexdigest()}
        calls=[]
        crashed=False
        def respond(system,user,**kwargs):
            nonlocal crashed
            def action():
                calls.append(True);record_usage({'provider':'Stub','status':'ok'})
                return json.dumps(drafts())
            content=checkpoint_request('Stub','fixture','agent',{'system':system,'user':user},action)
            if not crashed:
                crashed=True;raise KeyboardInterrupt('worker exited after durable RPC response')
            return content
        provider.complete=respond
        with self.assertRaises(KeyboardInterrupt):OptimizationAgent(self.store,provider).generate('EVAL-test')
        experiment=self.store.latest_experiment()
        with self.store.connection() as connection:
            connection.execute("UPDATE experiments SET status='failed' WHERE id=?",(experiment['id'],))
        result=OptimizationAgent(self.store,provider).generate('EVAL-test',experiment_id=experiment['id'])
        self.assertEqual(len(calls),1)
        self.assertEqual(len(result['candidates']),3)


if __name__ == "__main__":
    unittest.main()
