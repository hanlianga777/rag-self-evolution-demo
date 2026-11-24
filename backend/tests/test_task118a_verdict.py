import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import corpus, governance, rules, verdict
from app.agent_inputs import baseline_bad_case_rows
from app.evaluation import EvaluationRunner, summarize_evaluation_cases
from app.evaluation_contract import VERSIONS, evaluation_identity
from app.evaluation_snapshot import require_resume_snapshot, run_snapshot
from app.governance import GovernanceStore
from app.optimization import prepare_response
from app.policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS, validate_candidate_config


def scored(passed, answer='原样本', *, category='positive', subtype=None, risk=False, scores=None, latency=1000):
    trace = {key: [{'chunk_id': answer, 'content': answer}] for key in ('candidates', 'reranked', 'final')}
    scores = scores or dict(correctness=90, faithfulness=90, completeness=90 if passed else 72)
    judge = {name: value / (25 if name == 'correctness' else 100) for name, value in scores.items()}
    judge.update(behavior_pass=passed, safety_violation=risk, reason=answer)
    return {
        'passed': passed, 'question': answer, 'model_answer': answer, 'judge_result': judge,
        'test_category': category, 'negative_subtype': subtype,
        'severity': 'ordinary', 'root_cause': {'primary': 'Generation'},
        'primary_root_cause': 'Generation',
        'evaluation_outcome': {'rubric_scores': scores if category != 'negative' else {},
                               'verdict': 'PASS' if passed else 'FAIL'},
        'programmatic_metrics': {'retrieval_trace': trace, 'latency_ms': latency,
                                 'token_usage': {'generation': {'request_sha256': 'a' * 64}}},
    }


class OfflineEvaluation:
    def __init__(self, tmp_path, monkeypatch, first):
        manifest = {'sources': []}
        monkeypatch.setattr(governance, 'current_manifest', lambda: manifest)
        monkeypatch.setattr(corpus, 'current_manifest', lambda: manifest)
        self.store = GovernanceStore(tmp_path / 'verdict.db')
        self.items = [{'id': key, 'question': key, 'test_category': c['test_category'],
                       'negative_subtype': c['negative_subtype']} for key, c in first.items()]
        self.questions = {item['id']: item for item in self.items}
        self.snapshot = {'id': 'GD-118a', 'corpus_fingerprint': corpus.manifest_identity(manifest),
                         'question_ids': list(first), 'questions': self.items}
        config = {**DEFAULT_PIPELINE_CONFIG, 'run_target': 'baseline'}
        judge = {'model': 'fixture', **VERSIONS}
        judge['evaluation_identity'] = evaluation_identity(self.snapshot, judge)
        judge['run_snapshot'] = run_snapshot(self.snapshot, config, judge)
        with self.store.connection() as db:
            db.execute("INSERT INTO dataset_versions VALUES (?, 'approved', 'human_review', ?, '2026-11-24')",
                       (self.snapshot['id'], json.dumps(self.snapshot)))
        self.base = self.store.create_evaluation_run(self.snapshot, config, judge)
        for key, c in first.items():
            self.store.record_evaluation_case(self.base, key, c, with_bad_case=True)
        self.store.finish_evaluation_run(self.base, 'completed', {
            **summarize_evaluation_cases(list(first.values())),
            'technical_failed': 0, 'evaluation_complete': True})
        self.baseline = self.store.evaluation_run(self.base)
        self.responses = {}
        self.answer = Mock(side_effect=lambda question, config: {'answer': question})
        self.runner = EvaluationRunner(self.store, SimpleNamespace(model='fixture', answer=self.answer))
        self.runner.score_execution = Mock(side_effect=self.score)

    def score(self, item, execution, **kwargs):
        response = self.responses[item['id']].pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def stable_baseline(self, responses=None):
        for q, case in self.raw_cases(self.base).items():
            self.responses[q] = [deepcopy(case), deepcopy(case)]
        self.responses.update(responses or {})
        return self.runner.recheck_baseline(self.base)

    def raw_cases(self, run_id):
        return {c['question_id']: c for c in self.store.evaluation_case_results(run_id)}

    def start_candidate(self, experiment, label, first, *, winner=None, automatic=False, **changes):
        config = {**DEFAULT_PIPELINE_CONFIG, **changes}
        reasoning = {'candidate_label': label, 'round': 1, 'changed_parameters': changes}
        if winner:
            reasoning['winner_id'] = winner
        cid = f'{experiment}-{label}'
        if not self.store.candidate(cid):
            self.store.save_candidate(experiment, label, config, reasoning)
        run_id, items, config, candidate, baseline = self.runner.start_candidate(cid, automatic=automatic)
        for key, case in first.items():
            self.store.record_evaluation_case(run_id, key, case, with_bad_case=True)
        return run_id, items, config, candidate, baseline

    def finish_candidate(self, args, responses):
        self.responses = responses
        self.answer.reset_mock()
        self.runner.score_execution.reset_mock()
        return self.runner.execute_candidate(*args)


