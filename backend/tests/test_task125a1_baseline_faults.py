from api_fixture import main
from app.agent_inputs import baseline_bad_case_rows
from app.agent_mechanism import faults_for_cases

from test_task118a_verdict import OfflineEvaluation, scored


def test_baseline_diagnostics_match_agent_primary_faults(tmp_path, monkeypatch):
    first = {}
    for number in range(1, 9):
        case = scored(False, '回答漏了要点')
        if number > 3:
            case['programmatic_metrics']['retrieval_trace']['candidates'].append({'chunk_id': 'standard'})
        first[f'Q{number:02d}'] = case
    env = OfflineEvaluation(tmp_path, monkeypatch, first, evidence=[{'source_chunk_ids': ['standard']}])
    env.stable_baseline()
    monkeypatch.setattr(main, 'store', env.store)

    references = baseline_bad_case_rows(env.store, env.baseline)
    agent = faults_for_cases(env.baseline, [row['result'] for row in references], references,
                             decision_version='122f')
    listed = main.bad_cases(light=True, baseline_id=env.base)
    full = main.evaluation_run(env.base)['cases']
    expected = [('recall', '致命')] * 3 + [('ranking', '严重')] * 5
    for rows in ([row['result'] for row in listed], full):
        faults = [row['bad_case_fault'] for row in sorted(rows, key=lambda row: row['question_id'])]
        assert [(fault['code'], fault['severity']) for fault in faults] == expected
        assert {fault['layer'] for fault in faults} == {'retrieval'}
        for row in rows:
            fault = row['bad_case_fault']
            assert {key: fault[key] for key in agent[row['question_id']]} == agent[row['question_id']]
    detail = main.bad_case(listed[0]['id'])['result']
    assert detail['bad_case_fault'] == listed[0]['result']['bad_case_fault']
