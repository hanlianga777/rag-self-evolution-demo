#!/usr/bin/env python3
"""Resume only the authorized 031e experiment, atomically and once."""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.governance import GovernanceStore
from app.rules import LEGACY_031E_ROUND_LIMIT

EXPERIMENT = 'EXP-20261114175011989842'
REASON = '继续完成三轮优化，用户 2026-11-14 预先授权'


class _TransactionStore(GovernanceStore):
    def connection(self):
        return nullcontext(self.transaction)


def migrate(store):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT result_json FROM experiments WHERE id=?', (EXPERIMENT,)).fetchone()
        if row is None:
            raise ValueError('031e指定实验不存在')
        result = json.loads(row[0])
        if result.get('round_policy',{}).get('mode') == 'full_rounds' and result.get('strategy_contract') == 'agent-strategy-4':
            return False
        if result.get('optimization_cycle',{}).get('status') == 'running':
            raise ValueError('实验仍在运行，不能迁移')
        now = datetime.now(timezone.utc).isoformat()
        for field in ('report_confirmation','composite','d_facts'):
            if field in result:
                previous = result.pop(field)
                if field == 'report_confirmation':
                    previous = {**previous,'superseded_at':now,'superseded_reason':REASON}
                result.setdefault(field+'_history',[]).append(previous)
        conclusions = result.get('round_conclusions',{})
        if '1' in conclusions:
            result.setdefault('round_conclusions_history',{}).setdefault('1',[]).append(conclusions.pop('1'))
        for label in 'BC':
            cid = EXPERIMENT+'-R1-'+label
            candidate = db.execute('SELECT status,result_json FROM candidate_configs WHERE id=? AND experiment_id=?', (cid,EXPERIMENT)).fetchone()
            if candidate is None or candidate['status'] != 'skipped':
                raise ValueError('迁移前B/C应为未运行的skipped方案')
            saved = json.loads(candidate['result_json'])
            if saved.get('evaluation_run_id'):
                raise ValueError('B/C已有试跑记录，不能重置')
            if 'skip' in saved:
                saved.setdefault('skip_history',[]).append(saved.pop('skip'))
            db.execute("UPDATE candidate_configs SET status='generated',result_json=? WHERE id=?", (json.dumps(saved,ensure_ascii=False),cid))
        result['round_policy'] = {'mode':'full_rounds','max_rounds':LEGACY_031E_ROUND_LIMIT,'set_by':'用户','note':'用户 2026-11-14 预先授权'}
        result['strategy_contract'] = 'agent-strategy-4'
        cycle = result.setdefault('optimization_cycle',{})
        cycle.update(status='ready',phase='analysis',current_round_only=False,last_error=None,updated_at=now)
        for field in ('stop_request','owner_pid','worker_thread'):
            cycle.pop(field,None)
        db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(result,ensure_ascii=False),EXPERIMENT))
        # Reuse the real recommendation logic on this same uncommitted snapshot.
        transaction_store = object.__new__(_TransactionStore)
        transaction_store.database_path, transaction_store.transaction = store.database_path, db
        transaction_store.refresh_recommendation(EXPERIMENT)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'experiment_id':EXPERIMENT,'migrated':migrate(GovernanceStore(args.database,migrate=False))}))
