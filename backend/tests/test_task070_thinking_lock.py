"""070 噪声根治：Baseline 关闭思考时，Agent 方案不得改 generation_thinking；旧口径不受影响。"""
import pytest
from app.optimization import validate_round_contract
from app.policy import FRIEND_BASELINE_CONFIG


def _cands(diff_a):
    return [{'id': 'A', 'config_diff': diff_a}, {'id': 'B', 'config_diff': {'top_k': 6}}, {'id': 'C', 'config_diff': {'candidate_k': 24}}]


def test_friend_baseline_is_thinking_off():
    assert FRIEND_BASELINE_CONFIG['generation_thinking'] == 'off'


def test_thinking_change_rejected_when_baseline_off():
    with pytest.raises(ValueError, match='思考档位已锁定'):
        validate_round_contract(_cands({'generation_thinking': 'high'}), dict(FRIEND_BASELINE_CONFIG), [])


def test_retrieval_only_round_passes_when_baseline_off():
    validate_round_contract(_cands({'multi_query': 2}), dict(FRIEND_BASELINE_CONFIG), [])


def test_old_baseline_with_thinking_still_allows_change():
    validate_round_contract(_cands({'generation_thinking': 'low'}), {**FRIEND_BASELINE_CONFIG, 'generation_thinking': 'max'}, [])
