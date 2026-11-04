"""Price-window policy for authorized batch work; never authorizes a new task."""
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .telemetry import price_config


def utc_now():
    return datetime.now(timezone.utc)


def _settings(store):
    with store.connection() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='paid_schedule_settings'").fetchone():
            return {}
        return {row['key']: json.loads(row['value_json']) for row in db.execute('SELECT * FROM paid_schedule_settings')}


def _write(store, key, value):
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS paid_schedule_settings (key TEXT PRIMARY KEY,value_json TEXT NOT NULL)')
        db.execute('INSERT INTO paid_schedule_settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json',
                   (key, json.dumps(value, ensure_ascii=False)))


def set_settings(store, off_peak_only):
    _write(store, 'off_peak_only', off_peak_only)
    return schedule_status(store)


def set_run_now(store, task_key):
    _write(store, 'override:' + task_key, True)


def clear_run_now(store, task_key):
    _write(store, 'override:' + task_key, False)


def schedule_status(store, *, at=None):
    prices = price_config()
    now = (at or utc_now()).astimezone(timezone.utc)
    enabled = _settings(store).get('off_peak_only', True)
    windows = (prices or {}).get('peak_hours_utc', [])
    weekdays = (prices or {}).get('peak_weekdays', [])
    def peak(value):
        # Unknown holiday status does not permit an expensive batch. A verified
        # holiday is safe to use; otherwise respect the snapshot's UTC windows.
        calendar = (prices or {}).get('verified_holiday_calendar', {})
        holiday = calendar.get('source_url') and calendar.get('checked_at') and calendar.get('dates', {}).get(
            value.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()) is True
        return not holiday and value.weekday() in weekdays and any(start <= value.hour < end for start, end in windows)
    unknown = prices is None
    in_peak = peak(now) if not unknown else None
    resume = now
    while in_peak and peak(resume):
        resume = resume.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return {'off_peak_only': enabled, 'peak_now': in_peak, 'price_schedule_available': not unknown,
            'next_off_peak_at': resume.isoformat() if in_peak else None,
            'resume_at_toronto': resume.astimezone(ZoneInfo('America/Toronto')).strftime('%H:%M') if in_peak else None,
            'price_config_version': (prices or {}).get('price_config_version')}


def pause_state(store, task_key):
    status = schedule_status(store)
    settings = _settings(store)
    override = settings.get('override:' + task_key, False)
    # Sandbox belongs to the cycle/Agent task whose explicit override was saved.
    if task_key.startswith('evaluation:') and not override:
        run = store.evaluation_run(task_key.split(':', 1)[1], light=True)
        cid = (run or {}).get('config', {}).get('candidate_id')
        candidate = store.candidate(cid) if cid else None
        experiment_id = (candidate or {}).get('experiment_id')
        experiment = store.experiment(experiment_id, light=True) if experiment_id else None
        active_cycle = (experiment or {}).get('result', {}).get('optimization_cycle', {}).get('status') == 'running'
        override = bool(active_cycle and settings.get('override:cycle:' + experiment_id))
    if task_key.startswith('agent:'):
        experiment_id=task_key.split(':',1)[1]
        experiment=store.experiment(experiment_id,light=True)
        active_cycle=(experiment or {}).get('result',{}).get('optimization_cycle',{}).get('status')=='running'
        override = override or bool(active_cycle and settings.get('override:cycle:' + experiment_id, False))
    paused = status['off_peak_only'] and not override and status['peak_now'] is not False
    return {'paused': bool(paused), 'resume_at': status['next_off_peak_at'], 'resume_at_toronto': status['resume_at_toronto'],
            'message': ('高峰时段暂停，预计 ' + status['resume_at_toronto'] + ' 自动继续（多伦多时间）') if paused and status['peak_now'] else
                       '价格快照不可用，暂停等待价格信息' if paused else None,
            'peak_price_override': bool(override), 'price_config_version': status['price_config_version']}


def wait_for_off_peak(store, task_key, on_state, check_stop=lambda: None):
    previous = None
    while True:
        check_stop()
        pause = pause_state(store, task_key)
        if pause != previous:
            on_state(pause)
            previous = pause
        if not pause['paused']:
            return
        time.sleep(1)


def save_composite_schedule(store, experiment_id, **updates):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        if not row:
            raise ValueError('实验不存在')
        result = json.loads(row['result_json'])
        state = {**result.get('composite_schedule', {}), **updates}
        result['composite_schedule'] = state
        db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(result, ensure_ascii=False), experiment_id))
        return state


_composite_lock = threading.Lock()
_composite_workers = {}


