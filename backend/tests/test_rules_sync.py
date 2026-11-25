"""Keep the live rule values and their explanations aligned with the rulebook."""
import ast
import hashlib
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENV_KEYS = {'BASELINE_THINKING', 'JUDGE_THINKING', 'JUDGE_SAMPLES'}
SOURCE_DIRS = ('backend/app', 'backend/scripts', 'backend/tests', 'backend/config',
               'frontend/src', 'frontend/scripts', 'scripts', 'tools', '指挥/自动值班', '.github/workflows')
SOURCE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.mjs', '.sh', '.command', '.json', '.yml', '.yaml', '.txt'}
FIXTURE_PATHS = {
    'frontend/src/ui/PageSamples.tsx',
    'frontend/src/ui/evolution/fixture.ts',
}

# Match policy literals in context: a percentile threshold in a metric
# definition is different from a measured latency or an HTTP timeout.
RULE_FIELDS = (
    r'max_changed_parameters|d_max_changed_parameters|candidates_per_round|min_bad_cases|min_baseline_bad_cases|'
    r'judge_samples|judge_temperature|judge_thinking|baseline_thinking|candidate_qualification_version|rules_version|'
    r'max_evals|(?:evaluation_|agent_)?budget|max_new_(?:critical|failures)|min_fixed|'
    r'positive_avg|ablation_avg|safety_refusal|safety_critical_accuracy_threshold|prompt_injection_threshold|'
    r'p(?:50|99)_seconds|max_rounds|min_qualified_for_fusion|single_winner_after_round|winner_extra_parameters'
)
LITERAL = r'''(?:-?(?:\d+(?:\.\d+)?|\.\d+)(?![\d.])|["'][^"'\n]+["']|\[(?:\s*\d+\s*,?)+\])'''
FIELD_ASSIGNMENT = rf'^\s*(?:export\s+)?(?:const\s+)?(?:{RULE_FIELDS})\s*(?::\s*\w+\s*)?=\s*'
TEST_FIELD_LITERAL = re.compile(FIELD_ASSIGNMENT + LITERAL, re.I | re.M)
FIELD_LITERAL = re.compile(
    rf'''(?im)(?:{FIELD_ASSIGNMENT}|(?:["'](?:{RULE_FIELDS})["']|\b(?:{RULE_FIELDS}))\s*:\s*){LITERAL}''')
BASELINE_FIELDS = (
    r'candidate_k|top_k|min_score|hybrid_search|hybrid_alpha|rerank|query_rewrite|multi_query|hyde|'
    r'query_decompose|prompt_strategy|generation_thinking|retrieval_max_tokens|temperature'
)
RUNTIME_LITERAL = re.compile(
    rf'''(?imx)\.get\(\s*["'](?:{BASELINE_FIELDS})["']\s*,\s*(?:{LITERAL}|true|false)\s*\)
    |\b(?:baseline|baseline_defaults|baseline_config|draftDefaults|default_pipeline_config|friend_baseline_config)\s*=\s*\{{\s*
        ["']?(?:{BASELINE_FIELDS})["']?\s*:\s*(?:{LITERAL}|true|false)
    |(?:["']threshold["']|\bthreshold)\s*[:=]\s*(?:95|25|60|80|75|70|65)(?![\d.])
    |(?:\bP50\s*(?:<=|≤)\s*25|\bP99\s*(?:<=|≤)\s*60|(?:安全拒答率|提示注入抵抗率)\s*(?:>=|≥)\s*95)
    |(?<![\d.])(?:80\s*[/,，]\s*80\s*[/,，]\s*75|70\s*[/,，]\s*75\s*[/,，]\s*65)(?![\d.])
    |(?:prompt_strategy|Prompt\ Strategy)[^\n]{{0,60}}(?:Strict[/／、,， ]+Looser|Strict[（(：][^\n]{{0,40}}Looser)
    |每题\s*(?:固定)?判\s*[\d一二两三四五]+\s*次
    |最多\s*(?:只)?改\s*[\d一二两三四五]+\s*个?\s*参数
    |(?:每轮\s*[\d三]+\s*(?:套|个方案)|预算\s*[:：=]?\s*\d+\s*(?:次|个))
    |Baseline\s*(?:关闭思考|(?:用|采用|设为)\s*(?:Thinking\s*)?(?:Max|High))
    |(?:新增上限|普通上限|严重上限)\s*[\d零一]+
    |至少\s*修好\s*[\d一]+\s*道
    |\b\d+\s*项\s*(?:Hard\ Gate|门槛)
    |规则版本[：:]?\s*`?2026-11-20b
    |Gate\s*3[^\n]{{0,28}}必须[^\n]{{0,12}}亲自下令
    |["']用户睡前授权代发布["']
    ''')


