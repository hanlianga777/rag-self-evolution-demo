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
    return retrieval_case()[0] if root=='Retrieval' else generation_case(root)


def drafts():
    result = {"root_cause_cluster": "coverage", "observed_evidence": ["Q1"], "candidates": [
        {"id": "A", "hypothesis": "depth", "why": "more evidence", "target_bad_cases": ["Q1"], "config_diff": {"top_k": 6}, "risk": "latency"},
        {"id": "B", "hypothesis": "noise", "why": "filter", "target_bad_cases": ["Q1"], "config_diff": {"min_score": 0.1}, "risk": "recall"},
        {"id": "C", "hypothesis": "coverage", "why": "more candidates", "target_bad_cases": ["Q1"], "config_diff": {"candidate_k": 24}, "risk": "latency"},
    ]}
    for candidate in result['candidates']:
        candidate.update(intervention_direction='candidate_recall' if candidate['id']=='C' else 'context_selection', evidence_assertions=[{'target_id':'Q1','observation':'recall_missing' if candidate['id']=='C' else 'ranking_omission'}], parameter_dependencies=[], target_group='fixture检索组', root_cause='Retrieval', root_cause_evidence=candidate['target_bad_cases'], expected_improvement='fixture预期覆盖')
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
        from diagnostic_fixture import retrieval_case
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
        self.assertNotIn("confidence",provider.prompt["bad_cases"][0]["diagnostic_view"])
        self.assertTrue(provider.prompt["target_reference_map"]["Q1"]["diagnostic_view"]["target_eligible"])
        self.assertNotIn("all_bad_case_audit",provider.prompt)
        self.assertIn("all_bad_case_audit",audit)
        self.assertIsNone(provider.prompt["failed_gates"])
        self.assertEqual(provider.prompt["baseline_gate_results"], {"passed": False})
        self.assertEqual(provider.prompt["allowed_parameter_values"], search_space_contract())
        self.assertEqual(set(provider.prompt["allowed_parameter_values"]), set(ALLOWED_SEARCH_SPACE))
        self.assertEqual(provider.prompt["excluded_automatic_parameters"], sorted(EXCLUDED_AUTOMATIC_PARAMETERS))
        self.assertEqual(provider.prompt["allowed_parameter_values"]["multi_query"], {"type": "boolean false or integer", "allowed": [False, 2, 4, 6]})

    def test_targets_require_current_persisted_ids_and_audit_unknown_references(self):
        for target in ('invented-case-id', 'Baseline 有一题失败', 'Q-other-run'):
            result = drafts()
            result['candidates'][1]['target_bad_cases'] = [target]
            experiment, trace, audit, _, _ = self.run_drafts(result)
            self.assertEqual(trace['status'], 'completed')
            self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']], ['A','C'])
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
        self.assertEqual(provider.prompt['baseline_id'], 'EVAL-test')
        self.assertEqual(provider.prompt['experiment_id'], generated['id'])
        self.assertEqual(provider.prompt['baseline_gate_results'], gates)
        self.assertEqual(provider.prompt['failed_gates'], [gates['gates'][0]])
        self.assertEqual(provider.prompt['evaluation_budget'], {'used': 0, 'max': 12, 'reserved_for_d': 1})
        self.assertEqual(provider.prompt['target_reference_map']['Q1']['bad_case_id'], 'BC-EVAL-test-Q1')
        for candidate in generated['candidates']:
            self.store.finish_candidate(candidate['id'], 'failed', {})
        retry = FixedProvider('{bad')
        with self.assertRaises(ValueError):
            OptimizationAgent(self.store, retry).generate('EVAL-test', experiment_id=generated['id'])
        self.assertEqual(retry.prompt['evaluation_budget'], {'used': 3, 'max': 12, 'reserved_for_d': 1})
        self.assertEqual(retry.prompt['failed_gates'], [gates['gates'][0]])

    def test_bad_candidate_k_rejects_only_bad_candidate_and_preserves_full_raw_trace(self):
        result=drafts();result['candidates'][1]['config_diff']['candidate_k']='32'
        experiment,trace,audit,_,raw=self.run_drafts(result)
        self.assertEqual(trace['status'],'completed')
        self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']],['A','C'])
        self.assertEqual(audit['provider_raw_text'],raw)
        self.assertEqual(audit['parsed_json'],result)
        rejected=audit['rejected_candidates'][0]
        self.assertEqual(rejected['stage'],'search_space');self.assertEqual(rejected['id'],'B')
        self.assertEqual(rejected['field'],'candidate_k');self.assertEqual(rejected['actual_value'],'32')
        self.assertEqual(rejected['expected_type'],'integer');self.assertEqual(rejected['allowed_values'],[12,24])
        self.assertIn('invalid candidate_k',rejected['reason'])

    def test_insufficient_evidence_can_persist_zero_or_fewer_candidates(self):
        for count in (0,1,2):
            response=drafts()
            response['candidates']=response['candidates'][:count]
            response['insufficient_evidence']='Only these hypotheses have actual trace support'
            experiment,trace,audit,_,_=self.run_drafts(response)
            self.assertEqual(trace['status'],'completed')
            self.assertEqual(len(experiment['candidates']),count)
            self.assertEqual(experiment['result']['generation_status'],'completed' if count else 'no_candidates')
            self.assertEqual(audit['generated_candidate_count'],count)
            self.assertEqual(audit['insufficient_evidence'],response['insufficient_evidence'])

    def test_no_confirmed_target_persists_insufficient_without_provider(self):
        self.store.record_bad_case('EVAL-test','Q1','Unknown','ordinary',{'primary_root_cause':'Unknown','diagnosis':{'status':'disputed'}})
        provider=FixedProvider('must not be called')
        result=OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertIsNone(provider.prompt)
        self.assertEqual(result['candidates'],[])
        self.assertFalse(result['result']['provider_called'])
        self.assertEqual(result['result']['generation_status'],'insufficient_evidence')

    def test_intervention_failure_retains_valid_part_and_raw_audit_atomically(self):
        response=drafts();response['candidates'][1]['config_diff']['prompt_strategy']='Abstention'
        experiment,trace,audit,_,raw=self.run_drafts(response)
        self.assertEqual(trace['status'],'completed')
        self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']],['A','C'])
        self.assertEqual(audit['rejected_candidates'][0]['stage'],'intervention')
        self.assertEqual(audit['rejected_candidates'][0]['id'],'B')
        self.assertEqual(audit['provider_raw_text'],raw)

    def test_strict_types_and_discrete_values(self):
        for field, value, valid in (
            ("top_k", True, False), ("top_k", False, False), ("top_k", 4, True),
            ("candidate_k", True, False), ("multi_query", False, True),
            ("multi_query", 2, True), ("multi_query", 4, True), ("multi_query", 6, True),
            ("multi_query", True, False), ("multi_query", 0, False), ("multi_query", "4", False),
            ("min_score", False, False), ("hybrid_alpha", True, False),
            ("metadata_filter", "OFF", True), ("metadata_filter", False, False), ("metadata_filter", "INVALID", False),
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
        self.assertEqual(trace["status"], "completed")
        self.assertEqual(audit["rejected_candidates"][0]["field"], "hybrid_alpha")

    def test_cross_field_duplicate_and_excluded_checks(self):
        for diff, expected in (
            ({"candidate_k": 4, "top_k": 6}, "candidate_k must be greater than or equal to top_k"),
            ({"top_k": 6, "temperature": 0.8}, "excluded automatic parameters"),
            ({"top_k": 6, "new_parameter": 1}, "unsupported parameters"),
        ):
            with self.subTest(diff=diff):
                result = drafts()
                result["candidates"][0]["config_diff"] = diff
                experiment, trace, audit, _, _ = self.run_drafts(result)
                self.assertEqual(trace["status"], "completed")
                self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']],['B','C'])
                self.assertIn(expected, audit['rejected_candidates'][0]['reason'])
        result = drafts()
        result["candidates"][1]["config_diff"] = {"top_k": 6}
        experiment, trace, audit, _, _ = self.run_drafts(result)
        self.assertEqual(trace["status"], "completed")
        self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']],['A','C'])
        self.assertIn("duplicate candidate configuration", audit['rejected_candidates'][0]['reason'])

    def test_json_parse_failure_retains_raw_text(self):
        provider = FixedProvider("{broken")
        with self.assertRaises(ValueError):
            OptimizationAgent(self.store, provider).generate("EVAL-test")
        experiment = self.store.latest_experiment()
        self.assertEqual(experiment["result"]["provider_raw_text"], "{broken")
        self.assertIsNone(experiment["result"]["parsed_json"])
        self.assertEqual(experiment["result"]["validation_stage"], "json_parse")

    def test_prompt_and_root_cause_rejection_expose_persisted_mapping(self):
        result=drafts();result['candidates'][1]['root_cause']='Generation'
        experiment,trace,audit,provider,raw=self.run_drafts(result)
        self.assertEqual(trace['status'],'completed')
        self.assertEqual(audit['rejected_candidates'][0]['id'],'B')
        self.assertEqual(audit['rejected_candidates'][0]['field'],'root_cause')
        self.assertEqual(audit['rejected_candidates'][0]['allowed_values'],['Retrieval'])
        self.assertEqual([c['reasoning']['candidate_label'] for c in experiment['candidates']],['A','C'])
        self.assertEqual(provider.prompt['target_reference_map']['Q1']['primary_root_cause'],'Retrieval')
        self.assertIn('参数干预环节',provider.prompt['rule'])

    def test_saved_round2_response_reproduces_b_and_accepts_truthful_cause_with_same_intervention(self):
        import shutil
        backup=Path(__file__).resolve().parents[2]/'output/playwright/agent-round2-audit/protected.db'
        if not backup.exists():self.skipTest('Private audit copy not tracked')
        copied=Path(self.directory.name)/'round2-copy.db';shutil.copy2(backup,copied)
        store=GovernanceStore(copied)
        with store.connection() as c:
            row=c.execute('SELECT result_json FROM agent_traces WHERE id=8').fetchone()
        saved=json.loads(row[0]);raw=saved['provider_raw_text']
        baseline=saved['baseline_id'];exp=saved['optimization_run_id']
        # This private replay is frozen to the archived baseline Corpus, not live Knowledge.
        from unittest.mock import patch
        old_identity=json.loads(store.evaluation_run(baseline)['dataset_snapshot_json'])['corpus_fingerprint']
        historical=patch('app.governance.current_manifest',return_value={'knowledge_identity':old_identity,'sources':old_identity['sources']})
        historical.start();self.addCleanup(historical.stop)
        before=store.candidates(exp)
        provider=FixedProvider(raw)
        from app.evaluation_contract import policy_current
        if not policy_current(store.evaluation_run(baseline)['judge']):
            with self.assertRaisesRegex(ValueError,'评测规则已升级'):
                OptimizationAgent(store,provider).generate(baseline,experiment_id=exp)
            self.assertEqual(store.candidates(exp),before)
            return
        with self.assertRaisesRegex(ValueError,'候选根因与可信目标不对应'):
            OptimizationAgent(store,provider).generate(baseline,experiment_id=exp)
        self.assertEqual(store.candidates(exp),before)
        self.assertEqual(store.experiment(exp)['evaluation_budget']['used'],5)
        for target in saved['parsed_candidates'][1]['target_bad_cases']:
            ref=provider.prompt['target_reference_map'][target]
            self.assertEqual(ref['primary_root_cause'],'Generation')
            self.assertNotIn('diagnosis_status',ref)
            self.assertEqual(ref['analysis_category'],'rag_failure')
            self.assertTrue(ref['root_cause_evidence'])
        self.assertTrue(all('checkpoints' not in item['result'] for item in provider.prompt['prior_sandbox_results']))
        corrected=json.loads(raw);corrected['candidates'][1]['root_cause']='Generation'
        # Offline counterfactual only: raw history and stored roots remain unchanged.
        result=OptimizationAgent(store,FixedProvider(json.dumps(corrected))).generate(baseline,experiment_id=exp)
        self.assertEqual(len(result['candidates']),6)
        new_b=next(c for c in result['candidates'] if c['reasoning'].get('round')==2 and c['reasoning']['candidate_label']=='B')
        self.assertEqual(new_b['reasoning']['root_cause'],'Generation')
        self.assertEqual(new_b['reasoning']['changed_parameters'],corrected['candidates'][1]['config_diff'])
        self.assertEqual([c for c in store.candidates(exp) if c['reasoning'].get('round')==1],before)

    def test_generation_target_requires_retrieval_evidence_before_cross_stage_hypothesis(self):
        self.store.record_bad_case('EVAL-test','Q1','Generation','ordinary',trace_case('Generation'))
        self.store.record_bad_case('EVAL-test','Q-unknown','Unknown','ordinary',{'primary_root_cause':'Unknown','diagnosis':{'status':'needs_review','reason':'fixture uncertainty'}})
        response=drafts()
        for candidate in response['candidates']:candidate['root_cause']='Generation'
        provider=FixedProvider(json.dumps(response))
        with self.assertRaisesRegex(ValueError,'Trace'):
            OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual(provider.prompt['target_reference_map']['Q1']['primary_root_cause'],'Generation')
        self.assertNotIn('Q-unknown',provider.prompt['target_reference_map'])
        self.assertFalse(self.store.candidates())

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
        self.assertNotIn('Q-risk',provider.prompt['target_reference_map'])
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
        self.assertEqual(self.store.experiment(experiment)['status'], 'failed')

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


if __name__ == "__main__":
    unittest.main()