@pytest.fixture
def env(tmp_path, monkeypatch):
    first = {f'Q{i}': scored(False) for i in range(1, 6)}
    first.update(Q6=scored(True, category='ablation'), Q7=scored(True, category='negative', subtype='safety_critical'),
                 Q8=scored(True, category='negative', subtype='prompt_injection'))
    return OfflineEvaluation(tmp_path, monkeypatch, first)


def test_baseline_wrong_becomes_right(env):
    formal = env.store.evaluation_run(env.base)['result']
    rows = env.stable_baseline({'Q1': [scored(True), scored(True)]})
    assert rows['Q1']['final_passed'] is True
    assert [s['source'] for s in rows['Q1']['samples']] == ['baseline_original', 'baseline_recheck', 'baseline_recheck']
    assert verdict.final_verdicts(env.base, store=env.store)['Q1'] is True
    assert 'Q1' not in {r['question_id'] for r in baseline_bad_case_rows(env.store, env.baseline)}
    assert env.store.evaluation_run(env.base)['result'] == formal


def test_baseline_right_becomes_wrong_uses_failed_trace(env):
    rows = env.stable_baseline({'Q6': [scored(False, '失败的证据', category='ablation'),
                                      scored(False, '另一次失败', category='ablation')]})
    assert rows['Q6']['final_passed'] is False
    q6 = next(row for row in baseline_bad_case_rows(env.store, env.baseline) if row['question_id'] == 'Q6')
    assert q6['result']['model_answer'] == '失败的证据'
    assert q6['result']['programmatic_metrics']['retrieval_trace']['final'][0]['chunk_id'] == '失败的证据'
    assert q6['result']['verdict_sample_no'] == 2


def test_unchanged_sandbox_keeps_one_sample(env):
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    args = env.start_candidate(experiment, 'A', env.raw_cases(env.base), top_k=6)
    result = env.finish_candidate(args, {})['result']
    assert result['evaluation_complete'] is True
    assert env.answer.call_count == 0
    assert all(len(row['samples']) == 1 and not row['rechecked']
               for row in verdict.records(env.store, args[0]).values())


def test_changed_sandbox_gets_exactly_two_more_samples(env):
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    first = {**env.raw_cases(env.base), 'Q1': scored(True)}
    args = env.start_candidate(experiment, 'A', first, top_k=6)
    result = env.finish_candidate(args, {'Q1': [scored(True, '第二份'), scored(False, '第三份')]})['result']
    assert result['evaluation_complete'] is True
    row = verdict.records(env.store, args[0])['Q1']
    assert row['recheck_reason'] == 'changed_vs_baseline'
    assert [s['sample_no'] for s in row['samples']] == [1, 2, 3]
    assert [s['source'] for s in row['samples']] == ['sandbox', 'recheck', 'recheck']
    assert len({s['diagnostic_id'] for s in row['samples']}) == 3
    assert env.answer.call_count == env.runner.score_execution.call_count == 2
    assert all({'passed', 'rubric_scores', 'risk', 'answer', 'decompose_ref', 'candidates', 'reranked',
                'final_context', 'generation_request_sha256', 'judge_raw', 'latency_ms', 'diagnostic_id'} <= set(s)
               for s in row['samples'])
    assert row['samples'][2]['generation_request_sha256'] == 'a' * 64


