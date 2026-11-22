"""Execution rules for the 2026-11-20 rulebook."""

import hashlib
import json

RULES_VERSION = '2026-11-20b'
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
    'thinking_locked': True,
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
        'retrieval_max_tokens',
    ],
}
AGENT['candidates_per_round'] = len(AGENT['candidate_labels'])
QUALIFICATION = {'version': RULES_VERSION, 'max_new_critical': 0, 'max_new_failures': 0, 'min_fixed': 1}
AUTHORIZATION = {
    'gate2': {'delegated': True, 'authorizer': '用户', 'executed_by': '总指挥',
              'review_method': '预授权代确认', 'reviewers': ['claude', 'gpt']},
    'gate3': {'delegated': True, 'authorizer': '用户', 'executed_by': '总指挥',
              'review_method': '用户睡前授权代发布', 'reviewers': ['claude', 'gpt']},
}
LAUNCH = {'min_bad_cases': 5}
CONSISTENCY_CHECK = {'questions': 10, 'min_agree': 9}

def canonical_hash(value):
    canonical = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


# Pipeline value domains also support reading and comparing historical runs.
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
    "prompt_strategy": (STRICT, LOOSER, SAFE, STEPWISE, GROUNDED, TABLE_CHECK),
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
