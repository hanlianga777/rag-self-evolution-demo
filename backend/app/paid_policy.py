"""Explicit per-task USD cap (None disables it), retaining request accounting."""
import fcntl
import json
import math
import time
from contextlib import contextmanager
from pathlib import Path

E5_POLICY = 'e5_external_usd_cap'  # Persisted 120b policy name.
E6_TASK = '124c'
E6_BASELINE = 'EVAL-20261126212249302614'
E7_TASK = '125b'
E7_PRODUCTION = 'production-20261126232343'
E5_EXCHANGE = 6.7120
EXPERIMENT_ACCOUNTING = 'experiment_accounting_v1'
ALIBABA_RATES = {model: {'provider':'Alibaba', 'input':0.5, 'output':0, 'max_output':0, 'currency':'CNY'}
                 for model in ('text-embedding-v4', 'qwen3-rerank')}


def e6_accounting(run):
    return bool(run and isinstance(run.identity, dict) and run.identity.get('task') == E6_TASK)


def e7_accounting(run):
    return bool(run and isinstance(run.identity, dict) and run.identity.get('task') == E7_TASK)


def uses_judge_fallback(run):
    return e6_accounting(run) or e7_accounting(run)


def e5_cost(calls):
    from .providers import ProviderRequestError

    known = upper = 0.
    unknown = 0
    for call in calls:
        if call['status'] == 'rejected':
            continue
        estimate = call.get('estimated_cost')
        if call['status'] == 'ok' and estimate:
            amount = estimate['amount'] / (E5_EXCHANGE if estimate['currency'] == 'CNY' else 1)
            known += amount
        else:
            amount = call.get('reservation_usd')
            unknown += 1
        if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
            raise ProviderRequestError('费用账本缺少有效的美元费用上限')
        upper += amount
    return {'budget_used_upper_usd': upper, 'known_usd': known, 'unknown': unknown,
            'deepseek_calls': sum(c['provider'] == 'DeepSeek' for c in calls),
            'alibaba_calls': sum(c['provider'] == 'Alibaba' for c in calls)}


def policy_cost(directory):
    from .telemetry import cost_report
    calls = [c for p in Path(directory).glob('*.ledger.json') for c in json.loads(p.read_text())['calls']]
    total = known = 0.
    unknown = 0
    for call in calls:
        if call['provider'] != 'DeepSeek' or call['status']=='rejected': continue
        amount = cost_report(call['model'], [call.get('usage', {})]).get('amount') if call['status']=='ok' else None
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
    from .providers import ProviderRequestError, check_provider_stop
    policy = run.request_policy
    if policy.get('kind') == EXPERIMENT_ACCOUNTING:
        return run._begin(provider, model, payload)
    if policy.get('kind') == E5_POLICY:
        rate = run.prices.get(model, {})
        if rate.get('provider') != provider:
            raise ProviderRequestError('请求模型与 E5 授权账本不一致')
        repeated = max(0, len(payload.get('documents', []))-1)*len(str(payload.get('query', '')).encode())
        output = payload.get('max_tokens') if provider == 'DeepSeek' else 0
        if type(output) is not int or not 0 <= output <= rate['max_output']:
            raise ProviderRequestError('请求输出上限无效')
        reserve = ((len(json.dumps(payload,ensure_ascii=False).encode())+repeated+1024)*rate['input']
                   + output*rate['output'])/1_000_000
        if rate.get('currency') == 'CNY':
            reserve /= E5_EXCHANGE
        if e5_cost(run.calls)['budget_used_upper_usd']+reserve > policy['budget_usd']:
            raise ProviderRequestError('DeepSeek 与阿里云合计授权余额不足')
        return run._begin(provider, model, payload, reservation_usd=reserve,
                          e5_phase=getattr(run, 'phase', None))
    if policy.get('kind') not in {'off_peak_usd_cap_v1','scheduled_usd_cap_v1'}:
        raise ProviderRequestError('Unknown paid request policy')
    scheduled = policy['kind'] == 'scheduled_usd_cap_v1'
    if provider != 'DeepSeek': return run._begin(provider, model, payload)
    from .governance import GovernanceStore
    from .paid_schedule import schedule_status
    from .telemetry import price_config
    store = GovernanceStore(Path(policy['database_path']), migrate=False)
    while True:
        from .evaluation_stage import _request_checkpoint
        checkpoint=_request_checkpoint.get()
        check_provider_stop(checkpoint[4] if checkpoint else None)
        status = schedule_status(store)
        if not scheduled and status['off_peak_only'] is not True: raise RuntimeError('Off-peak setting must remain enabled')
        if (not scheduled or status['off_peak_only']) and status['peak_now'] is not False:
            time.sleep(1)
            continue
        # One lock covers all ledgers in the task, including recovery processes.
        with (Path(policy['ledger_directory']) / 'budget.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            status = schedule_status(store)
            if not scheduled and status['off_peak_only'] is not True: raise RuntimeError('Off-peak setting must remain enabled')
            if (not scheduled or status['off_peak_only']) and status['peak_now'] is not False: continue
            rates = price_config()['periods']['peak' if scheduled else 'off_peak']
            bound = ((len(json.dumps(payload).encode()) + 1024) * rates['input_per_million']
                     + payload['max_tokens'] * rates['output_per_million']) / 1_000_000
            if policy['budget_usd'] is not None and policy_cost(policy['ledger_directory'])['budget_used_upper_usd'] + bound > policy['budget_usd']:
                raise ProviderRequestError('Paid task USD limit reached')
            return run._begin(provider, model, payload, reservation_usd=bound, price_check=status)


def current_binding():
    from .paid_run import current_paid_run
    run = current_paid_run()
    return {'ledger_path': str(run.path), 'ledger_identity': run.identity} if run and getattr(run, 'request_policy', None) else None


def bind_experiment(store, experiment_id, binding):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        result = json.loads(row['result_json'])
        if result.get('paid_run') not in (None, binding):
            raise ValueError('实验已绑定另一份费用授权')
        result['paid_run'] = binding
        db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(result, ensure_ascii=False), experiment_id))