def literal_rule_hits(source, pattern):
    return [(source.count('\n', 0, match.start()) + 1, match.group().strip())
            for match in pattern.finditer(source)]


def test_no_embedded_rule_values():
    hits = []
    files = list(ROOT.glob('*.sh')) + list(ROOT.glob('*.command'))
    for directory in SOURCE_DIRS:
        files.extend((ROOT / directory).rglob('*'))
    for path in sorted(files):
        name = path.relative_to(ROOT).as_posix()
        fixture = (name in FIXTURE_PATHS
                   or name.startswith('backend/tests/') and ('fixtures' in path.parts or 'fixture' in path.stem)
                   or name.startswith('frontend/src/') and path.stem.endswith('-test-fixture'))
        if (path.suffix not in SOURCE_SUFFIXES or not path.is_file()
                or name == 'backend/app/rules.py' or fixture):
            continue
        source = path.read_text(encoding='utf-8')
        # Tests can express independent examples and expectations. Guard
        # policy defaults declared by tests as well as production literals.
        is_test = path.stem.startswith('test_') or '.test.' in path.name
        if is_test:
            violations = literal_rule_hits(source, TEST_FIELD_LITERAL)
        else:
            violations = literal_rule_hits(source, FIELD_LITERAL) + literal_rule_hits(source, RUNTIME_LITERAL)
        hits.extend(f'{name}:{line}: {value}' for line, value in violations)
    assert not hits, '\n' + '\n'.join(hits)


@pytest.mark.parametrize('source', [
    'limits = {max_changed_parameters: 7}',
    "limits = {'d_max_changed_parameters': 3}",
    'export const candidates_per_round = 3',
    'MIN_BASELINE_BAD_CASES = 5',
    'MAX_EVALS = 12',
    'const gate = {metric: "latency_p99_seconds", threshold: 60}',
    'gate_copy = "正向题过线 80/80/75，消融题 70/75/65"',
    'RULES_VERSION = "2026-11-20b"',
    'JUDGE_SAMPLES = 3',
    'draftDefaults = {generation_thinking: "off"}',
    'prompt_strategy 可选 Strict/Looser/Safe',
    'Gate 3 仍必须等用户亲自下令',
    '每个方案最多改 2 个参数',
])
def test_guard_detects_reintroduced_policy_literals(source):
    assert literal_rule_hits(source, FIELD_LITERAL) or literal_rule_hits(source, RUNTIME_LITERAL)


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
    assert rules.RULES_VERSION == CANDIDATE_QUALIFICATION_VERSION
    assert rules.AGENT['candidates_per_round'] == len(rules.AGENT['candidate_labels'])
    assert all(FRIEND_BASELINE_CONFIG[key] == value for key, value in rules.BASELINE.items())
    assert set(ALLOWED_SEARCH_SPACE) == set(rules.AGENT['tunable'])
    assert set(rules.AGENT['thinking_values']) < set(ALLOWED_SEARCH_SPACE['generation_thinking'])
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


def test_109b_keeps_completed_strict_baseline_usable_with_saved_fingerprints():
    from app.evaluation_snapshot import require_resume_snapshot

    saved = {
        'generation_prompt_version': 'generation-vnext-4',
        'run_snapshot': {
            'rules_hash': 'f0d368403ec9',
            'search_space_version': '48ce7c816182ef9701d14ba944f35b2f658c84128f97b5f876906e3e6e9dbc3e',
            'pipeline_config': {'prompt_strategy': 'Strict'},
            'prompt_version': {
                'Strict': 'a4c1510da62a9ec7525d4c3b453704a4db50cc31ce517b48c40a40a565bad6ae',
                'Looser': '3bd2349eff775f866e8f2e1729b740dbaf11fa739a1f4e46b42b43454207b83b',
                'Safe': '6f3ab5375dbbd8029a05f91f3f80cbba2a61aa8fdc22469a1b83b9d80864b35e',
                'judge': 'fdcc5e8d3ea89bdb24852b918325e24ef32267956f87a2a89196892961d739f6',
                'agent_system': '3a6d515d2a3b78f0acf3cf020436468d80f665f411b3f40e8824b505c014172a',
            },
        },
    }
    require_resume_snapshot(saved, for_candidate_baseline=True)
    with pytest.raises(ValueError, match='rules_hash.*prompt_version.agent_system'):
        require_resume_snapshot(saved)
    for name in ('Strict', 'judge'):
        old_hash = saved['run_snapshot']['prompt_version'][name]
        saved['run_snapshot']['prompt_version'][name] = 'changed'
        with pytest.raises(ValueError, match=f'prompt_version.{name}'):
            require_resume_snapshot(saved, for_candidate_baseline=True)
        saved['run_snapshot']['prompt_version'][name] = old_hash


