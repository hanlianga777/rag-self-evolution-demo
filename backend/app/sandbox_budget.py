"""One durable CNY ceiling per experiment; only explicit launches acquire it."""
import fcntl,json,math
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from .diagnostic_evidence import digest
from .paid_run import PaidRun

PRICE_PATH=Path(__file__).resolve().parents[1]/'config/sandbox_prices.json'

def prices(path=PRICE_PATH):
    data=json.loads(Path(path).read_text())
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(data['checked_at'])).total_seconds()
    if data.get('currency')!='CNY' or not 0<=age<=86400:raise ValueError('Sandbox人民币费率缺失或超过24小时，停止并重新核价')
    for rate in data['models'].values():
        if any(type(rate.get(k)) not in (int,float) or not math.isfinite(rate[k]) or rate[k]<0 for k in ('input','output','max_output')):raise ValueError('Sandbox费率无效')
    return data

def binding(store,candidate_id):
    candidate=store.candidate(candidate_id)
    experiment=store.experiment(candidate['experiment_id'])
    baseline=store.evaluation_run(experiment['baseline_run_id'])
    return {'experiment_id':experiment['id'],'baseline_id':baseline['id'],
        'baseline_sha256':digest([baseline['dataset_snapshot_json'],baseline['config'],baseline['judge']]),
        'candidate_configs':{c['id']:c['config'] for c in experiment['candidates']}}

def budget_path(store,candidate_id):
    return store.database_path.parent/'sandbox-budgets'/(digest(binding(store,candidate_id)['experiment_id'])+'.json')

def budget_view(store,candidate_id):
    data=prices();path=budget_path(store,candidate_id)
    ledger=json.loads(path.read_text()) if path.exists() else None
    return {'currency':'CNY','scope':'本Experiment新授权Sandbox请求累计（历史费用另列，不视为0）',
        'hard_limit_yuan':ledger['budget_yuan'] if ledger else None,'spent_yuan':ledger['spent_yuan'] if ledger else 0,
        'held_yuan':sum(c['reserved_yuan'] for c in ledger['calls'] if c['status'] not in {'ok','rejected'}) if ledger else 0,
        'requires_explicit_budget':True,'price_checked_at':data['checked_at'],'ledger_path':str(path)}

@contextmanager
def sandbox_budget(store,candidate_id,budget_yuan,*,price_path=PRICE_PATH):
    if type(budget_yuan) not in (int,float) or not math.isfinite(budget_yuan) or budget_yuan<=0:raise ValueError('Sandbox需要明确的人民币累计硬上限')
    quote=prices(price_path);identity=binding(store,candidate_id);path=budget_path(store,candidate_id)
    path.parent.mkdir(parents=True,exist_ok=True)
    # ponytail: one serial experiment worker; advisory OS lock also survives process exit.
    with path.with_suffix('.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('同一Experiment费用预算已有运行持有，禁止并发') from None
        def check():
            current=prices(price_path)
            if current['models']!=quote['models']:raise ValueError('执行期间费率变化，停止')
            return binding(store,candidate_id)
        if path.exists():
            saved=json.loads(path.read_text())
            if saved.get('identity')!=identity or saved.get('price_snapshot')!=quote['models']:raise ValueError('Sandbox费用身份/费率变化，禁止重置累计账本')
            if budget_yuan>saved['budget_yuan']:raise ValueError('不得增加或重置已冻结累计上限')
            if any(c['status'] not in {'ok','rejected'} for c in saved['calls']):raise ValueError('统一预算账本含未知费用，须先对账')
            run=PaidRun.load_accounting(path,check);run.budget=budget_yuan;run.stopped=None
        else:
            limits=store.evaluation_run(identity['baseline_id'])['judge']['execution_snapshot']['request_limits']
            run=PaidRun(path,budget_yuan,quote['models'],identity,identity_check=check,output_limits=limits)
        run.enforce_budget=True
        run.currency='CNY'
        run.request_byte_limits=quote.get('request_byte_limits')
        run.stages.append({'candidate_id':candidate_id,'explicit_authorization_at':datetime.now(timezone.utc).isoformat(),'price_checked_at':quote['checked_at'],'price_sources':quote.get('sources',[])})
        run.save()
        yield run