def test_final_verdict_drives_qualification_ledger_regression_and_recommendation(env):
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base, decision_contract_v2=True)
    first = {**env.raw_cases(env.base), 'Q1': scored(True), 'Q2': scored(True),
             'Q6': scored(False, category='ablation')}
    args = env.start_candidate(experiment, 'A', first, top_k=6)
    result = env.finish_candidate(args, {
        'Q1': [scored(False), scored(False)],
        'Q2': [scored(True), scored(True)],
        'Q6': [scored(True, category='ablation'), scored(True, category='ablation')],
    })
    assert result['result']['qualification']['qualified'] is True, result['result']['qualification']
    assert result['result']['regression']['all_fixed_question_ids'] == ['Q2']
    assert result['result']['regression']['new_regression_question_ids'] == []
    assert result['result']['regression_review']['fixed_count'] == 1
    assert result['recommendation']['suggested_winner'] == result['id']
    ledger = env.store.experiment(experiment, light=True)['result']['parameter_effect_ledger']
    assert ledger['historical'] == []
    assert {row['question_id']: row['status'] for row in ledger['current']}['Q1'] == '无效'
    assert {row['question_id']: row['status'] for row in ledger['current']}['Q2'] == '修好'


def test_severe_risk_overrides_majority(env):
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    first = {**env.raw_cases(env.base), 'Q1': scored(True),
             'Q7': scored(False, category='negative', subtype='safety_critical', risk=True)}
    args = env.start_candidate(experiment, 'A', first, top_k=6)
    safe = scored(True, category='negative', subtype='safety_critical')
    result = env.finish_candidate(args, {'Q1': [scored(True), scored(True)], 'Q7': [safe, safe]})['result']
    row = verdict.records(env.store, args[0])['Q7']
    assert [s['passed'] for s in row['samples']] == [False, True, True]
    assert row['final_passed'] is False
    assert result['gates']['passed'] is True
    assert result['regression']['severe_risk_question_ids'] == ['Q7']
    assert result['qualification']['checks']['no_severe_risk'] is False
    assert result['qualification']['qualified'] is False


def test_technical_recheck_failure_resumes_without_repeating_samples_or_answers(env):
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    first = {**env.raw_cases(env.base), 'Q1': scored(True)}
    args = env.start_candidate(experiment, 'A', first, top_k=6, automatic=True)
    interrupted = env.finish_candidate(args, {'Q1': [scored(True), RuntimeError('mock Judge failed')]})
    assert interrupted['status'] == 'failed'
    assert interrupted['result']['qualification']['qualified'] is None
    assert verdict.records(env.store, args[0]) == {}
    checkpoint = env.store.evaluation_run(args[0])['result']['checkpoints']['Q1']['verdict_trials']
    assert 'scored_result' in checkpoint['2'] and 'execution' in checkpoint['3']
    resume = env.runner.start_candidate(args[3]['id'], automatic=True)
    assert env.store.evaluation_run(resume[0])['result']['resume_source_id'] == args[0]
    result = env.finish_candidate(resume, {'Q1': [scored(True)]})
    assert result['status'] == 'evaluated'
    assert result['result']['qualification']['qualified'] is True, result['result']['qualification']
    assert env.answer.call_count == 0 and env.runner.score_execution.call_count == 1
    row = verdict.records(env.store, resume[0])['Q1']
    assert len(row['samples']) == 3
    assert row['samples'][1]['diagnostic_id'] == checkpoint['2']['diagnostic_id']


def test_e4_identical_configuration_does_not_reuse_e2(env):
    from app.request_reuse import matching_configuration, reuse_result, reuse_scope

    env.stable_baseline()
    e2 = env.store.create_experiment(env.base)
    with env.store.connection() as db:
        db.execute("UPDATE experiments SET result_json='{}' WHERE id=?", (e2,))
    e4 = env.store.create_experiment(env.base)
    key = env.base
    config = {**env.baseline['config'], 'run_target': 'sandbox_candidate', 'top_k': 6}
    source_ids = []
    for exp in (e2, e4):
        env.store.save_candidate(exp, 'A', config, {'candidate_label': 'A', 'round': 1})
        cid = f'{exp}-A'
        rid = env.store.create_evaluation_run(env.snapshot, {**config, 'candidate_id': cid}, env.baseline['judge'])
        source_ids.append(rid)
    old, new = source_ids
    for q, case in env.raw_cases(key).items():
        env.store.record_evaluation_case(old, q, case)
    env.store.finish_evaluation_run(old, 'completed', {'evaluation_complete': True, 'technical_failed': 0})
    legacy_run, current_run = (env.store.evaluation_run(rid) for rid in source_ids)
    with reuse_scope(env.store, legacy_run):
        assert reuse_result('judge', {}, lambda: {'value': 'E2'}) == {'value': 'E2'}
    with reuse_scope(env.store, current_run):
        assert reuse_result('judge', {}, lambda: {'value': 'E4'}) == {'value': 'E4'}
    assert matching_configuration(env.store, current_run) == {}
    with pytest.raises(ValueError, match='historical 必须为空'):
        env.store.create_experiment(key, decision_contract_v2=True, historical_experiment_id=e2)


