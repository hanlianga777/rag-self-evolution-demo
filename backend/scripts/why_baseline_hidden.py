"""只读诊断：页面为什么看不到当前 Baseline。逐条复现 current_baseline_identity 的筛选条件，打印每个评测卡在哪一条。

PYTHONPATH=backend python3 backend/scripts/why_baseline_hidden.py
"""
import json
import os
import sqlite3
from pathlib import Path


def main():
    from app.config import load_values
    db = load_values().get('RAG_DEMO_DB_PATH') or str(Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = db
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store
    from app.corpus import current_manifest
    from app.governance import manifest_identity
    from app.evaluation_contract import policy_current, evaluation_identity, VERSIONS
    from app.ai_service import generation_contract
    out = {'identity': store.current_baseline_identity(), 'designation': store.baseline_designation()}
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True); con.row_factory = sqlite3.Row
    golden = con.execute("SELECT * FROM dataset_versions WHERE status='approved' ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
    snapshot = json.loads(golden['snapshot_json'])
    fingerprint = manifest_identity(current_manifest())
    out['golden'] = golden['id']; out['golden_corpus_matches'] = snapshot.get('corpus_fingerprint') == fingerprint
    runs = []
    for row in con.execute("SELECT id,status,run_mode,data_source,config_json,judge_json,result_json,dataset_snapshot_json,error_message,completed_at FROM evaluation_runs WHERE dataset_version_id=? ORDER BY created_at DESC", (golden['id'],)):
        config, judge = json.loads(row['config_json'] or '{}'), json.loads(row['judge_json'] or '{}')
        result, frozen = json.loads(row['result_json'] or '{}'), json.loads(row['dataset_snapshot_json'] or '{}')
        cases = sorted(r[0] for r in con.execute('SELECT question_id FROM evaluation_case_results WHERE run_id=?', (row['id'],)))
        current = generation_contract()
        checks = {
            'status_completed_real': row['status'] == 'completed' and row['run_mode'] == 'real' and row['data_source'] == 'real',
            'run_target_baseline': config.get('run_target') in (None, 'baseline') and not config.get('candidate_id'),
            'judge_fields': bool(config and judge.get('model') and judge.get('prompt_version') and judge.get('scoring_policy')),
            'has_gates': 'gates' in result, 'no_error': not row['error_message'] and bool(row['completed_at']),
            'corpus_matches': frozen.get('corpus_fingerprint') == fingerprint,
            'questions_match': all(frozen.get(k) == snapshot.get(k) for k in ('question_ids', 'questions')),
            'cases_complete': cases == sorted(snapshot.get('question_ids') or []),
            'policy_current': policy_current(judge),
            'policy_diff': {k: [judge.get(k), v] for k, v in VERSIONS.items() if judge.get(k) != v},
            'generation_diff': {k: [judge.get(k), v] for k, v in current.items() if judge.get(k) != v},
            'evaluation_identity_matches': judge.get('evaluation_identity') == evaluation_identity(frozen, judge),
        }
        if not checks['questions_match']:
            a, b = frozen.get('questions') or [], snapshot.get('questions') or []
            checks['first_question_diff'] = next(({'index': i, 'keys': sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))} for i, (x, y) in enumerate(zip(a, b)) if x != y), {'len': [len(a), len(b)]})
        runs.append({'id': row['id'], **checks})
    out['runs'] = runs
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    main()
