"""073：回答提示词三版本、问题拆解进入 Agent 可调范围；旧配置仍然合法。"""
from app.policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, FRIEND_BASELINE_CONFIG, validate_candidate_config
from app.ai_service import PROMPT_STRATEGIES, STRICT_STRATEGY


def test_prompt_variants_extend_strict():
    assert set(ALLOWED_SEARCH_SPACE['prompt_strategy']) == set(PROMPT_STRATEGIES) == {'Strict', 'StrictComplete', 'StrictSafe'}
    assert all(text.startswith(STRICT_STRATEGY) for text in PROMPT_STRATEGIES.values())


def test_candidate_may_change_prompt_and_decompose():
    for change in ({'prompt_strategy': 'StrictSafe'}, {'prompt_strategy': 'StrictComplete'}, {'query_decompose': True}):
        assert validate_candidate_config({**FRIEND_BASELINE_CONFIG, **change})['valid'], change
    assert not validate_candidate_config({**FRIEND_BASELINE_CONFIG, 'prompt_strategy': 'Loose'})['valid']


def test_historical_config_without_new_keys_still_valid():
    old = {k: v for k, v in DEFAULT_PIPELINE_CONFIG.items() if k not in {'query_decompose'}}
    assert validate_candidate_config(old)['valid']
    assert DEFAULT_PIPELINE_CONFIG['query_decompose'] is False and FRIEND_BASELINE_CONFIG['prompt_strategy'] == 'Strict'
