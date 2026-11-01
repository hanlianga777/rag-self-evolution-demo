"""Task 007 speed sample; local resumable checkpoints, never formal evaluation rows."""
import csv
import json
import os
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.main import store, ai_service
from app.evaluation import EvaluationRunner
from app.evaluation_stage import perform_stage, correction_for, checkpoint_usage
from app.telemetry import cost_report
from app.providers import permanent_provider_error

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'backend/data/task007-speed.json'
CSV = ROOT / '指挥/报告/007-数据/速度小测.csv'
LOCK = threading.RLock()
STOP = threading.Event()
RUN = 'task007-speed'
SLOTS = ('Q13', 'Q17', 'Q25', 'Q35', 'Q36')
runner = EvaluationRunner(store, ai_service)
snapshot, items, config, judge = runner.baseline_inputs()
assert snapshot['id'] == 'GD-20261101151940'
selected = {i['raw']['coverage_slot']: i for i in items if i['raw'].get('coverage_slot') in SLOTS}
assert set(selected) == set(SLOTS)
state = json.loads(STATE.read_text()) if STATE.exists() else {
    'snapshot_id': snapshot['id'], 'config': config, 'judge': judge,
    'started_at': datetime.now(timezone.utc).isoformat(), 'samples': {}}
assert state['snapshot_id'] == snapshot['id'] and state['config'] == config and state['judge'] == judge


def save(*args, **kwargs):
    with LOCK:
        temporary = STATE.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, ensure_ascii=False))
        temporary.replace(STATE)
        CSV.parent.mkdir(parents=True, exist_ok=True)
        with CSV.open('w', encoding='utf-8-sig', newline='') as output:
            fields = ['题号', '档位', '总耗时（秒）', '首字时间（秒）', '检索耗时', '回答耗时', '判分结果（对/错）', '未通过的要点', '输入token', '输出token', '费用估算', '技术状态']
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for effort in ('off', 'low', 'high', 'max'):
                for slot in SLOTS:
                    cp = state['samples'].get(effort + ':' + slot, {})
                    if not cp: continue
                    execution = cp.get('execution', {})
                    case = cp.get('scored_result', {})
                    events = checkpoint_usage(cp)
                    deepseek = [u for u in events if u.get('provider') == 'DeepSeek']
                    cost = cost_report(ai_service.model, deepseek)
                    def tokens(name):
                        values = [u.get(name) for u in deepseek]
                        return sum(values) if values and all(type(v) is int for v in values) else '未知'
                    seconds = lambda value: round(value / 1000, 3) if isinstance(value, (int, float)) else '未知'
                    stages = {s['stage_name']: s['duration_ms'] for s in execution.get('stages', [])}
                    findings = [c.get('requirement', c.get('reason', str(c))) for c in case.get('judge_result', {}).get('checks', []) if c.get('met') is False or c.get('passed') is False or c.get('pass') is False]
                    findings.extend(c.get('reason', c.get('description', str(c))) for c in case.get('judge_result', {}).get('issues', []))
                    if not case.get('passed', True) and not findings:
                        findings = [case.get('judge_result', {}).get('reason', case.get('judge_result', {}).get('summary', '详见原始判分'))]
                    writer.writerow(dict(zip(fields, [slot, effort, seconds(execution.get('latency_ms')), seconds(execution.get('ttft_ms')),
                        seconds(stages.get('retrieval')), seconds(stages.get('generation')),
                        ('对' if case['passed'] else '错') if 'passed' in case else '未知',
                        json.dumps(findings, ensure_ascii=False) if findings else cp.get('error', ''),
                        tokens('prompt_tokens'), tokens('completion_tokens'),
                        cost['amount'] if cost['amount'] is not None else '未知',
                        '完成' if case else '技术失败' if cp.get('error') else '进行中'])))


def run_effort(effort):
    for final_pass in range(2):
        for slot in SLOTS:
            if STOP.is_set(): return
            key = effort + ':' + slot
            with LOCK:
                cp = state['samples'].setdefault(key, {'attempts': []})
            if 'scored_result' in cp or final_pass and (not cp.get('error') or cp.get('final_retry_done')):
                continue
            if cp.get('permanent_error'): continue
            if final_pass:
                cp['final_retry_done'] = True
                cp.pop('phase_windows', None)
            stage_run = RUN + (':final-retry' if final_pass else '') + ':' + key
            item = selected[slot]
            try:
                if 'execution' not in cp:
                    cp['execution'] = perform_stage(cp, 'generation', lambda: ai_service.answer(item['question'], {**config, 'generation_thinking': effort}), stage_run, automatic=False, check_stop=lambda: None, on_state=save)
                    save()
                if 'scored_result' not in cp:
                    cp['scored_result'] = perform_stage(cp, 'judge', lambda: runner.score_execution(item, cp['execution'], judge_correction=correction_for(cp, stage_run)), stage_run, automatic=False, check_stop=lambda: None, on_state=save)
                cp.pop('error', None)
                print(key, 'PASS' if cp['scored_result']['passed'] else 'FAIL', cp['execution']['latency_ms'], flush=True)
            except Exception as error:
                cp['error'] = type(error).__name__ + ': ' + str(error)
                cp['permanent_error'] = permanent_provider_error(error)
                if cp['permanent_error']:
                    STOP.set()
                    state['stopped_reason'] = cp['error']
                print(key, type(error).__name__, flush=True)
            finally:
                save()


if __name__ == '__main__':
    assert not [r for r in store.evaluation_runs() if r['status'] in ('queued', 'running')]
    save()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run_effort, ('off', 'low', 'high', 'max')))
    state['finished_at'] = datetime.now(timezone.utc).isoformat()
    save()
    print('速度小测完成', flush=True)