def test_109g_keeps_the_previous_strict_baseline_usable_without_allowing_resume():
    from app.evaluation_snapshot import require_resume_snapshot, run_snapshot
    from app.rules import BASELINE

    snapshot = run_snapshot({'id': 'frozen'}, {'prompt_strategy': BASELINE['prompt_strategy']}, {})
    snapshot.update(rules_version='2026-11-20b', rules_hash='a1b4d0991ca6')
    snapshot['prompt_version']['agent_system'] = '02b20fea1fdb4a999d785307ff26a2fc40c0c1c70d5d8ca893e1c315f7e0166e'
    saved = {'run_snapshot': snapshot}
    require_resume_snapshot(saved, for_candidate_baseline=True)
    with pytest.raises(ValueError, match='prompt_version.agent_system'):
        require_resume_snapshot(saved)
    snapshot['prompt_version']['judge'] = 'changed'
    with pytest.raises(ValueError, match='prompt_version.judge'):
        require_resume_snapshot(saved, for_candidate_baseline=True)


def test_current_explanations():
    from app import rules
    from app.ai_service import PROMPT_STRATEGIES
    from app.policy import search_space_contract

    space = search_space_contract()
    assert rules.BASELINE['generation_thinking'] in space['generation_thinking']['description']
    assert set(PROMPT_STRATEGIES) == set(space['prompt_strategy']['allowed'])
    for key, allowed in rules.PIPELINE_VALUES.items():
        assert [option['value'] for option in space[key]['options']] == list(allowed)


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
    from app import rules
    env_file = tmp_path / '.env'
    env_file.write_text(f'export {key} = off\n')
    with pytest.raises(ValueError, match='规则项已移到 rules.py，请从 .env 删除'):
        load_settings({key: 'override'}, env_file)
    env_file.unlink()
    settings = load_settings({key: 'ignored'}, env_file)
    assert settings.baseline_thinking == rules.BASELINE['generation_thinking']
    assert (settings.judge_thinking, settings.judge_samples) == (rules.JUDGE['thinking'], rules.JUDGE['samples'])


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


def test_agent_prompt_uses_current_qualification_and_parameter_contract():
    from app import rules
    from app.optimization import ROUND_LABELS, build_agent_prompt
    from app.policy import DEFAULT_PIPELINE_CONFIG, GATE_DEFINITIONS

    system, prompt = build_agent_prompt([], DEFAULT_PIPELINE_CONFIG, [], [], ROUND_LABELS,
        retrieval_preview={'configs': []}, round_policy={'mode': 'full_rounds'}, causal_evidence=True)
    assert 'qualification_rules' in prompt
    assert prompt['qualification_rules'] == rules.RULES['qualification']
    assert prompt['qualification_rules']['version'] == rules.RULES_VERSION
    assert prompt['round_contract']['max_changed_parameters'] == rules.AGENT['max_changed_parameters']
    assert {key: row['allowed'] for key, row in prompt['allowed_parameter_values'].items()} == {
        key: rules.AGENT['thinking_values'] if key == 'generation_thinking' else list(rules.PIPELINE_VALUES[key])
        for key in rules.AGENT['tunable']}
    assert f"{len(GATE_DEFINITIONS)} 项门槛" in system
    assert '普通新增只用于' not in system
    assert f"至少修好 {prompt['qualification_rules']['min_fixed']} 道" in system


def test_current_qualification_counts_include_ordinary_regressions():
    from app import rules
    from app.policy import qualify_candidate

    for new, fixed, qualified in [(['Q22'], ['Q01', 'Q02'], False), ([], [], False), ([], ['Q01'], True)]:
        regression = {'passed': True, 'comparison_complete': True,
                      'all_fixed_question_ids': fixed, 'new_regression_question_ids': new,
                      'new_critical_failures': 0, 'severe_risk_question_ids': []}
        result = qualify_candidate({'passed': True}, regression, len(fixed), 5, 5, rule_version=rules.RULES_VERSION)
        assert result['qualified'] is qualified


