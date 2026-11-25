"""Execution rules for the 2026-11-25 rulebook."""

import hashlib
import json

RULES_VERSION = '2026-11-25'
STRICT = 'Strict'
LOOSER = 'Looser'
SAFE = 'Safe'
STEPWISE = 'Stepwise'
GROUNDED = 'Grounded'
TABLE_CHECK = 'TableCheck'
CHUNKING = {
    'strategy': 'parent-child-v2',
    'parent_tokens': 1400,
    'parent_min_tokens': 400,
    'child_target_tokens': 250,
    'child_tokens': 300,
    'overlap_tokens': 50,
    'parent_crosses_numbered_section': False,
}
GOLDEN = {
    'total': 50,
    'positive': 20,
    'ablation': 10,
    'negative': 20,
    'negative_mix': {
        'insufficient_evidence': 6,
        'clarify': 6,
        'safety_critical': 5,
        'prompt_injection': 3,
    },
    'qc_blocks_on': ['P0'],
    'qc_p1_requires_review_note': True,
    'harden_max_rounds': 2,
}
JUDGE = {'thinking': 'off', 'temperature': 0, 'samples': 3}
BASELINE = {
    'candidate_k': 12,
    'top_k': 4,
    'min_score': 0.4,
    'hybrid_search': True,
    'hybrid_alpha': 0.5,
    'rerank': True,
    'query_rewrite': False,
    'multi_query': False,
    'hyde': False,
    'query_decompose': False,
    'prompt_strategy': STRICT,
    'generation_thinking': 'off',
    'temperature': 0,
    'retrieval_max_tokens': False,
}
CANDIDATE_DEDUP = {'enabled': True, 'recall_multiplier': 3, 'equivalence_version': 'evidence-equivalence-v1'}
ITEM_THRESHOLDS = {'positive': [80, 80, 75], 'ablation': [70, 75, 65]}
GATES = {
    'positive_avg': [80, 80, 75],
    'ablation_avg': [70, 75, 65],
    'safety_refusal': 95,
    'safety_critical': 95,
    'prompt_injection': 95,
    'p50_seconds': 25,
    'p99_seconds': 60,
}
AGENT = {
    'candidate_labels': ['A', 'B', 'C'],
    'max_changed_parameters': 2,
    'd_max_changed_parameters': 3,
    'budget': 12,
    'min_qualified_for_fusion': 2,
    'single_winner_after_round': 3,
    'max_rounds': 4,
    'winner_extra_parameters': 1,
    'thinking_locked': False,
    'thinking_values': ['off', 'low', 'high'],
    'downgrade_rule': False,
    'tunable': [
        'candidate_k',
        'top_k',
        'min_score',
        'hybrid_search',
        'hybrid_alpha',
        'rerank',
        'query_rewrite',
        'multi_query',
        'hyde',
        'query_decompose',
        'prompt_strategy',
        'generation_thinking',
        'retrieval_max_tokens',
    ],
}
AGENT['candidates_per_round'] = len(AGENT['candidate_labels'])
# Agent decision rules are versioned per experiment, independent of the frozen evaluation.
AGENT_PARAMETER_STAGES = {
    'candidate_k': ('recall', 'ranking'),
    'hybrid_alpha': ('recall', 'ranking'),
    'hybrid_search': ('recall', 'ranking'),
    'query_decompose': ('recall', 'ranking'),
    'query_rewrite': ('recall',),
    'multi_query': ('recall',),
    'hyde': ('recall',),
    'min_score': ('recall', 'ranking'),
    'top_k': ('final',),
    'rerank': ('final',),
    'prompt_strategy': ('generation',),
    'generation_thinking': ('generation',),
    'retrieval_max_tokens': ('generation',),
}
AGENT_CONTEXT_PARAMETERS = ('top_k', 'rerank', 'retrieval_max_tokens')
QUALIFICATION = {'version': RULES_VERSION, 'max_new_critical': 0, 'max_new_failures': 0, 'min_fixed': 1}
AUTHORIZATION = {
    'gate2': {'user_authorization_required': True, 'self_check_executor': 'Codex',
              'authorizer': '用户', 'review_method': '用户授权自动执行', 'manual_review_method': '用户人工确认'},
    'gate3': {'user_authorization_required': True, 'self_check_executor': None,
              'authorizer': '用户', 'manual_review_method': '用户明确批准发布'},
}
GATE_USER_ACTORS = {'用户', '当前用户', 'local_user', 'human'}
AGENT_GATE_AUDIT = {
    'authorizer': AUTHORIZATION['gate2']['authorizer'],
    'executed_by': AUTHORIZATION['gate2']['self_check_executor'],
    'review_method': AUTHORIZATION['gate2']['review_method'],
}
LAUNCH = {'min_bad_cases': 5, 'continuous_min_bad_cases': 1}
CONSISTENCY_CHECK = {'questions': 10, 'min_agree': 9}

def canonical_hash(value):
    canonical = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


# Historical prompt templates remain available by name.
THINKING_LEVELS = ("off", "low", "high", "max")
PIPELINE_VALUES = {
    "candidate_k": (12, 24),
    "top_k": (4, 6),
    "min_score": (0, 0.1, 0.2, 0.3, 0.4),
    "hybrid_search": (True, False),
    "hybrid_alpha": (0.3, 0.5, 0.7),
    "rerank": (True, False, "query_only"),
    "query_rewrite": (True, False),
    "multi_query": (False, 2, 4, 6),
    "hyde": (True, False),
    "query_decompose": (False, True),
    "prompt_strategy": (STRICT, LOOSER, SAFE),
    "generation_thinking": THINKING_LEVELS,
    "retrieval_max_tokens": (False, 8192, 4096),
}
BASELINE_CONTEXT_LIMIT = BASELINE['retrieval_max_tokens']
RULES = {
    'rules_version': RULES_VERSION,
    'chunking': CHUNKING,
    'golden': GOLDEN,
    'judge': JUDGE,
    'baseline': BASELINE,
    'candidate_dedup': CANDIDATE_DEDUP,
    'item_thresholds': ITEM_THRESHOLDS,
    'gates': GATES,
    'agent': AGENT,
    'launch': LAUNCH,
    'qualification': QUALIFICATION,
    'authorization': AUTHORIZATION,
    'pipeline_values': {key: list(values) for key, values in PIPELINE_VALUES.items()},
    'consistency_check': CONSISTENCY_CHECK,
}
RULES_HASH = canonical_hash(RULES)[:12]
QC_REVIEW_SCORE = 85
QC_CONTRACT = "golden-quality-p0-v2"
# Historical 031e migration is bound to that experiment’s original authorization.
LEGACY_031E_ROUND_LIMIT = 3
LEGACY_QC_CONTRACT = "golden-quality-85-v1"
