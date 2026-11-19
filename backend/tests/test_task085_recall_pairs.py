"""085：父子切块下 Top-K 挡住召回收益，扫描固定补扫"Top-K 最大 + 召回类参数"组合。"""
from app.policy import ALLOWED_SEARCH_SPACE
from scripts.retrieval_headroom import RECALL_PAIR_PARTNERS


def test_recall_partners_are_legal_search_values():
    for key, value in RECALL_PAIR_PARTNERS:
        assert value in ALLOWED_SEARCH_SPACE[key], (key, value)
    assert max(ALLOWED_SEARCH_SPACE['top_k']) == 6
