"""Append the E2 Gate 2 audit correction while preserving its approval."""
import json
from datetime import datetime, timezone

from .rules import AGENT_GATE_AUDIT

E2_ID = 'EXP-20261123010322145772'
E2_APPROVAL_ID = 590
AUDIT_KEYS = tuple(AGENT_GATE_AUDIT)


def gate2_correction(db, experiment_id):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='gate_audit_corrections' AND type='table'").fetchone():
        return None
    row = db.execute("""SELECT correction.event_json FROM gate_audit_corrections correction
        JOIN approvals ON approvals.id = correction.approval_id
        WHERE approvals.gate = 'experiment_report' AND approvals.target_id = ?""", (experiment_id,)).fetchone()
    return json.loads(row[0]) if row else None


def append_e2_gate2_correction(store):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if previous := gate2_correction(db, E2_ID):
            return previous
        approval = db.execute('SELECT * FROM approvals WHERE id=?', (E2_APPROVAL_ID,)).fetchone()
        if (not approval or approval['gate'] != 'experiment_report' or approval['target_id'] != E2_ID
                or approval['decision'] != 'approved' or approval['actor'] != 'Codex'):
            raise ValueError('无法定位 E2 原 Gate 2 审批 590')
        snapshots = []
        for table, key in (('experiments', 'id'), ('recommendations', 'experiment_id')):
            row = db.execute(f'SELECT result_json FROM {table} WHERE {key}=?', (E2_ID,)).fetchone()
            result = json.loads(row[0]) if row else {}
            confirmation = result.get('report_confirmation') or {}
            if (confirmation.get('actor') != approval['actor']
                    or confirmation.get('winner_id') != f'{E2_ID}-R2-B'
                    or confirmation.get('confirmed_at', '')[:19] != approval['created_at'][:19]
                    or {k: confirmation.get(k) for k in AUDIT_KEYS} != AGENT_GATE_AUDIT):
                raise ValueError(f'{table} 的 E2 确认与已核对的补录记录不一致')
            snapshots.append((table, key, result, confirmation))
        event = {'type': 'gate2_audit_correction', 'corrected_at': datetime.now(timezone.utc).isoformat(),
                 'corrected_by': 'Codex',
                 'reason': '111d 记录旧后端落下授权审计字段，审批后直接补写了两个确认快照。本次将补写字段移入独立更正事件。',
                 'original_approval': {key: approval[key] for key in approval.keys()},
                 'original_backfill_at': None, 'audit': AGENT_GATE_AUDIT.copy()}
        db.execute('''CREATE TABLE IF NOT EXISTS gate_audit_corrections (
            approval_id INTEGER PRIMARY KEY REFERENCES approvals(id), event_json TEXT NOT NULL)''')
        db.execute('INSERT INTO gate_audit_corrections VALUES (?,?)',
                   (E2_APPROVAL_ID, json.dumps(event, ensure_ascii=False)))
        for table, key, result, confirmation in snapshots:
            for field in AUDIT_KEYS:
                del confirmation[field]
            db.execute(f'UPDATE {table} SET result_json=? WHERE {key}=?',
                       (json.dumps(result, ensure_ascii=False), E2_ID))
        return event
