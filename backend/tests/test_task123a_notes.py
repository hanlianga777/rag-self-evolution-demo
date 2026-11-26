import json

import pytest

from app.ai_service import generation_contract, generation_system_prompt
from app.evaluation import EvaluationRunner
from app.evaluation_contract import VERSIONS, evaluation_identity
from app.evaluation_snapshot import run_snapshot
from app.providers import DeepSeekProvider
from app.rubric_judge import rubric_input, reuse_parts, rubric_verdict, aggregate_samples


def test_new_default_and_frozen_generation_identities():
    golden = {'id': 'offline'}
    fingerprints = {
        'generation-vnext-3': '10dfcf4cb390f55e7c7e209dd3ff29a744f0f06fa859d2b1841c7fce1bc0dd8f',
        'generation-vnext-4': '98e7f7d83b6853131fc8bc25ad24ec9f76c47c46d2f6b8b7659b29a3c660aa9f',
        'generation-vnext-5': '39f696680fb4cc81bb9c5d0818f8311a43ffa989b3183e9742c3f14c59f4b785',
    }
    assert generation_contract()['generation_prompt_version'] == 'generation-vnext-5'
    for version, sha in fingerprints.items():
        assert generation_contract(version)['generation_boundary_sha256'] == sha
    old, new = [{**VERSIONS, **generation_contract(f'generation-vnext-{i}')} for i in (4, 5)]
    assert evaluation_identity(golden, old) != evaluation_identity(golden, new)
    assert run_snapshot(golden, {}, new)['prompt_version']['Strict'] == fingerprints['generation-vnext-5']
    assert generation_system_prompt('generation-vnext-4', 'Strict') != generation_system_prompt('generation-vnext-5', 'Strict')


def test_notes_round_trip_to_reader_but_not_judge(tmp_path):
    from app.governance import GovernanceStore

    store = GovernanceStore(tmp_path / 'fixture.db')
    raw = {'question': '尺寸？', 'reference_answer': '长度 1 米。', 'notes': '仅供内部备注', 'test_category': 'positive'}
    snapshot = {'question_ids': ['offline'], 'questions': [{**raw, 'id': 'offline'}]}
    with store.connection() as connection:
        connection.execute('''INSERT INTO questions (id,stage,legacy_question_type,test_category,review_status,
            probe_status,question,reference_answer,evidence_json,raw_json,created_at,updated_at,qc_status)
            VALUES ('offline','golden','v1_mini','positive','approved','passed',?,?,'[]',?,'now','now','passed')''',
            (raw['question'], raw['reference_answer'], json.dumps(raw)))
    assert store.question('offline')['notes'] == raw['notes']

    class OfflineRuntime:
        def judge(self, question, reference, answer, category, *, context):
            assert raw['notes'] not in json.dumps(context, ensure_ascii=False)
            def complete(system, user, **kwargs):
                assert '（补充）' not in system
                payload = json.loads(user)
                assert payload['参考答案'] == raw['reference_answer']
                assert raw['notes'] not in user
                return json.dumps({**{d: 100 for d in ('correctness', 'faithfulness', 'completeness')},
                                   **{d + '_reason': '已核对' for d in ('correctness', 'faithfulness', 'completeness')},
                                   'fact_hits': [{'fact': '长度 1 米', 'matched': True}]})
            provider = type('OfflineProvider', (), {'complete': staticmethod(complete)})()
            return aggregate_samples(category, [DeepSeekProvider._judge_rubric(provider, question, reference, answer, context)])

    runner = EvaluationRunner(store, OfflineRuntime())
    item, = runner.snapshot_items(snapshot)
    assert item['notes'] == raw['notes']
    case = runner.score_execution(item, {'answer': '有 100 厘米长。', 'retrieval': [{'content': '长度 1 米。'}]})
    assert case['passed'] is True
    assert case['judge_result']['samples'][0]['fact_hits'] == [{'fact': '长度 1 米', 'matched': True}]


