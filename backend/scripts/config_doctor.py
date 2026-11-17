"""付费运行前的配置体检：把"实际生效的配置"和《规则总表-机读.json》逐项对照，不一致就拒绝开跑。不调模型、不改任何东西。

为什么要有它（2026-11-16 复盘）：规则总表写 Baseline = Max，但用户 Mac 上 .env 里一直是 BASELINE_THINKING=off，
直到跑之前人工翻配置才发现；规则散在 规则总表 / 任务单 / HANDOFF / SPEC / .env / 代码常量 六处，靠人记不住。
现在规则里影响运行的那几条有一份机读版本，每次花钱前自动对一遍。

PYTHONPATH=backend python3 backend/scripts/config_doctor.py [--rules 指挥/规则总表-机读.json]
退出码：0 = 全部一致；1 = 有不一致（逐项打印"规则值 / 实际值 / 来源"）。
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def check(rules, settings, pipeline, gates, search_space, min_bad_cases):
    problems = []

    def diff(name, expected, actual, source):
        if expected != actual:
            problems.append({'项目': name, '规则值': expected, '实际值': actual, '来源': source})

    for key, expected in rules['settings'].items():
        diff(f'settings.{key}', expected, getattr(settings, key), '.env / 环境变量（backend/app/config.py 默认值）')
    for key, expected in rules['baseline_pipeline'].items():
        diff(f'baseline_pipeline.{key}', expected, pipeline.get(key), 'backend/app/policy.py DEFAULT_PIPELINE_CONFIG')
    diff('baseline_pipeline.generation_thinking 与 settings.baseline_thinking 一致', True,
         pipeline.get('generation_thinking') == settings.baseline_thinking, 'policy.py 与 .env')
    actual_gates = {g['metric']: g['threshold'] for g in gates}
    for key, expected in rules['gates'].items():
        diff(f'gates.{key}', expected, actual_gates.get(key), 'backend/app/policy.py GATE_DEFINITIONS')
    diff('gates 项数', len(rules['gates']), len(actual_gates), 'backend/app/policy.py GATE_DEFINITIONS')
    diff('agent_search_space_keys', sorted(rules['agent_search_space_keys']), sorted(search_space), 'backend/app/policy.py ALLOWED_SEARCH_SPACE')
    diff('launch_check.min_baseline_bad_cases', rules['launch_check']['min_baseline_bad_cases'], min_bad_cases, 'backend/scripts/arm_agent_chain.py')
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--rules', type=Path, default=ROOT / '指挥/规则总表-机读.json')
    args = parser.parse_args(argv)
    from app.config import load_settings
    from app.policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, GATE_DEFINITIONS
    spec = importlib.util.spec_from_file_location('arm_agent_chain', Path(__file__).resolve().parent / 'arm_agent_chain.py')
    arm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arm)
    rules = json.loads(args.rules.read_text(encoding='utf-8'))
    problems = check(rules, load_settings(), DEFAULT_PIPELINE_CONFIG, GATE_DEFINITIONS, ALLOWED_SEARCH_SPACE, arm.MIN_BASELINE_BAD_CASES)
    return {'rules_version': rules['版本'], 'ok': not problems, 'problems': problems}


if __name__ == '__main__':
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str), flush=True)
    sys.exit(0 if result['ok'] else 1)
