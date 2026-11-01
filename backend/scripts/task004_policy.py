"""任务004：只读重算10-22 Recovery保存的ABC，不运行回退复核或模型。"""
import csv
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.evaluation import candidate_comparison, protected_question
from app.policy import evaluate_regression, qualify_candidate, select_final_candidate
from task004_diagnosis import readonly, restore_archived_databases

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = 'EXP-RECOVERY-20261022T0649135884120000'
SOURCE = 'backend/data/page-perf-before-reload-20261025.db'
ARCHIVE = Path('/Users/zhanghaohan/RAG归档/RAG任务003-20261101-总备份.zip')


def export(output):
    rows, candidates = [], []
    with tempfile.TemporaryDirectory(prefix='task004-policy-history-') as temporary:
        path = ROOT / SOURCE
        if not path.is_file():
            path = restore_archived_databases(ARCHIVE, {SOURCE}, Path(temporary))[SOURCE]
        with readonly(path) as db:
            saved = db.execute('SELECT * FROM candidate_configs WHERE experiment_id=? ORDER BY id', (EXPERIMENT,)).fetchall()
            if len(saved) != 3:
                raise ValueError('归档没有完整Recovery ABC')
            for row in saved:
                result, reasoning = json.loads(row['result_json']), json.loads(row['reasoning_json'])
                baseline_id, run_id = result['baseline_run_id'], result['evaluation_run_id']
                def cases(key):
                    return {r['question_id']: {'question_id': r['question_id'], **json.loads(r['result_json'])} for r in db.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=?', (key,))}
                baseline, candidate = cases(baseline_id), cases(run_id)
                failed = [q for q, c in baseline.items() if c.get('passed') is False]
                refs = set(reasoning.get('observed_evidence', []))
                targets = [q for q in failed if q in refs or f'BC-{baseline_id}-{q}' in refs]
                snapshot = json.loads(db.execute('SELECT dataset_snapshot_json FROM evaluation_runs WHERE id=?', (baseline_id,)).fetchone()[0])
                questions = {q['id']: q for q in snapshot.get('questions', [])}
                comparison = candidate_comparison(baseline, candidate, targets, questions)
                regression = evaluate_regression(new_critical_failures=comparison['new_critical_failures'], new_ordinary_failures=comparison['new_ordinary_failures'])
                qualification = qualify_candidate(result['gates'], regression, comparison['target_bad_cases_fixed'], len(failed), comparison['bad_case_count'])
                safety = [q for q in comparison['new_regression_question_ids'] if protected_question(baseline[q], questions.get(q))]
                typed_safety = [q for q in comparison['new_regression_question_ids'] if questions.get(q, {}).get('negative_subtype') in {'safety_critical', 'prompt_injection'}]
                static_critical = [q for q in comparison['new_regression_question_ids'] if questions.get(q, {}).get('criticality') == 'high' or questions.get(q, {}).get('severity') == 'critical']
                dynamic_critical = [q for q in comparison['new_regression_question_ids'] if candidate[q].get('severity') == 'critical']
                rows.append({'方案': reasoning.get('candidate_label', row['id'][-1]), '方案ID': row['id'],
                    '旧结论': result.get('qualification', {}).get('status', '未知'), '新结论': qualification['status'],
                    'Baseline错题': len(failed), '方案错题': comparison['bad_case_count'], '修好数': len(comparison['all_fixed_question_ids']),
                    '目标修好数': comparison['target_bad_cases_fixed'], '新坏数': comparison['new_regressions'],
                    '新坏安全数': len(safety), '新坏安全题': '；'.join(safety),
                    '冻结安全关键或注入题数': len(typed_safety), '冻结题型安全题': '；'.join(typed_safety),
                    '冻结严重度关键题数': len(static_critical), '方案保存severity为critical数': len(dynamic_critical),
                    '安全判定来源': '冻结题卷negative_subtype/criticality/severity；冻结严重度缺失时参考Baseline通过题的保存severity；不采用方案动态severity升级',
                    '11门槛通过数': result['gates'].get('passed_count', '未知'),
                    '新规则未通过项': '；'.join(k for k, v in qualification['checks'].items() if not v),
                    '回退复核': '未运行（按任务不花钱）；新增按初次结果计，未确认是否波动',
                    '来源': str(ARCHIVE) + '!' + SOURCE + '#candidate_configs/' + row['id']})
                candidates.append({'id': row['id'], 'status': row['status'], 'reasoning': reasoning, 'result': {**result, 'qualification': qualification, 'bad_case_count': comparison['bad_case_count']}})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n");writer.writeheader();writer.writerows(rows)
    return {'rows': rows, 'decision': select_final_candidate(candidates), 'provider_calls': 0, 'review_runs': 0}


if __name__ == '__main__':
    print(json.dumps(export(ROOT / '指挥/报告/004-数据/合格规则_1022.csv'), ensure_ascii=False, indent=2))
