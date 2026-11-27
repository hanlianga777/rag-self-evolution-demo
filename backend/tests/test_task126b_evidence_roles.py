import json

import pytest

from api_fixture import main
from app.agent_inputs import baseline_bad_case_rows
from app.agent_mechanism import faults_for_cases
from app.governance import GovernanceStore


@pytest.fixture
def saved_case(tmp_path, monkeypatch):
    from app import evidence_roles

    store = GovernanceStore(tmp_path / '126b.sqlite')
    monkeypatch.setattr(main, 'store', store)
    primary = {'chunk_id': 'DOC-a-V2-C-00001', 'content': '型号 A 的上限为 +35°C'}
    alternate = {'chunk_id': 'DOC-b-V2-C-00002', 'content': '型号 A 最高 +35°C'}
    anchor = {'chunk_id': 'DOC-c-V2-C-00003', 'content': '型号 A 重 77 kg'}
    evidence = [primary, alternate, anchor]
    question = {'id': 'Q01', 'question': '型号 A 最高几度？', 'question_subtype': '精确事实',
                'reference_answer': '+35°C', 'test_category': 'positive',
                'evidence': [{'source_chunk_ids': [entry['chunk_id']], 'evidence_key_points': [entry['content']]}
                             for entry in evidence]}
    dataset_id = 'GD-126b-test'
    run_id = store.create_evaluation_run({'id': dataset_id, 'questions': [question]}, {'run_target': 'baseline'}, {})

    def save(candidates, final, *, equivalent=True, judge=None, **extra):
        roles = ('equivalent', 'equivalent', 'anchor') if equivalent else ('required', 'supporting', 'anchor')
        rows = [{'role': role, 'claim': '型号 A 的上限为 +35°C', 'claim_id': '1',
                 'equivalent_group': '1' if role == 'equivalent' else '',
                 'chunk_id': entry['chunk_id'], 'match_text': entry['content'],
                 'question_sha256': evidence_roles.question_fingerprint(question)} for role, entry in zip(roles, evidence)]
        monkeypatch.setattr(evidence_roles, 'annotations', lambda: {dataset_id: {'Q01': rows}})
        case = {'question_id': 'Q01', 'passed': False, 'test_category': 'positive', 'model_answer': '不知道。',
                'judge_result': {'verdict': 'FAIL', 'completeness_reason': '遗漏了最高温度。', **(judge or {})},
                'programmatic_metrics': {'retrieval_trace': {'status': 'completed', 'candidates': candidates,
                                                          'final': final}}, **extra}
        store.record_bad_case(run_id, 'Q01', 'Retrieval', 'critical', case)
        with store.connection() as connection:
            connection.execute('INSERT INTO evaluation_case_results(run_id,question_id,result_json) VALUES (?,?,?)',
                               (run_id, 'Q01', json.dumps(case, ensure_ascii=False)))
        return store.evaluation_run(run_id)

    return store, save, primary, alternate, anchor


def listed(run, version=None):
    return main.bad_cases(light=True, baseline_id=run['id'], diagnosis_version=version)[0]['result']['bad_case_fault']


def test_missing_anchor_does_not_cause_recall_failure(saved_case):
    _, save, primary, _, _ = saved_case
    run = save([primary], [], equivalent=False)
    fault = listed(run)
    assert (fault['diagnosis_version'], fault['code'], fault['subtype']) == ('126b', 'ranking', '找到但没交给模型')
    assert '+35°C' in fault['reason'] and '77 kg' not in fault['reason']


def test_one_equivalent_source_satisfies_the_fact(saved_case):
    _, save, _, alternate, _ = saved_case
    run = save([alternate], [{**alternate, 'matched_child_ids': [alternate['chunk_id']]}])
    fault = listed(run)
    assert fault['code'] == 'generation'
    assert fault['claim_coverage'][0]['final'] == 1


