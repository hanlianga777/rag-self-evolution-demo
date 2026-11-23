"""085：用离线检索检查按生效规则生成的补扫组合。"""
from types import SimpleNamespace
from unittest.mock import Mock

from api_fixture import main
from app.policy import ALLOWED_SEARCH_SPACE, FRIEND_BASELINE_CONFIG
from scripts import retrieval_headroom


def test_scan_includes_legal_recall_pairs_and_wider_combinations(tmp_path, monkeypatch):
    question_file = tmp_path / 'questions.csv'
    question_file.write_text('题号,题型,问题,证据\nQ01,positive,离线测试,C1｜示例证据\n', encoding='utf-8')
    retrieve = Mock(return_value=([], {}))
    corpus = SimpleNamespace(index_info=lambda: {'knowledge_identity': {'corpus_id': 'fixture'}})
    monkeypatch.setattr(main, 'ai_service', SimpleNamespace(
        live_enabled=True, corpus=corpus, retrieve_context=retrieve,
    ))
    database = tmp_path / 'fixture.db'
    monkeypatch.setenv('RAG_DEMO_DB_PATH', str(database))
    monkeypatch.setenv('RAG_SAFE_START', '1')

    retrieval_headroom.main(['--csv', str(question_file), '--database', str(database), '--pairs', '0'])

    baseline = {**FRIEND_BASELINE_CONFIG, 'knowledge_identity': {'corpus_id': 'fixture'}}
    changes = [
        {key: value for key, value in call.args[1].items() if value != baseline[key]}
        for call in retrieve.call_args_list
    ]
    top_k = max(ALLOWED_SEARCH_SPACE['top_k'])
    candidate_k = max(ALLOWED_SEARCH_SPACE['candidate_k'])
    assert {'top_k': top_k, 'candidate_k': candidate_k} in changes
    recall_keys = {'candidate_k', 'multi_query', 'query_decompose', 'hyde', 'query_rewrite', 'min_score'}
    assert {
        key for change in changes if len(change) == 2 and change.get('top_k') == top_k
        for key in change if key != 'top_k'
    } == recall_keys
    assert {'top_k': top_k, 'candidate_k': candidate_k, 'min_score': min(ALLOWED_SEARCH_SPACE['min_score'])} in changes
    assert all(value in ALLOWED_SEARCH_SPACE[key] for change in changes for key, value in change.items())