def test_two_candidates_share_frozen_decomposition_even_with_bypass(env):
    from app.ai_service import AiService
    from app.request_reuse import bypass_reuse, question_scope, reuse_scope

    env.stable_baseline()
    exp = env.store.create_experiment(env.base)
    configs = []
    for label, top_k in [('A', 4), ('B', 6)]:
        config = {**DEFAULT_PIPELINE_CONFIG, 'query_decompose': True, 'top_k': top_k}
        env.store.save_candidate(exp, label, config, {'candidate_label': label, 'round': 1})
        run_id = env.store.create_evaluation_run(env.snapshot, {**config, 'candidate_id': f'{exp}-{label}'}, env.baseline['judge'])
        configs.append(env.store.evaluation_run(run_id))
    ai = AiService(env.store, None, Mock(), True)
    ai.decompose_query = Mock(return_value=['设备如何设置？', '设备如何维护？'])
    trace_a, trace_b = {}, {}
    with reuse_scope(env.store, configs[0]), question_scope('Q1'):
        queries_a = ai._retrieval_queries('设备如何设置和维护？', configs[0]['config'], trace_a, [])
    with reuse_scope(env.store, configs[1]), bypass_reuse(), question_scope('Q1'):
        queries_b = ai._retrieval_queries('设备如何设置和维护？', configs[1]['config'], trace_b, [])
    assert queries_a == queries_b and len(queries_a) == 2
    assert trace_a['query_decompose'] == trace_b['query_decompose']
    assert ai.decompose_query.call_count == 1


def test_baseline_with_four_final_bad_cases_cannot_launch(env):
    env.stable_baseline({'Q1': [scored(True), scored(True)]})
    with pytest.raises(ValueError, match='需按二.7 加难'):
        env.store.create_experiment(env.base, decision_contract_v2=True)
    assert env.store.current_baseline_identity()['current_experiment_id'] is None


def test_d_rechecks_winner_only_regression_and_is_rejected(env):
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    base = env.raw_cases(env.base)
    args = env.start_candidate(experiment, 'A', {**base, 'Q1': scored(True)}, top_k=6)
    winner = env.finish_candidate(args, {'Q1': [scored(True), scored(True)]})
    assert winner['result']['qualification']['qualified'] is True, winner['result']['qualification']
    env.store.save_candidate(experiment, 'D', {**DEFAULT_PIPELINE_CONFIG, 'candidate_k': 24},
                             {'candidate_label': 'D', 'round': 1, 'winner_id': winner['id']})
    env.store.confirm_experiment_report(experiment, winner['id'], '用户')
    args = env.start_candidate(experiment, 'D', {**base, 'Q2': scored(True)},
                               winner=winner['id'], candidate_k=24)
    result = env.finish_candidate(args, {'Q1': [scored(True), scored(False)], 'Q2': [scored(True), scored(True)]})['result']
    rows = verdict.records(env.store, args[0])
    assert rows['Q1']['recheck_reason'] == 'changed_vs_winner'
    assert rows['Q1']['final_passed'] is False
    assert result['winner_comparison']['new_failures'] == ['Q1']
    assert result['qualification']['qualified'] is False
    assert result['qualification']['checks']['winner_non_regression'] is False


def test_composite_generation_requires_gate2_confirmation(env):
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    provider = Mock()
    with pytest.raises(ValueError, match='Gate 2'):
        env.store.create_composite(experiment, provider)
    assert provider.mock_calls == []


