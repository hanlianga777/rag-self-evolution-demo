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
    # 109a–109g change planning/qualification, without changing Baseline or Judge
    # requests. Only known versions may anchor a new Candidate; resume stays strict.
    known_upgrade = (for_candidate_baseline and current['rules_hash'] == 'bb96bee3ca3b'
                     and current['prompt_version']['agent_system'] == '96ad675251b7055547d9ada7cca7454acd6f2f4e7e50d83f9a177740388c649a')
    legacy_rules = saved['rules_hash'] in {'f0d368403ec9', '2aa1acc7b9c0'}
    if known_upgrade and legacy_rules:
        changed.remove('rules_hash')
    saved_prompts = saved['prompt_version']
    current_prompts = current['prompt_version']
    ignored_prompts = set()
    # 109b expanded the search space for new Candidates. The saved Strict
    # Baseline still has to match the Judge and its generation prompt.
    if (known_upgrade and legacy_rules and (saved.get('pipeline_config') or {}).get('prompt_strategy') == rules.BASELINE['prompt_strategy']
            and (saved.get('search_space_version'), current['search_space_version']) == (
                '48ce7c816182ef9701d14ba944f35b2f658c84128f97b5f876906e3e6e9dbc3e',
                '272daae6a9c4061157e9665b43f016086180c2fa5d44111d79ac9ba7e195e0de')
            and saved_prompts.get('agent_system') == '3a6d515d2a3b78f0acf3cf020436468d80f665f411b3f40e8824b505c014172a'):
        changed.remove('search_space_version')
        ignored_prompts = {'agent_system'} | ({rules.STEPWISE, rules.GROUNDED, rules.TABLE_CHECK} - saved_prompts.keys())
    elif (known_upgrade and legacy_rules and saved.get('search_space_version') == current['search_space_version']
            and saved_prompts.get('agent_system') == '4ca6578f34f254a015f1784c0c10cb5bfa0778a5dfe2c2cb70b31a2673747df7'):
        ignored_prompts = {'agent_system'}
    elif (known_upgrade and saved['rules_hash'] == current['rules_hash'] and not changed
            and (saved.get('pipeline_config') or {}).get('prompt_strategy') == rules.BASELINE['prompt_strategy']
            and saved_prompts.get('agent_system') == '02b20fea1fdb4a999d785307ff26a2fc40c0c1c70d5d8ca893e1c315f7e0166e'):
        ignored_prompts = {'agent_system'}
    changed.extend(f'prompt_version.{name}' for name, fingerprint in current_prompts.items()
                   if name not in ignored_prompts and saved_prompts.get(name) != fingerprint)
    if changed:
        raise ValueError('续跑启动快照已变化：' + '、'.join(changed))


def shared_judge(judge):
    """The shared scoring contract excludes the Baseline or Candidate's own run snapshot."""
    return {key: value for key, value in judge.items() if key != 'run_snapshot'}
