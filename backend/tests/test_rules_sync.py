"""Keep the live rule values and their explanations aligned with the rulebook."""
import ast
import hashlib
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENV_KEYS = {'BASELINE_THINKING', 'JUDGE_THINKING', 'JUDGE_SAMPLES'}


def test_rulebook_machine_contract():
    from app import rules
    from app.policy import ALLOWED_SEARCH_SPACE, CANDIDATE_QUALIFICATION_VERSION, FRIEND_BASELINE_CONFIG, MAX_EVALS
    data = re.search(r'```json rules\s*\n(.*?)\n```',
                     (ROOT / '指挥/规则总表.md').read_text(), re.S)
    assert data
    documented = json.loads(data[1])
    assert json.dumps(rules.RULES, sort_keys=True) == json.dumps(documented, sort_keys=True)
    canonical = json.dumps(documented, sort_keys=True, separators=(',', ':'))
    assert getattr(rules, 'RULES_HASH', None) == hashlib.sha256(canonical.encode()).hexdigest()[:12]
    assert rules.RULES_VERSION == rules.RULES['rules_version']
    assert rules.RULES_VERSION == CANDIDATE_QUALIFICATION_VERSION == '2026-11-20b'
    assert rules.AGENT['max_changed_parameters'] == 2
    assert rules.AGENT['d_max_changed_parameters'] == 3
    assert all(FRIEND_BASELINE_CONFIG[key] == value for key, value in rules.BASELINE.items())
    assert set(ALLOWED_SEARCH_SPACE) - {'generation_thinking'} == set(rules.AGENT['tunable'])
    assert MAX_EVALS == rules.AGENT['budget']


def test_completed_baseline_snapshot_allows_109a_upgrade_only():
    from app.evaluation_snapshot import require_resume_snapshot, run_snapshot

    snapshot = run_snapshot({'id': 'frozen'}, {}, {})
    saved = {'run_snapshot': {**snapshot, 'rules_hash': 'f0d368403ec9', 'rules_version': '2026-11-20'}}
    require_resume_snapshot(saved, for_candidate_baseline=True)
    with pytest.raises(ValueError, match='rules_hash'):
        require_resume_snapshot(saved)
    saved['run_snapshot']['prompt_version']['Strict'] = 'changed'
    with pytest.raises(ValueError, match='prompt_version.Strict'):
        require_resume_snapshot(saved, for_candidate_baseline=True)
    saved['run_snapshot']['rules_hash'] = 'unknown'
    with pytest.raises(ValueError, match='rules_hash'):
        require_resume_snapshot(saved, for_candidate_baseline=True)


def test_current_explanations():
    from app.policy import PARAMETER_EXPLANATIONS
    assert PARAMETER_EXPLANATIONS['generation_thinking'][0] == 'Baseline 关闭思考，Agent 不调这一项'
    files = ['backend/app/optimization.py', 'frontend/src/display.ts', 'frontend/src/helpText.ts']
    for name in files:
        source = (ROOT / name).read_text()
        assert not re.search(r'Baseline\s*用\s*(?:Max|High)|降档补位|保证同一请求结果一致', source), name
    assert '判定稳定，回答文字仍可能不同' in (ROOT / files[0]).read_text()
    for name in files[1:]:
        assert 'Baseline 关闭思考，Agent 不调这一项' in (ROOT / name).read_text()


def test_rule_keys_are_not_read_by_config():
    tree = ast.parse((ROOT / 'backend/app/config.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {'get', 'getenv'} and node.args:
            assert not isinstance(node.args[0], ast.Constant) or node.args[0].value not in ENV_KEYS
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and isinstance(node.slice, ast.Constant):
            assert node.slice.value not in ENV_KEYS


@pytest.mark.parametrize('key', sorted(ENV_KEYS))
def test_rule_key_in_env_file_blocks_startup(key, tmp_path):
    from app.config import load_settings
    env_file = tmp_path / '.env'
    env_file.write_text(f'export {key} = off\n')
    with pytest.raises(ValueError, match='规则项已移到 rules.py，请从 .env 删除'):
        load_settings({key: 'override'}, env_file)
    env_file.unlink()
    settings = load_settings({key: 'ignored'}, env_file)
    assert (settings.baseline_thinking, settings.judge_thinking, settings.judge_samples) == ('off', 'off', 3)


def test_qc_p0_and_content_blockers_and_review_only_scores():
    from app.golden_v2 import QC_CONTRACT, qc_outcome
    assert QC_CONTRACT == 'golden-quality-p0-v2'
    for score, priority in [(84, 'P2'), (91, 'P1')]:
        assert qc_outcome({'score': score, 'priority': priority}) == {
            'passed': True, 'needs_review': True, 'threshold': 85}
    assert not qc_outcome({'score': 99, 'priority': 'P0'})['passed']
    assert not qc_outcome({'score': 99, 'priority': 'P2', 'ablation_valid': False})['passed']
    assert not qc_outcome({'score': 99, 'priority': 'P2', 'content_validation': {'safety_valid': False}})['passed']
    assert not qc_outcome({'score': 84, 'priority': 'P2', 'rule_version': 'golden-quality-85-v1'})['passed']