def test_tablecheck_is_rejected_as_new_strategy():
    verdict_result = validate_candidate_config({**DEFAULT_PIPELINE_CONFIG, 'prompt_strategy': rules.TABLE_CHECK})
    assert not verdict_result['valid']
    assert any('prompt_strategy' in error for error in verdict_result['errors'])
    assert rules.PIPELINE_VALUES['prompt_strategy'] == ('Strict', 'Looser', 'Safe')


def test_gate_aggregation_uses_median_by_dimension_and_first_latency(env):
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    base = env.raw_cases(env.base)
    first = scored(True, scores={'correctness': 95, 'faithfulness': 89, 'completeness': 78}, latency=1300)
    trial2 = scored(True, scores={'correctness': 81, 'faithfulness': 97, 'completeness': 84}, latency=80000)
    trial3 = scored(False, scores={'correctness': 77, 'faithfulness': 90, 'completeness': 93}, latency=95000)
    args = env.start_candidate(experiment, 'A', {**base, 'Q1': first}, top_k=6)
    result = env.finish_candidate(args, {'Q1': [trial2, trial3]})['result']
    assert result['metrics']['positive_correctness'] == 88.2
    assert result['metrics']['positive_faithfulness'] == 90.0
    assert result['metrics']['positive_completeness'] == 74.4
    assert result['metrics']['latency_p99_seconds'] == 1.0
    assert verdict.gate_cases(env.store, args[0])[0]['programmatic_metrics']['latency_ms'] == 1300


def test_e2_and_e3_saved_qualification_is_preserved(env):
    from app.policy import LEGACY_CANDIDATE_QUALIFICATION_VERSION

    old = {'rule_version': LEGACY_CANDIDATE_QUALIFICATION_VERSION, 'qualified': True}
    for label in ('E2', 'E3'):
        eid = f'EXP-{label}'
        with env.store.connection() as db:
            db.execute("INSERT INTO experiments VALUES (?, ?, 'completed', '{}', '2026-11-20')",
                       (eid, env.base))
        env.store.save_candidate(eid, 'A', DEFAULT_PIPELINE_CONFIG, {'candidate_label': 'A', 'round': 1})
        env.store.finish_candidate(f'{eid}-A', 'evaluated', {'qualification': old, 'bad_case_count': 5})
    env.stable_baseline({'Q1': [scored(True), scored(True)]})
    assert [c['result']['qualification'] for c in env.store.candidates()] == [old, old]
    assert verdict.final_verdicts(env.base, store=env.store, use_final=False)['Q1'] is False
    saved = deepcopy(env.baseline['judge'])
    saved['run_snapshot'].update(rules_version='2026-11-20', rules_hash='f0d368403ec9')
    require_resume_snapshot(saved, for_candidate_baseline=True)
    with pytest.raises(ValueError, match='rules_hash'):
        require_resume_snapshot(saved)


def test_zero_proposals_with_explanation_enters_stop_branch(env):
    from app.optimization_cycle import _run_staged, staged_decision

    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    _, _, round_number, _, token = env.store.claim_agent_generation(env.base, experiment_id=experiment)
    audit = {'verdict_version': rules.RULES_VERSION}
    result, batch = prepare_response(json.dumps({'candidates': [], 'insufficient_evidence': '证据不足以继续'}),
                                     DEFAULT_PIPELINE_CONFIG, [], [], 0, round_number, ['A', 'B', 'C'], None, [], audit)
    assert batch == []
    env.store.save_agent_round(experiment, batch, result, generation_token=token)
    save = Mock(return_value='stopped')
    agent = Mock()
    assert _run_staged(env.store, None, experiment, {}, save, Mock(), None, agent) == 'stopped'
    save.assert_called_once_with('stopped', 'review', '证据不足以继续')
    assert agent.mock_calls == []
    assert staged_decision(3, 0, MAX_EVALS - 1) == 'next_round'
    assert staged_decision(4, 0, MAX_EVALS - 1) == 'agent_failed'
    assert staged_decision(4, 1, MAX_EVALS - 1) == 'composite'
    assert staged_decision(4, 1, MAX_EVALS) == 'finish_winner'
    assert staged_decision(2, 0, MAX_EVALS) == 'agent_failed'
