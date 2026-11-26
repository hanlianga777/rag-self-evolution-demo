"""Offline checks against the final M2 and M3 CSVs and the active read-only corpus."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import rules
from app.ai_service import AiService
from app.corpus import CorpusStore
from app.evaluation import EvaluationRunner
from app.golden_v2 import validate_golden_candidate
from app.governance import GovernanceStore
from app.providers import DeepSeekProvider
from app.reviewed_import import FRIEND_CONTRACT, validate_friend_content
from app.rubric_judge import aggregate_samples
from scripts.import_friend_golden import main, to_candidate


REPORTS = Path(__file__).resolve().parents[2] / '指挥/报告'
M2 = REPORTS / 'M2-题卷定稿.csv'
M3 = REPORTS / 'M3-备用池定稿.csv'
NEW_TEXT_FIELDS = {'题型细分': 'question_subtype', '真实问法理由': 'realism_note',
                   '必要安全前提': 'safety_premise', '部分可答': 'partial_answerable', '替换槽位': 'replace_slot'}


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as source:
        return list(csv.DictReader(source))


@pytest.fixture
def store(tmp_path):
    return GovernanceStore(tmp_path / 'import.db')


def import_csv(store, path, *options):
    return main(['--database', str(store.database_path), '--csv', str(path), '--apply', *options])


@pytest.fixture
def negative_probe(store):
    class Retriever:
        def search(self, question, limit):
            return [{'chunk_id': 'fixture', 'score': .9, 'content': '相关资料'}]

        def full_text_probe(self, question):
            return {'matches': [], 'coverage': {'status': 'complete'}}

    def run(subtype, behavior, *, answerable=False, matched=True, contract=FRIEND_CONTRACT):
        candidate = {'question': '设备需要哪些操作条件？', 'test_category': 'negative',
                     'negative_subtype': subtype, 'expected_behavior': behavior,
                     'golden_contract': contract, 'import_row': 1}
        key, = store.save_business_candidates([candidate], 'offline.csv', 'offline')

        def answerability_judge(question, hits, signals):
            assert signals['negative_subtype'] == subtype
            return {'answerable': answerable, 'reason': '本地可答性检查'}

        def subtype_judge(question, hits, signals):
            assert signals == {'negative_subtype': subtype, 'expected_behavior': behavior}
            return {'matched': matched, 'detected_subtype': subtype, 'reason': '本地语义检查'}

        return store.run_probe(key, Retriever(), [], answerability_judge,
                               subtype_judge=subtype_judge, fail_on_judge_error=True)

    return run


@pytest.mark.parametrize(('subtype', 'behavior'), [
    ('insufficient_evidence', 'insufficient_evidence'),
    ('insufficient_evidence', 'refuse_insufficient'),
    ('insufficient_evidence', 'partial_answer'),
    ('clarify', 'clarify'),
    ('clarify', 'conditional_answer'),
    ('safety_critical', 'safe_rejection'),
    ('safety_critical', 'refuse_unsafe'),
    ('safety_critical', 'partial_refuse'),
    ('prompt_injection', 'prompt_injection_resistance'),
    ('prompt_injection', 'resist_injection'),
])
def test_friend_negative_probe_accepts_legal_subtype_behavior(negative_probe, subtype, behavior):
    probe = negative_probe(subtype, behavior)
    assert probe['classification'] == 'NEGATIVE_VALID'
    checks = probe['probe_details']['negative_checks']
    if subtype in {'clarify', 'insufficient_evidence'}:
        assert checks['answerability']['answerable'] is False
    else:
        assert checks['subtype_semantic']['detected_subtype'] == subtype


def test_friend_negative_probe_rejects_behavior_from_wrong_subtype(negative_probe):
    probe = negative_probe('insufficient_evidence', 'resist_injection')
    assert probe['classification'] == 'NEGATIVE_SUBTYPE_MISMATCH'
    assert not probe['passed']


@pytest.mark.parametrize(('subtype', 'behavior'), [
    ('insufficient_evidence', 'partial_answer'),
    ('clarify', 'conditional_answer'),
])
def test_friend_negative_probe_rejects_fully_answerable_questions(negative_probe, subtype, behavior):
    probe = negative_probe(subtype, behavior, answerable=True)
    assert probe['classification'] == 'FAKE_NEGATIVE_RISK'
    assert not probe['passed']


@pytest.mark.parametrize(('subtype', 'behavior'), [
    ('safety_critical', 'partial_refuse'),
    ('prompt_injection', 'resist_injection'),
])
def test_friend_negative_probe_rejects_semantic_mismatch(negative_probe, subtype, behavior):
    probe = negative_probe(subtype, behavior, matched=False)
    assert probe['probe_details']['negative_checks']['subtype_semantic']['matched'] is False
    assert probe['classification'] == 'NEGATIVE_SUBTYPE_MISMATCH'
    assert not probe['passed']


def test_legacy_negative_probe_keeps_exact_behavior_match(negative_probe):
    probe = negative_probe('insufficient_evidence', 'partial_answer', contract=None)
    assert probe['classification'] == 'NEGATIVE_SUBTYPE_MISMATCH'
    assert not probe['passed']


def test_final_csv_60_rows_validate_and_persist_raw_fields(store):
    chunks = CorpusStore().chunks()
    total = 0
    for path, options, expected in [(M2, [], 50), (M3, ['--pool', 'backup'], 10)]:
        rows = read_rows(path)
        assert len(rows) == expected
        result = import_csv(store, path, *options)
        assert result['error_rows'] == 0
        ids = result['receipt']['question_ids']
        assert len(ids) == len(rows)
        for row, question_id in zip(rows, ids, strict=True):
            candidate = to_candidate(row)
            validate_friend_content(candidate, chunks)
            validation = validate_golden_candidate(candidate, chunks)
            assert validation['valid'], (row['题号'], validation['blocking_errors'])
            question = store.question(question_id)
            raw = question['raw']
            assert raw['display_id'] == row['题号']
            assert raw['paired_question'] == (row['配对题号'] or None)
            for column, field in NEW_TEXT_FIELDS.items():
                assert candidate[field] == raw[field] == (row[column] or None)
            basis = [
                {'chunk_id': line.split('｜', 1)[0], 'quote': line.split('｜', 1)[1]}
                for line in row['负向依据'].splitlines() if line.strip()
            ]
            assert candidate['negative_basis'] == raw['negative_basis'] == (basis or None)
            if row['题型'] == 'negative':
                assert question['evidence'] == raw['evidence'] == raw['acceptable_evidence'] == []
            total += 1
    assert total == 60


def test_negative_basis_requires_strict_quote_location():
    row = next(row for row in read_rows(M3) if row['负向依据'])
    chunks = CorpusStore().chunks()
    chunk_id, _, quote = row['负向依据'].splitlines()[0].partition('｜')
    with pytest.raises(ValueError, match='负向依据.*找不到'):
        validate_friend_content(to_candidate({**row, '负向依据': f'{chunk_id}｜{quote}⟦不存在⟧'}), chunks)
    with pytest.raises(ValueError, match='负向依据.*格式'):
        to_candidate({**row, '负向依据': '缺少切块编号和分隔符'})
    with pytest.raises(ValueError, match='负向依据.*切块'):
        validate_friend_content(to_candidate({**row, '负向依据': f'missing｜{quote}'}), chunks)
    with pytest.raises(ValueError, match='负向题不填证据'):
        to_candidate({**row, '证据': f'{chunk_id}｜{quote}'})
    assert to_candidate({**row, '部分可答': '  原样保存  ', '必要安全前提': '  '})['partial_answerable'] == '  原样保存  '
    assert to_candidate({**row, '必要安全前提': '  '})['safety_premise'] is None


def test_negative_basis_only_reaches_qc_prompt_for_negative_questions(store):
    result = import_csv(store, M2)
    negative, positive = store.question(result['receipt']['question_ids'][32]), store.question(result['receipt']['question_ids'][0])
    assert negative['raw']['display_id'] == 'Q33'
    basis = negative['raw']['negative_basis']
    assert basis
    requests = []

    def qc_complete(system, user, **kwargs):
        requests.append(json.loads(user))
        return json.dumps({'score': 90, 'priority': 'P2', 'issues': [], 'reason': '本地测试'})

    provider = SimpleNamespace(settings=SimpleNamespace(configured=True, model='offline'), complete=qc_complete)
    service = AiService(store, CorpusStore(), provider, False)
    service._quality_check(negative)
    service._quality_check({**positive, 'raw': {**positive['raw'], 'negative_basis': basis}})
    assert requests[0]['negative_basis'] == basis
    assert requests[0]['evidence'] == []
    assert 'negative_basis' not in requests[1]

    def judge_complete(system, user, **kwargs):
        assert 'negative_basis' not in user
        assert all(source['quote'] not in user for source in basis)
        payload = json.loads(user)
        assert payload['参考答案'] == negative['reference_answer']
        assert payload['预期行为代码'] == negative['raw']['expected_behavior']
        assert payload['检索资料'] == []
        return json.dumps({'behavior_correct': True, 'behavior_reason': '本地测试', 'safety_violation': False,
                           'safety_reason': '本地测试',
                           'behavior_checks': {'missing_evidence': True, 'supported_answer': True}})

    def judge(question, expected, answer, category, *, context):
        assert 'negative_basis' not in context
        offline = SimpleNamespace(complete=judge_complete)
        return aggregate_samples(category, [DeepSeekProvider._judge_rubric(offline, question, expected, answer, context)])

    runner = EvaluationRunner(store, SimpleNamespace(judge=judge))
    item, = runner.snapshot_items({'question_ids': [negative['id']], 'questions': [negative['raw']]})
    assert runner.score_execution(item, {'answer': '本地测试用回答', 'retrieval': []})['passed']


def test_backup_freezes_through_gate_without_replacing_current_golden(store):
    main_receipt = import_csv(store, M2)['receipt']
    with pytest.raises(ValueError, match='Q01–Q50'):
        import_csv(store, M3)
    backup = import_csv(store, M3, '--pool', 'backup')['receipt']
    assert store.working_generation_run()['id'] == main_receipt['generation_run_id']
    assert not set(backup['question_ids']) & {item['id'] for item in store.active_pool_rows()}
    with pytest.raises(ValueError, match='备用池'):
        store.preview_pool_run('medium', backup['question_ids'][:1], [])
    with pytest.raises(ValueError, match='备用池'):
        store.rematch_profile_run(backup['generation_run_id'], 'medium', [], {})
    with pytest.raises(ValueError):
        store.create_generation_snapshot(backup['generation_run_id'])

    def review_with_offline_results(receipt):
        for question_id in receipt['question_ids']:
            store.record_probe_result(question_id, {'question_quality': 30, 'golden_answer_quality': 30,
                                                     'evidence_support': 40, 'reason': '本地测试'})
            store.record_qc(question_id, {'priority': 'P2', 'score': 90, 'reason': '本地测试',
                                         'rule_version': rules.QC_CONTRACT}, 'passed')
        store.review_generation_batch(receipt['question_ids'], 'offline', confirmed_manual_review=True,
                                      reason='本地测试 Gate 1')

    review_with_offline_results(main_receipt)
    current = store.create_generation_snapshot(main_receipt['generation_run_id'])
    review_with_offline_results(backup)
    frozen = store.create_generation_snapshot(backup['generation_run_id'])
    assert frozen == store.create_generation_snapshot(backup['generation_run_id'])
    assert [q['display_id'] for q in frozen['questions']] == [f'B{i:02d}' for i in range(1, 11)]
    assert [q['replace_slot'] for q in frozen['questions']] == ['Q05', 'Q04', 'Q11', 'Q20', 'Q26', 'Q25', 'Q31', 'Q38', 'Q47', 'Q49']
    assert [snapshot['id'] for snapshot in store.dataset_snapshots()] == [current['id']]
    assert store.current_baseline_identity()['current_golden_id'] == current['id']
    with store.connection() as connection, pytest.raises(ValueError, match='Golden身份已变化'):
        store.validate_evaluation_start(connection, frozen, {})
    assert not set(backup['question_ids']) & {item['id'] for item in store.questions('golden')}
    with pytest.raises(ValueError, match='备用池'):
        store.create_dataset_snapshot([store.question(key) for key in backup['question_ids']])
    with pytest.raises(ValueError, match='备用池'):
        store.reopen_snapshot_question(backup['question_ids'][0], frozen['id'], actor='offline', reason='本地测试')
