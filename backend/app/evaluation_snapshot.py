"""Bind new evaluation records to the rules and templates available at startup."""

import hashlib

from . import rules
from .policy import DEFAULT_PIPELINE_CONFIG


def _versions(judge):
    from .ai_service import GENERATION_PROMPT_VERSION, generation_system_prompt
    from .optimization import ROUND_LABELS, build_agent_prompt
    from .rubric_judge import RUBRIC_JUDGE_PROMPT

    generation_version = judge.get('generation_prompt_version', GENERATION_PROMPT_VERSION)
    # Enable every optional system-message paragraph. Case data affects only the user message.
    agent_system, _ = build_agent_prompt([], DEFAULT_PIPELINE_CONFIG, [], [], ROUND_LABELS,
        retrieval_preview={'configs': []}, round_policy={'mode': 'full_rounds'}, causal_evidence=True)
    prompts = {strategy: generation_system_prompt(generation_version, strategy)
               for strategy in rules.PIPELINE_VALUES['prompt_strategy']}
    prompts.update(judge=RUBRIC_JUDGE_PROMPT, agent_system=agent_system)
    return {
        'rules_hash': rules.RULES_HASH,
        'search_space_version': rules.canonical_hash({key: rules.PIPELINE_VALUES[key] for key in rules.AGENT['tunable']}),
        'prompt_version': {name: hashlib.sha256(template.encode()).hexdigest() for name, template in prompts.items()},
    }


def run_snapshot(golden, config, judge):
    from .rubric_judge import DEFAULT_JUDGE_SAMPLES

    pipeline = {key: value for key, value in config.items()
                if key not in {'run_target', 'candidate_id', 'source_evaluation_id'}}
    return {
        **_versions(judge),
        'rules_version': rules.RULES_VERSION,
        'pipeline_config': {**DEFAULT_PIPELINE_CONFIG, **pipeline, 'temperature': rules.BASELINE['temperature']},
        'judge_config': {'model': judge.get('model'),
                         'thinking': judge.get('judge_thinking', {}).get('reasoning_effort', rules.JUDGE['thinking']),
                         'temperature': rules.JUDGE['temperature'], 'samples': DEFAULT_JUDGE_SAMPLES},
        'golden_version': golden['id'],
        'knowledge_identity': golden.get('corpus_fingerprint'),
    }


def require_resume_snapshot(judge, current_judge=None, *, for_candidate_baseline=False):
    saved = judge.get('run_snapshot')
    if not isinstance(saved, dict) or not saved.get('rules_hash') or not isinstance(saved.get('prompt_version'), dict):
        raise ValueError('续跑原记录缺少 rules_hash 或 prompt_version，无法验证启动快照')
    current = _versions(current_judge if current_judge is not None else judge)
    changed = [field for field in ('rules_hash', 'search_space_version') if saved.get(field) != current[field]]
    saved_prompts = saved['prompt_version']
    current_prompts = current['prompt_version']
    # A completed Strict Baseline can anchor the new verdict contract when its
    # frozen answer and Judge templates match. Resumes still compare every field.
    strict_baseline = (for_candidate_baseline
                       and saved.get('rules_version') in {None, '2026-11-20', '2026-11-20b'}
                       and saved.get('rules_hash') in {'f0d368403ec9', '2aa1acc7b9c0', 'bb96bee3ca3b', 'a1b4d0991ca6'}
                       and (saved.get('pipeline_config') or {}).get('prompt_strategy') == rules.STRICT)
    if strict_baseline:
        changed.clear()
        current_prompts = {name: current_prompts[name] for name in (rules.STRICT, 'judge')}
    changed.extend(f'prompt_version.{name}' for name, fingerprint in current_prompts.items()
                   if saved_prompts.get(name) != fingerprint)
    if changed:
        raise ValueError('续跑启动快照已变化：' + '、'.join(changed))


def shared_judge(judge):
    """The shared scoring contract excludes the Baseline or Candidate's own run snapshot."""
    return {key: value for key, value in judge.items() if key != 'run_snapshot'}
