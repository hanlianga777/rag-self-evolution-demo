"""回答提示词与问题拆解的选项、校验和历史兼容性。"""
from hashlib import sha256

from app.policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, FRIEND_BASELINE_CONFIG, search_space_contract, validate_candidate_config
from app.ai_service import GENERATION_PROMPT_VERSION, LEGACY_PROMPT_STRATEGIES, PROMPT_STRATEGIES, STRICT_STRATEGY, generation_boundary, generation_system_prompt
from app.optimization import build_agent_prompt


def test_prompt_variants_extend_strict():
    assert set(ALLOWED_SEARCH_SPACE['prompt_strategy']) == set(PROMPT_STRATEGIES) == {
        'Strict', 'Looser', 'Safe',
    }
    assert all(text.startswith(STRICT_STRATEGY) for text in PROMPT_STRATEGIES.values())


def test_candidate_may_change_prompt_and_decompose():
    for strategy in ('Looser', 'Safe'):
        assert strategy in search_space_contract()['prompt_strategy']['allowed']
        assert generation_system_prompt(GENERATION_PROMPT_VERSION, strategy).startswith(generation_boundary(GENERATION_PROMPT_VERSION) + '\n回答策略：')
        assert generation_system_prompt('generation-vnext-4', strategy).endswith(PROMPT_STRATEGIES[strategy])
        assert validate_candidate_config({**FRIEND_BASELINE_CONFIG, 'prompt_strategy': strategy})['valid']
    for strategy, prompt in LEGACY_PROMPT_STRATEGIES.items():
        assert generation_system_prompt(GENERATION_PROMPT_VERSION, strategy).endswith(prompt)
        assert not validate_candidate_config({**FRIEND_BASELINE_CONFIG, 'prompt_strategy': strategy})['valid']
    assert validate_candidate_config({**FRIEND_BASELINE_CONFIG, 'query_decompose': True})['valid']
    assert not validate_candidate_config({**FRIEND_BASELINE_CONFIG, 'prompt_strategy': 'Loose'})['valid']


def test_historical_config_without_new_keys_still_valid():
    old = {k: v for k, v in DEFAULT_PIPELINE_CONFIG.items() if k not in {'query_decompose'}}
    assert validate_candidate_config(old)['valid']
    assert DEFAULT_PIPELINE_CONFIG['query_decompose'] is False and FRIEND_BASELINE_CONFIG['prompt_strategy'] == 'Strict'


def test_current_strict_and_historical_grounded_keep_their_exact_prompts():
    assert GENERATION_PROMPT_VERSION == 'generation-vnext-5'
    expected = {
        ('generation-vnext-4', 'Strict'): 'a4c1510da62a9ec7525d4c3b453704a4db50cc31ce517b48c40a40a565bad6ae',
        ('generation-vnext-2', 'Grounded'): 'c6add1d575f33d70a8f62d32edde885bd6a7d8dc0a0a9c2843728be987634d5f',
        ('generation-vnext-3', 'Grounded'): 'f7e8d0cb31f2e0f65753785b5b757ebdeee66d544b4883589633e353a21aa758',
    }
    for (version, strategy), digest in expected.items():
        assert sha256(generation_system_prompt(version, strategy).encode()).hexdigest() == digest


def test_agent_can_name_safety_critical_and_injection_questions_in_prompt_strategy_risks():
    system, data = build_agent_prompt([], FRIEND_BASELINE_CONFIG, [], [], ['A'], golden_questions=[
        {'id': 'critical', 'negative_subtype': 'safety_critical'},
        {'id': 'injection', 'negative_subtype': 'prompt_injection'},
        {'id': 'positive', 'test_category': 'positive'},
    ])
    assert data['prompt_strategy_risk_questions'] == {'safety_critical': ['critical'], 'prompt_injection': ['injection']}
    for strategy in ('Grounded', 'Stepwise', 'TableCheck'):
        assert strategy not in system
    assert '换提示词会影响整卷回答' in system
    assert '在risks里按题号点名安全关键题和提示注入题' in system
