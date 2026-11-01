"""任务004：只读重算保存的 Baseline 错题归因，不调用模型、不写数据库。"""
import argparse
from collections import Counter
from contextlib import contextmanager
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
from zipfile import ZipFile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.diagnostics import automatic_analysis, _saved_verdict


LATEST = 'EVAL-20261027122116244939'
CATEGORIES = ('检索失败', '检索噪声', '回答问题', '过度拒答', '安全边界问题', '记录缺失')
FIELDS = ['运行ID', '题号', '原题ID', '题型', '结论类别', '一句话理由', '标准证据逐段检查',
          'Recall@K', 'Precision@K', 'MRR', '缺失具体原因', '来源']


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as source:
        return list(csv.DictReader(source))


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as output:
        writer = csv.DictWriter(output, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@contextmanager
def readonly(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    try:
        yield connection
    finally:
        connection.close()


def restore_archived_databases(archive, wanted, directory):
    """Reassemble only requested historical DBs from task003's deduplicated archive.

    All restored files live in TemporaryDirectory, never in the formal data path.
    The current demo.db is read in place and never copied for this operation.
    """
    import zstandard
    with ZipFile(archive) as package:
        member = next(n for n in package.namelist() if n.endswith('.tar.zst'))

        def stream():
            return zstandard.ZstdDecompressor().stream_reader(package.open(member))

        with stream() as reader, tarfile.open(fileobj=reader, mode='r|') as tar:
            manifest = None
            for entry in tar:
                if entry.name == 'metadata/manifest.json':
                    manifest = json.load(tar.extractfile(entry))
                    break
        if manifest is None:
            raise ValueError('任务003归档缺少 metadata/manifest.json')
        files = {f['path']: f for f in manifest['files'] if f['path'] in wanted}
        missing = wanted - files.keys()
        if missing:
            raise FileNotFoundError('任务003归档未找到数据库：' + '、'.join(sorted(missing)))
        required = {digest for file in files.values() for digest in file['chunks']}
        chunks = directory / 'chunks'
        chunks.mkdir()
        with stream() as reader, tarfile.open(fileobj=reader, mode='r|') as tar:
            for entry in tar:
                digest = entry.name.removeprefix('chunks/')
                if entry.name.startswith('chunks/') and digest in required:
                    data = zlib.decompress(tar.extractfile(entry).read())
                    if hashlib.sha256(data).hexdigest() != digest:
                        raise ValueError('归档块哈希不一致：' + digest)
                    (chunks / digest).write_bytes(data)
        restored = {}
        for index, (name, file) in enumerate(files.items()):
            destination = directory / f'historical-{index}.db'
            digest = hashlib.sha256()
            with destination.open('wb') as output:
                for block in file['chunks']:
                    data = (chunks / block).read_bytes()
                    output.write(data)
                    digest.update(data)
            if destination.stat().st_size != file['bytes'] or digest.hexdigest() != file['sha256']:
                raise ValueError('历史库重组哈希不一致：' + name)
            restored[name] = destination
        return restored


def diagnose_run(path, run_id, source):
    with readonly(path) as connection:
        run = connection.execute('SELECT dataset_snapshot_json FROM evaluation_runs WHERE id=?', (run_id,)).fetchone()
        if run is None:
            raise ValueError('数据库缺少运行：' + run_id)
        snapshot = json.loads(run['dataset_snapshot_json'])
        questions = snapshot.get('questions') or []
        questions_by_id = {q['id']: q for q in questions}
        rows = connection.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=? ORDER BY id', (run_id,)).fetchall()
    result = []
    for row in rows:
        case = json.loads(row['result_json'])
        if _saved_verdict(case) != 'FAIL':
            continue
        question = questions_by_id.get(row['question_id']) or {}
        analysis = automatic_analysis(case, golden_item=question)
        metrics = analysis['retrieval_metrics']
        result.append({'运行ID': run_id, '题号': question.get('coverage_slot') or row['question_id'],
                       '原题ID': row['question_id'], '题型': case.get('test_category') or question.get('test_category') or '未知',
                       '结论类别': analysis['diagnosis_category'], '一句话理由': analysis['analysis_reason'],
                       '标准证据逐段检查': json.dumps(analysis['evidence_checks'], ensure_ascii=False),
                       'Recall@K': metrics['recall_at_k'], 'Precision@K': metrics['precision_at_k'], 'MRR': metrics['mrr'],
                       '缺失具体原因': '；'.join(gap['condition'] for gap in analysis['diagnostic_gaps']),
                       '来源': source + '#evaluation_case_results/' + run_id + '/' + row['question_id']})
    return result


def export_report(root, runs_csv, output, archive):
    runs = [row for row in read_csv(runs_csv) if row['类型'].lower() == 'baseline' and row['原始状态'] == 'completed']
    sources = {row['运行ID']: row['来源'].split('#')[0] for row in runs}
    missing = {name for name in sources.values() if not (root / name).is_file()}
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='task004-history-') as temporary:
        restored = restore_archived_databases(archive, missing, Path(temporary)) if missing else {}
        results = []
        for row in runs:
            name = sources[row['运行ID']]
            path = restored[name] if name in restored else root / name
            label = (str(archive) + '!' + name) if name in restored else name
            results.extend(diagnose_run(path, row['运行ID'], label))
    latest = [row for row in results if row['运行ID'] == LATEST]
    write_csv(output / '归因_1027.csv', FIELDS, latest)
    write_csv(output / '归因_全部已完成Baseline.csv', FIELDS, results)
    missing_rows = [row for row in results if row['结论类别'] == '记录缺失']
    write_csv(output / '归因_记录缺失明细.csv', FIELDS, missing_rows)
    summary_rows = []
    for run_id in [row['运行ID'] for row in runs] + ['全部']:
        selected = [row for row in results if row['运行ID'] == run_id] if run_id != '全部' else results
        counts = Counter(row['结论类别'] for row in selected)
        summary_rows.append({'运行ID': run_id, '错题数': len(selected), **{category: counts[category] for category in CATEGORIES}})
    write_csv(output / '归因_分类统计.csv', ['运行ID', '错题数', *CATEGORIES], summary_rows)
    return {'baseline_run_count': len(runs), 'bad_case_count': len(results),
            'category_counts': dict(Counter(row['结论类别'] for row in results)),
            'latest_bad_case_count': len(latest),
            'latest_category_counts': dict(Counter(row['结论类别'] for row in latest)),
            'missing_record_count': len(missing_rows), 'restored_historical_database_count': len(missing),
            'provider_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument('--root', type=Path, default=root)
    parser.add_argument('--runs', type=Path, default=root / '指挥/报告/001-数据/runs.csv')
    parser.add_argument('--output', type=Path, default=root / '指挥/报告/004-数据')
    parser.add_argument('--archive', type=Path, default=Path.home() / 'RAG归档/RAG任务003-20261101-总备份.zip')
    args = parser.parse_args()
    summary = export_report(args.root, args.runs, args.output, args.archive)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