def test_gate3_saves_audit_without_dual_review_and_keeps_hard_gates(tmp_path, monkeypatch, legacy_launch):
    from app import governance, rules
    from app.policy import qualify_candidate
    import identity_fixture

    monkeypatch.setattr(identity_fixture, 'current_manifest', lambda: {'sources': []})
    monkeypatch.setattr(governance, 'current_manifest', lambda: {'sources': []})
    store = governance.GovernanceStore(tmp_path / 'gate3.db')
    baseline_id = identity_fixture.completed_baseline(store)
    baseline = store.evaluation_run(baseline_id)
    experiment = store.create_experiment(baseline_id)
    label = rules.AGENT['candidate_labels'][0]
    config = {**baseline['config'], 'run_target': 'sandbox_candidate'}
    store.save_candidate(experiment, label, config, {'candidate_label': label, 'round': 1})
    run_id = store.create_evaluation_run(json.loads(baseline['dataset_snapshot_json']), config, baseline['judge'])
    store.finish_evaluation_run(run_id, 'completed', {'gates': {'passed': True}})
    candidate = f'{experiment}-{label}'
    regression = {'passed': True, 'comparison_complete': True,
                  'all_fixed_question_ids': ['Q1'], 'new_regression_question_ids': [], 'severe_risk_question_ids': []}
    qualification = qualify_candidate({'passed': True}, regression, 1, 1, 0, rule_version=rules.RULES_VERSION)
    result = {'evaluation_run_id': run_id, 'evaluation_identity': baseline['judge']['evaluation_identity'],
              'gates': {'passed': True}, 'regression': regression, 'qualification': qualification,
              'release_qualification': qualification}
    store.finish_candidate(candidate, 'evaluated', result)
    with store.connection() as db:
        db.execute('INSERT OR REPLACE INTO recommendations VALUES (?, ?, ?, ?, ?)',
                   (experiment, candidate, 'Recommended',
                    json.dumps({'status': 'Recommended', 'recommended_candidate': candidate}), 'fixture'))

    store.finish_candidate(candidate, 'evaluated', {**result, 'gates': {'passed': False}})
    with pytest.raises(ValueError, match='门槛'):
        store.publish_candidate(candidate, 'local_user')
    assert store.latest_approval('human_release', candidate) is None

    store.finish_candidate(candidate, 'evaluated', result)
    for actor in ('Codex', '总指挥'):
        with pytest.raises(ValueError, match='发布须由用户'):
            store.publish_candidate(candidate, actor)
        assert store.latest_approval('human_release', candidate) is None
    released = store.publish_candidate(candidate, 'local_user')
    audit = released['snapshot']['human_release']
    assert {key: audit[key] for key in ('authorizer', 'executed_by', 'review_method')} == {
        'authorizer': '用户', 'executed_by': 'local_user', 'review_method': '用户明确批准发布',
    }
    assert 'review_evidence' not in audit


@pytest.mark.parametrize('table', [
    '项目 | 每季度 | 每两年\n更换密封圈 |  | x\n检查外壳 | x | ',
    '组件 | 型号 A | 型号 B\n过滤器 | G1 | G2\n夹具 | J1 | J3',
], ids=['different-periods', 'different-models'])
def test_tablecheck_request_has_general_column_rule(table):
    from app.ai_service import GENERATION_PROMPT_VERSION, generation_context, generation_system_prompt
    from app.rules import STRICT, TABLE_CHECK

    strict = generation_system_prompt(GENERATION_PROMPT_VERSION, STRICT)
    prompt = generation_system_prompt(GENERATION_PROMPT_VERSION, TABLE_CHECK)
    context = generation_context([{'content': table}], numbered=True)
    assert hashlib.sha256(strict.encode()).hexdigest() == 'a4c1510da62a9ec7525d4c3b453704a4db50cc31ce517b48c40a40a565bad6ae'
    assert "按实际表头列名和单元格内容归类" in prompt
    assert "不得把不同周期、条件或型号对应的项目混在一起" in prompt
    assert '36个月' not in prompt and '12个月' not in prompt
    assert table in context


def test_109i_tablecheck_update_keeps_strict_baseline_usable_for_new_candidates():
    from app.evaluation_snapshot import require_resume_snapshot, run_snapshot
    from app.rules import STRICT, TABLE_CHECK

    saved = run_snapshot({'id': 'frozen'}, {'prompt_strategy': STRICT}, {})
    assert TABLE_CHECK not in saved['prompt_version']
    saved.update(rules_version='2026-11-20b', rules_hash='bb96bee3ca3b')
    saved['prompt_version'][TABLE_CHECK] = '2b50bbbc1784401081198006d005527ac0fe7ca721adcdcf04f26fd5b2e9564b'
    require_resume_snapshot({'run_snapshot': saved}, for_candidate_baseline=True)
    with pytest.raises(ValueError, match='rules_hash'):
        require_resume_snapshot({'run_snapshot': saved})
    saved['pipeline_config']['prompt_strategy'] = TABLE_CHECK
    with pytest.raises(ValueError, match='rules_hash'):
        require_resume_snapshot({'run_snapshot': saved}, for_candidate_baseline=True)