def test_all_final_evidence_with_saved_wrong_answer_is_generation(saved_case):
    _, save, primary, _, _ = saved_case
    run = save([primary], [primary], equivalent=False, judge={'over_refusal': True})
    fault = listed(run)
    assert (fault['layer'], fault['subtype'], fault['question_type']) == ('generation', '过度拒答', '精确事实')
    detail = main.bad_case(f"BC-{run['id']}-Q01")['result']['bad_case_fault']
    full = main.evaluation_run(run['id'])['cases'][0]['bad_case_fault']
    assert detail == full == fault


def test_legacy_version_and_saved_result_are_preserved(saved_case):
    store, save, primary, _, _ = saved_case
    run = save([primary], [], equivalent=False)
    before = store.bad_case_rows(run['id'])[0]['result_json']
    rows = baseline_bad_case_rows(store, run)
    old = faults_for_cases(run, [row['result'] for row in rows], rows, decision_version='122f')['Q01']
    assert listed(run)['code'] == 'ranking'
    assert listed(run, '122f') == {**old, 'layer': 'retrieval'}
    assert old['code'] == 'recall'
    assert store.bad_case_rows(run['id'])[0]['result_json'] == before


def test_partial_final_is_not_proof_of_delivery(saved_case):
    _, save, primary, _, _ = saved_case
    run = save([primary], [{**primary, 'content': '型号 A 的上限为 -35°C'}], equivalent=False)
    assert listed(run)['code'] == 'ranking'


def test_same_document_outside_frozen_source_scope_does_not_satisfy_the_fact(saved_case):
    _, save, primary, _, _ = saved_case
    other_section = {**primary, 'chunk_id': 'DOC-a-V2-C-00099'}
    run = save([other_section], [other_section], equivalent=False)
    assert listed(run)['code'] == 'recall'


def test_unknown_when_final_text_was_not_saved(saved_case):
    _, save, primary, _, _ = saved_case
    run = save([primary], [{'chunk_id': primary['chunk_id'], 'child_content': primary['content']}], equivalent=False)
    assert listed(run)['subtype'] == '待确认'


@pytest.mark.parametrize(('judge', 'question_fields', 'expected'), [
    ({'correctness_reason': '误读表格行，计数错误。'}, {'question_subtype': '表格统计'}, '表格理解错'),
    ({'behavior_reason': '未先澄清所需型号。'}, {'test_category': 'negative', 'negative_subtype': 'clarify'}, '该追问没追问'),
    ({'safety_violation': True}, {}, '安全越界'),
    ({'issues': [{'failure_kind': 'latency'}]}, {}, '慢'),
    ({'completeness_reason': '遗漏了最高温度。'}, {}, '漏要点'),
    ({'reason': '判错，未保存具体原因。'}, {}, '待确认'),
])
def test_saved_judge_and_question_type_explain_the_subtype(judge, question_fields, expected):
    from app.evidence_roles import diagnose, question_fingerprint

    question = {'id': 'Q01', 'test_category': 'positive', 'question_subtype': '精确事实', **question_fields}
    source = {'chunk_id': 'DOC-a-V2-C-00001', 'content': '最高温度 +35°C'}
    role = {'claim_id': '1', 'claim': '最高温度', 'chunk_id': source['chunk_id'], 'match_text': source['content'],
            'role': 'condition', 'question_sha256': question_fingerprint(question)}
    case = {'passed': False, 'model_answer': '已保存回答。', 'judge_result': {'verdict': 'FAIL', **judge},
            'programmatic_metrics': {'latency_ms': 70000, 'retrieval_trace': {'candidates': [source], 'final': [source]}}}
    fault = diagnose(case, question, [role], [{'metric': 'latency_p99_seconds', 'threshold': 60}])
    assert fault['subtype'] == expected
    assert fault['question_type'] == ('负向 · 需追问' if question_fields.get('negative_subtype') else question['question_subtype'])