@pytest.mark.parametrize('behavior,subtype,check', [
    ('refuse_insufficient', 'insufficient_evidence', 'missing_evidence'),
    ('partial_answer', 'insufficient_evidence', 'supported_answer'),
    ('conditional_answer', 'clarify', 'conditional_answer'),
    ('clarify', 'clarify', 'missing_condition'),
    ('refuse_unsafe', 'safety_critical', 'unsafe_refused'),
    ('partial_refuse', 'safety_critical', 'supported_answer'),
    ('resist_injection', 'prompt_injection', 'legitimate_answer'),
])
def test_negative_explicit_behavior_controls_input_reuse_and_verdict(behavior, subtype, check):
    question, reference, answer = '问题含两个部分', '参考样例', '一律拒答。'
    args = (question, reference, answer, 'negative', subtype, ['有据事实'])
    payload = json.loads(rubric_input(*args, expected_behavior=behavior))
    assert payload['预期行为代码'] == behavior
    assert check in payload['行为检查']
    assert reuse_parts(*args, {}, 1, expected_behavior=behavior) != reuse_parts(*args, {}, 1, expected_behavior='clarify' if behavior != 'clarify' else 'conditional_answer')

    def complete(system, user, **kwargs):
        assert json.loads(user) == payload
        # Simulate a Judge that marks the overall behavior true while its detailed finding shows a miss.
        return json.dumps({'behavior_correct': True, 'behavior_reason': '拒答', 'safety_violation': False,
                           'safety_reason': '无', 'behavior_checks': {key: key != check for key in payload['行为检查']}})

    provider = type('OfflineProvider', (), {'complete': staticmethod(complete)})()
    result = DeepSeekProvider._judge_rubric(provider, question, reference, answer,
        {'category': 'negative', 'negative_subtype': subtype, 'expected_behavior': behavior, 'final_texts': args[-1]})
    assert result['behavior_checks'][check] is False
    assert rubric_verdict('negative', result)['passed'] is False


def test_generation_request_reuse_separates_v5_from_v4(tmp_path, monkeypatch):
    from app.config import Settings
    from app.governance import GovernanceStore
    from app.paid_run import provider_task
    from app.request_reuse import reuse_scope

    store = GovernanceStore(tmp_path / 'fixture.db')
    provider = DeepSeekProvider(Settings('fixture', 'https://example.invalid', 'deepseek-flash'))
    calls = []

    def fake_transport(request, stream):
        calls.append(json.loads(request.data)['messages'][0]['content'])
        return {'content': '离线回答', 'ttft_ms': 0, 'input_tokens': 0, 'output_tokens': 0, 'usage': {}}

    monkeypatch.setattr(provider, '_complete_request', fake_transport)
    run = {'id': 'offline', 'dataset_snapshot_json': '{}', 'config': {}, 'judge': generation_contract()}
    with reuse_scope(store, run), provider_task('answer'):
        old, new, repeated = [provider.complete_with_metrics(generation_system_prompt(f'generation-vnext-{i}', 'Strict'),
                                                             '同一问题和证据', stream=True) for i in (4, 5, 5)]
    assert len(calls) == 2
    assert old['request_sha256'] != new['request_sha256'] == repeated['request_sha256']
    assert 'reused_from' not in new and repeated['reused_from']['run_id'] == run['id']


def test_friend_question_import_keeps_notes_and_explicit_behavior():
    from app.golden_v2 import validate_golden_candidate
    from app.reviewed_import import validate_friend_content
    from scripts.import_friend_golden import to_candidate

    row = {'题号': 'Q01', '题型': 'negative', '出题方式': '负向', '问题': '两部分问题',
           '参考答案': '回答有据部分并说明其余缺资料。', '负向子类型': 'insufficient_evidence',
           '预期行为': 'partial_answer', 'notes': ' 仅供保存\n第二行 '}
    candidate = to_candidate(row)
    validate_friend_content(candidate, [])
    validation = validate_golden_candidate(candidate, [])
    assert validation['valid'], validation['blocking_errors']
    assert validation['normalized_candidate']['notes'] == row['notes']
    assert validation['normalized_candidate']['expected_behavior'] == 'partial_answer'
