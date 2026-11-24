"""E2 rank observations and offline integration for decision contract v2."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from app.agent_inputs import MISSING
from app.governance import GovernanceStore
from app.optimization import OptimizationAgent
from identity_fixture import completed_baseline
from test_optimization_contract import drafts, trace_case


def target(qid, positions, subtype='', **diagnosis):
    return {
        'question_id': qid, 'id': 'BC-' + qid, 'result': {'passed': False},
        'diagnostic_view': {'display_question_id': qid, 'subfeature': subtype, **diagnosis},
        'retrieval_facts': {'standard_evidence_positions': [
            dict(zip(('candidates', 'reranked', 'final'), p)) for p in positions]},
    }


@pytest.mark.parametrize('qid,positions,subtype,change,stage', [
    ('Q17', [(5, 2, 2), (1, 1, 1), (6, 10, '未进入')], '', {'prompt_strategy': 'Grounded'}, '排序靠后'),
    ('Q15', [(7, 2, 1), (5, 5, 1), (3, 6, 1)], '表格读取或归类错误', {'min_score': 0.2}, '进了 Final 但生成出错'),
])
def test_e2_r3_b_and_c_conflict_with_facts_even_if_agent_says_otherwise(qid, positions, subtype, change, stage):
    from app.agent_mechanism import validate_mechanism

    proposal = {'config_diff': change, 'cross_layer_mechanisms': {qid: '交付内容会变化'}}
    row = validate_mechanism(proposal, [target(qid, positions, subtype)], 'R2-B', {}, [])[0]
    assert row['decision'] == '拒绝'
    assert row['fault']['stage'] == stage
    assert row['reason']
    assert row['base_id'] == 'R2-B'


def test_e2_r2_b_decomposition_works_for_ranking_and_recall_on_baseline():
    from app.agent_mechanism import validate_mechanism

    proposal = {'config_diff': {'query_decompose': True}}
    targets = [target('Q21', [('1（原文在同一父块内，按原文判定）',
                              '5（原文在同一父块内，按原文判定）', '未进入')]),
               target('Q27', [('未进入', '未进入', '未进入')])]
    preview = {'configs': [{'change': {'query_decompose': True}, 'evidence_enters_final': ['Q21', 'Q27']}]}
    rows = validate_mechanism(proposal, targets, 'Baseline', preview, [])
    assert [(r['fault']['stage'], r['decision']) for r in rows] == [('排序靠后', '放行'), ('未召回', '放行')]
    assert all(r['decision'] == '拒绝' for r in validate_mechanism(proposal, targets, 'R2-B', preview, []))


def test_cross_layer_requires_agent_mechanism_and_matching_preview():
    from app.agent_mechanism import validate_mechanism

    change = {'top_k': 6}
    proposal = {'config_diff': change, 'cross_layer_mechanisms': {'Q15': '增补对照周期，解决归类混淆'}}
    targets = [target('Q15', [(7, 2, 1)], '表格读取或归类错误')]
    preview = {'configs': [{'change': change, 'context_changed_question_ids': ['Q15']}]}
    decide = lambda draft, data: validate_mechanism(draft, targets, 'Baseline', data, [])[0]
    row = decide(proposal, preview)
    assert row['decision'] == '补证'
    assert row['fault']['subtype'] == '表格归类'
    assert '对照周期' in row['mechanism']
    assert decide({'config_diff': change}, preview)['decision'] == '拒绝'
    assert decide(proposal, {'configs': [{'change': change}]})['decision'] == '拒绝'
    preview['configs'][0]['evidence_lost_from_final'] = ['Q15']
    assert decide(proposal, preview)['decision'] == '拒绝'


def test_missing_final_trace_is_unknown_and_safety_uses_saved_diagnosis():
    from app.agent_mechanism import fault_stage

    assert fault_stage(target('Q01', [(1, 1, MISSING)]))['stage'] == '未知'
    assert fault_stage(target('Q43', [], primary_root_cause='Safety'))['stage'] == '安全相关'


def test_effect_ledger_distinguishes_base_outcome_rank_changes_and_combinations():
    from app.agent_mechanism import effect_entries

    def case(passed, chunk):
        entry = {'chunk_id': chunk}
        return {'passed': passed, 'programmatic_metrics': {'retrieval_trace': {
            'candidates': [entry], 'reranked': [entry], 'final': [entry]}}}

    questions = {q: {'id': q, 'evidence': [{'chunk_id': 'standard'}]} for q in ('Q1', 'Q2', 'Q3', 'Q4', 'Q5')}
    before = {'Q1': case(False, 'other'), 'Q2': case(True, 'standard'), 'Q3': case(False, 'other'),
              'Q4': case(False, 'other'), 'Q5': case(True, 'standard')}
    after = {'Q1': case(True, 'standard'), 'Q2': case(False, 'other'), 'Q3': case(False, 'other'),
             'Q5': case(True, 'standard')}
    source = {'experiment_id': 'E3', 'candidate_id': 'R3-C', 'round': 3, 'base_id': 'R2-B',
              'base_run_id': 'EVAL-B', 'candidate_run_id': 'EVAL-C'}
    rows = effect_entries({'query_decompose': True}, source, questions, {'Q1', 'Q3', 'Q4'}, before, after)
    assert {r['question_id']:r['status'] for r in rows} == {'Q1':'修好', 'Q2':'弄坏', 'Q3':'无效', 'Q4':'未知'}
    assert all(r['base_id'] == 'R2-B' and r['confidence'] == '单参数对照，未复验' for r in rows)
    assert rows[0]['evidence'][0]['before'] == dict.fromkeys(('candidates', 'reranked', 'final'), '未进入')
    assert rows[0]['evidence'][0]['after'] == dict.fromkeys(('candidates', 'reranked', 'final'), 1)
    assert rows[0]['final_added'] is True and rows[1]['final_lost'] is True
    assert rows[3]['final_lost'] is None
    combined = effect_entries({'query_decompose': True, 'top_k': 6}, source, questions, {'Q1'}, before, after, historical=True)
    assert combined[0]['changes'] == {'query_decompose': True, 'top_k': 6}
    assert combined[0]['parameter'] is None and combined[0]['confidence'] == '组合观察，不可归因'
    assert combined[0]['source'] == '历史观察（改造前实验）'


def test_ledger_is_saved_when_sandbox_finishes_and_sent_before_next_proposal(monkeypatch):
    with TemporaryDirectory() as directory:
        store = GovernanceStore(Path(directory) / 'test.db')
        completed_baseline(store, run_id='EVAL-113b')
        baseline = store.evaluation_run('EVAL-113b')
        with store.connection() as db:
            db.execute("UPDATE evaluation_runs SET config_json=json_set(config_json,'$.knowledge_identity',json(?)) WHERE id=?",
                       (json.dumps(json.loads(baseline['dataset_snapshot_json'])['corpus_fingerprint']), baseline['id']))
        case = trace_case()
        with store.connection() as db:
            db.execute("UPDATE evaluation_case_results SET result_json=? WHERE run_id=? AND question_id='Q1'",
                       (json.dumps({**case, 'question_id': 'Q1'}), baseline['id']))
        store.record_bad_case(baseline['id'], 'Q1', 'Retrieval', 'ordinary', case)
        legacy = store.create_experiment(baseline['id'])
        identity = baseline['judge']['evaluation_identity']
        store.save_candidate(legacy, 'R1-B', {**baseline['config'], 'query_decompose': True}, {'candidate_label': 'B'})
        winner = f'{legacy}-R1-B'
        source_config = {**baseline['config'], 'query_decompose': True}
        store.finish_candidate(winner, 'evaluated', {'evaluation_run_id': 'EVAL-winner', 'evaluation_identity': identity})
        store.record_evaluation_case('EVAL-winner', 'Q1', case)
        store.save_candidate(legacy, 'R2-C', {**source_config, 'min_score': 0.2},
                             {'inherited_from': winner, 'inherited_parameters': {'query_decompose': True}, 'round': 2})
        store.finish_candidate(f'{legacy}-R2-C', 'evaluated', {'evaluation_run_id': 'EVAL-history', 'evaluation_identity': identity})
        store.record_evaluation_case('EVAL-history', 'Q1', {**case, 'passed': True})
        with store.connection() as db:
            # Older candidates omit fixed temperature while formal Baseline includes it.
            db.execute("UPDATE evaluation_runs SET config_json=json_set(config_json,'$.temperature',0) WHERE id=?", (baseline['id'],))
        from app.agent_mechanism import candidate_effects
        with store.connection() as db:
            source = db.execute('SELECT * FROM experiments WHERE id=?', (legacy,)).fetchone()
            source_candidate = db.execute('SELECT * FROM candidate_configs WHERE id=?', (f'{legacy}-R2-C',)).fetchone()
            history = candidate_effects(db, source, source_candidate, json.loads(source_candidate['result_json']), historical=True)
        assert not store.experiment(legacy)['result'].get('parameter_effect_ledger')
        experiment = store.create_experiment(baseline['id'], decision_contract_v2=True)
        assert store.experiment(experiment)['result']['parameter_effect_ledger']['historical'] == []
        inherited = next(row for row in history if row['candidate_id'].endswith('-R2-C'))
        assert inherited['changes'] == {'min_score': 0.2}
        assert inherited['base_id'] == winner and inherited['status'] == '修好'
        cid = f'{experiment}-R1-A'
        store.save_candidate(experiment, 'R1-A', {**baseline['config'], 'query_decompose': True},
                             {'round': 1, 'candidate_label': 'A', 'root_cause_evidence': ['Q1']})
        result = {'evaluation_run_id': 'EVAL-partial', 'evaluation_identity': identity, 'evaluation_complete': False}
        store.finish_candidate(cid, 'failed', result)
        store.finish_candidate(cid, 'failed', result)
        rows = store.experiment(experiment)['result']['parameter_effect_ledger']['current']
        assert [(r['candidate_id'], r['status']) for r in rows] == [(cid, '未知')]

        def proposal(system, user, **_):
            payload = json.loads(user)
            assert payload['parameter_effect_ledger']['current'] == rows
            assert payload['fault_stages']['Baseline']['Q1']['stage']
            assert payload['parameter_stages']['query_decompose'] == ['recall', 'ranking']
            raise RuntimeError('offline fixture reached proposal')

        with store.connection() as db:
            db.execute("UPDATE candidate_configs SET status='evaluated' WHERE id=?", (cid,))
            saved = {'1': {'status': 'saved', 'review': {'lessons': ['保存事实']}, 'case_facts': {}, 'parameter_findings': []}}
            db.execute("UPDATE experiments SET result_json=json_set(result_json,'$.round_conclusions',json(?)) WHERE id=?",
                       (json.dumps(saved), experiment))
        from app.agent_inputs import baseline_bad_case_rows
        [target_row] = baseline_bad_case_rows(store, store.evaluation_run(baseline['id']))
        display = target_row['diagnostic_view']['display_question_id'] or 'Q1'
        monkeypatch.setattr('app.optimization.load_retrieval_preview', lambda *_: {
            'configs': [{'change': {'top_k': 6}, 'evidence_enters_final': [display]}]})
        monkeypatch.setattr('app.optimization.wait_for_off_peak', Mock())
        provider = Mock(spec=['complete'])
        provider.complete.side_effect = proposal
        with pytest.raises(ValueError, match='offline fixture reached proposal'):
            OptimizationAgent(store, provider).generate(baseline['id'], experiment_id=experiment)
        provider.complete.assert_called_once()


def test_continue_api_saves_per_target_checks_and_rejected_draft(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.agent_inputs import baseline_bad_case_rows

    with TemporaryDirectory() as directory:
        store = GovernanceStore(Path(directory) / 'test.db')
        baseline_id = completed_baseline(store, run_id='EVAL-113b-api')
        baseline = store.evaluation_run(baseline_id)
        with store.connection() as db:
            db.execute("UPDATE evaluation_runs SET config_json=json_set(config_json,'$.knowledge_identity',json(?)) WHERE id=?",
                       (json.dumps(json.loads(baseline['dataset_snapshot_json'])['corpus_fingerprint']), baseline_id))
        store.record_bad_case(baseline_id, 'Q1', 'Retrieval', 'ordinary', trace_case())
        experiment = store.create_experiment(baseline_id, decision_contract_v2=True)
        [target] = baseline_bad_case_rows(store, baseline)
        display = target['diagnostic_view']['display_question_id']
        alternative = {'query_decompose': True}
        rejected = drafts()['candidates'][0]['config_diff']
        variants = [alternative, *[c['config_diff'] for c in drafts()['candidates'][1:]]]
        preview = {'configs': [{'change': change, 'evidence_enters_final': [display]} for change in variants]}
        monkeypatch.setattr('app.optimization.load_retrieval_preview', lambda *_: preview)
        monkeypatch.setattr('app.optimization.wait_for_off_peak', Mock())
        provider = Mock(spec=['complete'])

        def respond(_system, user, **_kwargs):
            prompt = json.loads(user)
            output = drafts()
            output['prior_round_review']['summary'] = '无'
            output['hypothesis_plan'] = {'hypothesis': '交付标准证据可以改善回答', 'test_candidate': 'A',
                                         'if_true': {'action': 'D'}, 'if_false': {'action': 'stop'}}
            output['bad_case_summary'] = {'groups': prompt['bad_case_groups'], 'focus': '核对已保存证据',
                                          'conclusions': [{'id': 'B1', 'conclusion': '证据缺口'}]}
            output['candidates'][0]['config_diff'] = alternative if 'validation_rejection' in prompt else rejected
            for candidate in output['candidates']:
                candidate.update(bad_case_conclusion_ids=['B1'], predicted_fixed_question_ids=['Q1'],
                    adjustments=[{'parameter': k, 'candidate_value': v, 'expected_impact': '预期修好Q1'}
                                 for k, v in candidate['config_diff'].items()],
                    risks=[{'question_ids': [], 'metric': '时延', 'reason': '需观察'}])
            return json.dumps(output)

        provider.complete.side_effect = respond
        monkeypatch.setattr(main, 'store', store)
        monkeypatch.setattr(main.ai_service, 'provider', provider)
        client = TestClient(main.app)
        result = client.post(f'/api/experiments/{experiment}/continue')
        assert result.status_code == 200, result.json()
        read_back = client.get(f'/api/experiments/{experiment}?light=true').json()
        assert len(read_back['candidates']) == 3
        assert read_back['evaluation_budget']['used'] == 0
        plan = read_back['result']['hypothesis_chain']['1']
        assert plan['candidate_id'].endswith('-R1-A') and plan['question_ids'] == ['Q1']
        assert all(c['reasoning']['mechanism_checks'][0]['decision'] == '放行' for c in read_back['candidates'])
        trace = client.get(f'/api/experiments/{experiment}/round-trace/1').json()
        assert trace['result']['validation_retries'][0]['mechanism_checks']['A'][0]['decision'] == '拒绝'
        assert provider.complete.call_count == 2