def _price_snapshot():
    from .telemetry import price_config

    prices = dict(ALIBABA_RATES)
    config = price_config()
    if config:
        periods = config.get('periods', {'fixed':config}).values()
        rate = {'provider':'DeepSeek', 'currency':config['currency'],
                'input':max(item['input_per_million'] for item in periods)*1_000_000/config['unit'],
                'output':max(item['output_per_million'] for item in periods)*1_000_000/config['unit'],
                'max_output':393216}
        prices.update(dict.fromkeys([config['model'], *config.get('aliases', [])], rate))
    return prices


def standalone_ledger(database_path):
    """Account for configured calls outside a named experiment without granting a cap."""
    from .paid_run import PaidRun

    database = Path(database_path).resolve()
    directory = database.parent / (database.name + '.provider-ledgers')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / 'standalone.ledger.json'
    identity = {'database_path':str(database), 'scope':'standalone'}
    with path.with_suffix('.init.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not path.exists():
            return PaidRun(path, prices=_price_snapshot(), identity=identity, identity_check=lambda:identity,
                           request_policy={'kind':EXPERIMENT_ACCOUNTING, 'database_path':str(database), 'budget_usd':None})
        return PaidRun.load_accounting(path, lambda:identity)


def experiment_binding(store, experiment_id, provider=None):
    """Adopt an existing authorization or create the experiment's uncapped ledger."""
    from .paid_run import PaidRun
    from .providers import DeepSeekProvider

    record = store.experiment(experiment_id, light=True)
    if not record:
        return None
    if binding := record['result'].get('paid_run'):
        return binding
    active = current_binding()
    if active is None and (not isinstance(provider, DeepSeekProvider) or not provider.settings.configured):
        return None
    database = Path(store.database_path).resolve()
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT result_json, baseline_run_id FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        result = json.loads(row['result_json'])
        if binding := result.get('paid_run'):
            return binding
        if active:
            identity = active['ledger_identity']
            if isinstance(identity, dict) and identity.get('experiment_id') not in (None, experiment_id):
                raise ValueError('当前请求与实验费用授权不一致')
            binding = active
        else:
            # A pre-122b E5 already has a cap even before the script records its binding.
            legacy = database.parent / 'task120b' / '120b.ledger.json'
            identity = None
            if legacy.is_file():
                identity = json.loads(legacy.read_text()).get('identity')
            if isinstance(identity, dict) and identity.get('experiment_id') == experiment_id:
                binding = {'ledger_path':str(legacy), 'ledger_identity':identity}
            else:
                directory = database.parent / (database.name + '.provider-ledgers')
                directory.mkdir(mode=0o700, exist_ok=True)
                path = directory / (experiment_id + '.ledger.json')
                baseline = store.evaluation_run(row['baseline_run_id'], light=True)
                if baseline is None:
                    raise ValueError('费用授权所绑定的 Baseline 缺失')
                identity = {'experiment_id':experiment_id, 'baseline':row['baseline_run_id'],
                            'evaluation_identity':baseline['judge'].get('evaluation_identity')}
                if not path.exists():
                    PaidRun(path, prices=_price_snapshot(), identity=identity, request_policy={'kind':EXPERIMENT_ACCOUNTING,
                            'database_path':str(database), 'budget_usd':None})
                binding = {'ledger_path':str(path), 'ledger_identity':identity}
        result['paid_run'] = binding
        db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(result, ensure_ascii=False), experiment_id))
        return binding


@contextmanager
def restore_paid_context(store, binding, *, reopen=False):
    from .paid_run import PaidRun, current_paid_run, controlled_run, accounting_only
    if current_paid_run() is not None:
        if binding != current_binding():
            raise ValueError('当前请求与实验费用授权不一致')
        yield
        return

    def check_identity():
        identity = binding['ledger_identity']
        if isinstance(identity, dict) and identity.get('experiment_id'):
            experiment = store.experiment(identity['experiment_id'], light=True)
            if not experiment or experiment['result'].get('paid_run') != binding:
                return None
            if identity.get('baseline'):
                baseline = store.require_current_baseline(identity['baseline'])
                if experiment['baseline_run_id'] != baseline['id'] or baseline['judge'].get('evaluation_identity') != identity.get('evaluation_identity'):
                    return None
        return identity

    try:
        run = PaidRun.load_accounting(binding['ledger_path'], check_identity)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise ValueError('费用账本缺失或损坏，请核对原账本') from error
    if (run.identity != binding['ledger_identity'] or not run.request_policy
            or Path(run.request_policy['database_path']).resolve() != Path(store.database_path).resolve()):
        raise ValueError('Recovered paid task binding changed')
    if reopen:
        run.reopen()
    with controlled_run(run), accounting_only(): yield
