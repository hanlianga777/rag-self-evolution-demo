"""Compare the Agent prompt, Pipeline endpoint and outgoing payloads without sending them."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[1]
REPORT = BACKEND.parent / '指挥/报告/101-端到端核对.md'
sys.path.insert(0, str(BACKEND))

THINKING_TEXT = 'Baseline 关闭思考，Agent 不调这一项'
STABILITY_TEXT = '温度 0 下判定稳定，回答文字仍可能不同'
STALE_TEXT = re.compile(r'Baseline\s*(?:使用|用|采用|设为|为|是)\s*(?:Thinking\s*)?(?:Max|High)'
                        r'|降档补位|保证[^。；，\n]{0,24}一致', re.IGNORECASE)


def collect():
    from fastapi.testclient import TestClient
    from app import main, rules
    from app.ai_service import AiService
    from app.config import Settings
    from app.optimization import build_agent_prompt
    from app.paid_run import provider_task
    from app.providers import DeepSeekProvider
    from app.rubric_judge import RUBRIC_VERSION

    # TestClient is used without lifespan, so no background workers start.
    response = TestClient(main.app).get('/api/pipeline')
    response.raise_for_status()
    api = response.json()

    baseline = {'id': 'offline-baseline', 'config': {**rules.BASELINE, 'retrieval_max_tokens': rules.BASELINE_CONTEXT_LIMIT}}
    system, prompt = build_agent_prompt([], {key: value for key, value in baseline['config'].items()
                                            if key in rules.PIPELINE_VALUES}, [], [], list('ABC'))
    provider = DeepSeekProvider(Settings('offline-placeholder', 'https://offline.invalid', 'offline-model'))
    runtime = AiService(None, main.corpus, provider, False)
    payloads = {}

    class Captured(Exception):
        pass

    def intercept(request, stream):
        payloads[task] = json.loads(request.data)
        raise Captured

    evidence = [{'chunk_id': 'offline-chunk', 'content': '离线样本文档。'}]
    calls = {
        'Baseline': lambda: runtime._generate('离线问题', {**baseline['config'], 'run_target': 'baseline'},
                                              time.perf_counter(), evidence, {'generation_allowed': True}, [], {}, [], None),
        'Sandbox': lambda: runtime._generate('离线问题', {**baseline['config'], 'run_target': 'sandbox_candidate'},
                                             time.perf_counter(), evidence, {'generation_allowed': True}, [], {}, [], None),
        'Judge': lambda: provider.judge('离线问题', '离线参考', '离线回答',
                                        context={'contract_version': RUBRIC_VERSION, 'category': 'positive', 'final_texts': []}),
        'Agent': lambda: provider.complete(system, json.dumps(prompt, ensure_ascii=False), json_mode=True),
    }
    with patch.object(provider, '_complete_request', side_effect=intercept):
        for task, call in calls.items():
            try:
                with provider_task('answer' if task in ('Baseline', 'Sandbox') else task.lower()):
                    call()
            except Captured:
                continue
            raise RuntimeError(f'{task} 没有到达预发送拦截点')
    return system, prompt, api, payloads


def compare(system, prompt, api, payloads):
    from app import rules

    agent_allowed = prompt['allowed_parameter_values']
    api_allowed = api['search_space']
    body = json.loads(payloads['Agent']['messages'][1]['content'])
    agent_config = prompt['goal']['baseline_configuration']
    api_config = api['baseline_defaults']
    thinking_description = api_allowed['generation_thinking']['description']
    audit_tasks = ('Baseline', 'Sandbox', 'Judge')
    settings = {task: {key: payloads[task].get(key) for key in ('thinking', 'reasoning_effort', 'temperature')}
                for task in payloads}
    allowed = {key: list(values) for key, values in rules.PIPELINE_VALUES.items()}
    tunable = {key: allowed[key] for key in rules.AGENT['tunable']}
    agent_values = {key: entry['allowed'] for key, entry in agent_allowed.items()}
    api_values = {key: entry['allowed'] for key, entry in api_allowed.items()}
    drift = {source: STALE_TEXT.findall(value) for source, value in {
        'Agent system': system, 'Agent 配置': json.dumps(prompt, ensure_ascii=False),
        '前端参数接口': json.dumps(api_allowed, ensure_ascii=False),
        'Provider 消息': json.dumps([payload['messages'] for payload in payloads.values()], ensure_ascii=False),
    }.items()}
    return [
        ('思考档关闭', THINKING_TEXT in system and thinking_description == THINKING_TEXT
         and agent_config['generation_thinking'] == api_config['generation_thinking'] == rules.BASELINE['generation_thinking'] == 'off'
         and body['goal']['baseline_configuration']['generation_thinking'] == 'off'
         and payloads['Agent']['messages'][0]['content'] == system
         and all(settings[task]['thinking'] == {'type': 'disabled'} and settings[task]['reasoning_effort'] is None for task in audit_tasks),
         {'Agent 原文': excerpt(system, THINKING_TEXT), '接口原文': thinking_description,
          'Agent 配置': agent_config['generation_thinking'], '接口配置': api_config['generation_thinking'],
          'Provider': settings}),
        ('温度为 0', STABILITY_TEXT in system and api['fixed_parameters']['temperature'] == rules.BASELINE['temperature'] == rules.JUDGE['temperature'] == 0
         and all(type(settings[task]['temperature']) in (int, float) and settings[task]['temperature'] == 0 for task in audit_tasks),
         {'Agent 原文': excerpt(system, STABILITY_TEXT), '接口 fixed_parameters': api['fixed_parameters'],
          'Provider temperature': {task: settings[task]['temperature'] for task in audit_tasks}}),
        ('搜索空间一致', rules.canonical_hash(agent_values) == rules.canonical_hash(tunable)
         and rules.canonical_hash(api_values) == rules.canonical_hash(allowed)
         and rules.canonical_hash(body.get('allowed_parameter_values')) == rules.canonical_hash(agent_allowed),
         {'rules.py Agent 白名单': tunable, 'Agent 请求取值': agent_values, '接口取值': api_values}),
        ('旧说法扫描', not any(drift.values()),
         {'命中原文': drift, 'Agent 当前原文': excerpt(system, STABILITY_TEXT), '接口当前原文': thinking_description}),
    ]


def excerpt(text, phrase):
    start = text.find(phrase)
    return text[start:start + len(phrase)] if start >= 0 else text[:160]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只输出检查结果，不写报告文件')
    args = parser.parse_args()
    with TemporaryDirectory(prefix='rules-e2e-') as directory:
        root = Path(directory)
        environment = {f'RAG_DEMO_{key}': str(root / name) for key, name in {
            'DB_PATH': 'demo.db', 'ENV_PATH': 'absent.env', 'INDEX_DIR': 'index',
            'DOCUMENTS_DIR': 'documents', 'UPLOADS_DIR': 'uploads',
        }.items()}
        environment.update(RAG_FORCE_MOCK='1', RAG_SAFE_START='0', DEEPSEEK_API_KEY='')
        with patch.dict(os.environ, environment), patch('urllib.request.urlopen', side_effect=AssertionError('离线检查禁止发送请求')):
            checks = compare(*collect())

    lines = ['# 101 规则端到端核对', '',
             '使用离线样本构造实际 Agent prompt，读取 `GET /api/pipeline`，在 DeepSeek `_complete_request` 入口截获请求体。实际发送 0 次。', '',
             '思考档与温度验收针对 Baseline、Sandbox 的回答生成和 Judge。Agent 自身提出方案的请求单独列出。', '']
    for name, passed, evidence in checks:
        lines.extend([f'## {name} · {"一致" if passed else "不一致"}', '', '```json',
                      json.dumps(evidence, ensure_ascii=False, indent=2), '```', ''])
    report = '\n'.join(lines)
    if not args.check:
        REPORT.write_text(report, encoding='utf-8')
    print(report)
    return 0 if all(passed for _, passed, _ in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