def start_scheduled_composite(store, provider, experiment_id, *, recover=False):
    """Persist only an explicitly requested D; the monitor cannot invent one."""
    def work():
        try:
            wait_for_off_peak(store, 'composite:' + experiment_id,
                lambda pause: save_composite_schedule(store, experiment_id, price_pause=pause))
            save_composite_schedule(store, experiment_id, status='running')
            outcome=store.create_composite(experiment_id, provider)
            save_composite_schedule(store, experiment_id,
                status='running' if outcome.get('status')=='analyzing' else 'completed')
        except Exception as error:
            save_composite_schedule(store, experiment_id, status='failed', error=str(error))
    with _composite_lock:
        key = (str(store.database_path), experiment_id)
        thread = _composite_workers.get(key)
        if thread and thread.is_alive():
            return store.experiment(experiment_id, light=True)['result']['composite_schedule']
        experiment = store.experiment(experiment_id, light=True)
        if not experiment or not experiment['result'].get('report_confirmation'):
            raise ValueError('需要Gate 2确认合格方案')
        if recover:
            state = experiment['result'].get('composite_schedule', {})
            if state.get('status') not in {'waiting', 'running'}: return state
            owner = state.get('owner_pid')
            if owner != os.getpid() and type(owner) is int:
                try: os.kill(owner, 0)
                except ProcessLookupError: pass
                except PermissionError: return state
                else: return state
            composite = experiment['result'].get('composite')
            if composite:
                complete = composite.get('status') in {'generated', 'no_effective_composite'}
                return save_composite_schedule(store, experiment_id, status='completed' if complete else 'unknown',
                    error=None if complete else '组合请求的结果未知，保留记录，不重复调用')
        elif experiment['result'].get('composite'):
            raise ValueError('方案 D 已处理，请刷新查看结果')
        elif experiment['result'].get('composite_schedule', {}).get('status') not in {'waiting', 'running'}:
            clear_run_now(store, 'composite:' + experiment_id)
        state = save_composite_schedule(store, experiment_id, status='waiting', owner_pid=os.getpid(),
                                        price_pause=pause_state(store, 'composite:' + experiment_id))
        thread = threading.Thread(target=work, daemon=True)
        _composite_workers[key] = thread
        thread.start()
        return state


def recover_scheduled_composites(store, provider):
    with store.connection() as db:
        ids = [row['id'] for row in db.execute("SELECT id FROM experiments WHERE json_extract(result_json,'$.composite_schedule.status') IN ('waiting','running')")]
    for experiment_id in ids:
        start_scheduled_composite(store, provider, experiment_id, recover=True)


def active_pauses(store):
    """Lightweight settings view, including batches with a historical source run."""
    result=[]
    def add(label,pause,target):
        if pause and pause.get('paused'):
            result.append({'task_label':label,'price_pause':pause,'target':target})
    with store.connection() as db:
        for row in db.execute("SELECT id,config_json,json_extract(result_json,'$.price_pause') pause FROM evaluation_runs WHERE status IN ('queued','running')"):
            config=json.loads(row['config_json']);candidate_id=config.get('candidate_id','')
            label=candidate_id.rsplit('-',1)[-1]
            name='方案 '+label+' · Sandbox 试跑' if label in 'ABCD' and label else 'Baseline 评测'
            if config.get('run_target')=='answer_replay':name='历史回答判分回放'
            add(name,json.loads(row['pause']) if row['pause'] else None,{'evaluation_id':row['id']})
        for row in db.execute("SELECT id,status,json_object('optimization_cycle',json_extract(result_json,'$.optimization_cycle'),'price_pause',json_extract(result_json,'$.price_pause'),'composite_schedule',json_extract(result_json,'$.composite_schedule')) result_json FROM experiments"):
            saved={key:value for key,value in json.loads(row['result_json']).items() if value is not None}
            if saved.get('optimization_cycle',{}).get('status')=='running':
                pauses=[saved['optimization_cycle'].get('price_pause'),saved.get('price_pause')]
                add('Agent 优化循环',next((pause for pause in pauses if pause and pause.get('paused')),None),{'experiment_id':row['id']})
            elif row['status']=='generating':
                add('Agent 生成方案',saved.get('price_pause'),{'experiment_id':row['id']})
            if saved.get('composite_schedule',{}).get('status') in {'waiting','running'}:
                add('方案 D · 合并方案',saved['composite_schedule'].get('price_pause'),{'experiment_id':row['id']})
        for row in db.execute("SELECT r.id,json_extract(a.hard_validation_json,'$.price_pause') pause FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.status IN ('queued','running','generating','coverage','validation','validating','probing','qc')"):
            add('Golden 出题与质检',json.loads(row['pause']) if row['pause'] else None,{'generation_id':row['id']})
        for row in db.execute("SELECT id,json_extract(audit_json,'$.price_pause') pause FROM candidate_revision_runs WHERE status IN ('queued','generating','validating','probing','qc')"):
            add('Golden 题目修订',json.loads(row['pause']) if row['pause'] else None,{'revision_id':row['id']})
        for row in db.execute("SELECT run_id,question_id,checkpoint_json FROM job_checkpoints WHERE question_id LIKE 'diagnostic-batch:%' AND json_extract(checkpoint_json,'$.status') IN ('waiting','running')"):
            saved=json.loads(row['checkpoint_json'])
            add('保存证据批量诊断',saved.get('price_pause'),{'evaluation_id':row['run_id'],'diagnostic_id':row['question_id'].split(':',1)[1]})
    root=store.database_path.parent/'followups'
    if root.exists():
        for path in root.glob('*/*.json'):
            if path.stem not in {'max','high','low'}:continue
            saved=json.loads(path.read_text()).get('_job',{})
            if saved.get('status') in {'starting','running'}:
                add('保存回答判分校准',saved.get('price_pause'),{'evaluation_id':path.parent.name,'calibration_group':path.stem})
    return result
