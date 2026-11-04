"""Explicit, persistent per-task USD cap; ordinary accounting stays unchanged."""
import fcntl
import json
import math
import time
from contextlib import contextmanager
from pathlib import Path


def policy_cost(directory):
    from .telemetry import cost_report
    calls = [c for p in Path(directory).glob('*.ledger.json') for c in json.loads(p.read_text())['calls']]
    total = known = 0.
    unknown = 0
    for call in calls:
        if call['provider'] != 'DeepSeek': continue
        amount = cost_report(call['model'], [call.get('usage', {})]).get('amount')
        if amount is not None:
            total += amount; known += amount
        else:
            unknown += call['status'] != 'reserved'
            bound = call.get('reservation_usd')
            if type(bound) not in (int, float) or not math.isfinite(bound) or bound < 0: raise RuntimeError('Unknown DeepSeek charge without bound')
            total += bound
    return {'deepseek_calls': sum(c['provider'] == 'DeepSeek' for c in calls),
            'alibaba_calls': sum(c['provider'] == 'Alibaba' for c in calls),
            'known_usd': known, 'budget_used_upper_usd': total, 'unknown': unknown}


def guarded_begin(run, provider, model, payload):
    policy = run.request_policy
    if policy.get('kind') != 'off_peak_usd_cap_v1': raise RuntimeError('Unknown paid request policy')
    if provider != 'DeepSeek': return run._begin(provider, model, payload)
    from .governance import GovernanceStore
    from .paid_schedule import schedule_status
    from .telemetry import price_config
    store = GovernanceStore(Path(policy['database_path']), migrate=False)
    while True:
        status = schedule_status(store)
        if status['off_peak_only'] is not True: raise RuntimeError('Off-peak setting must remain enabled')
        if status['peak_now'] is not False:
            time.sleep(1)
            continue
        # One lock covers all ledgers in the task, including recovery processes.
        with (Path(policy['ledger_directory']) / 'budget.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            status = schedule_status(store)
            if status['off_peak_only'] is not True: raise RuntimeError('Off-peak setting must remain enabled')
            if status['peak_now'] is not False: continue
            rates = price_config()['periods']['off_peak']
            bound = ((len(json.dumps(payload).encode()) + 1024) * rates['input_per_million']
                     + payload['max_tokens'] * rates['output_per_million']) / 1_000_000
            if policy_cost(policy['ledger_directory'])['budget_used_upper_usd'] + bound > policy['budget_usd']:
                raise RuntimeError('Paid task USD limit reached')
            call = run._begin(provider, model, payload)
            call.update(reservation_usd=bound, price_check=status)
            run.save()
            return call


def current_binding():
    from .paid_run import current_paid_run
    run = current_paid_run()
    return {'ledger_path': str(run.path), 'ledger_identity': run.identity} if run and getattr(run, 'request_policy', None) else None


@contextmanager
def restore_paid_context(store, binding):
    from .paid_run import PaidRun, current_paid_run, controlled_run, accounting_only
    if current_paid_run() is not None:
        yield
        return
    run = PaidRun.load_accounting(binding['ledger_path'], lambda: binding['ledger_identity'])
    if (run.identity != binding['ledger_identity'] or not run.request_policy
            or Path(run.request_policy['database_path']).resolve() != Path(store.database_path).resolve()):
        raise ValueError('Recovered paid task binding changed')
    with controlled_run(run), accounting_only(): yield
