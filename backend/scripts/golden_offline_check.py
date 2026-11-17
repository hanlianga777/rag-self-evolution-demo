"""总指挥发题卷前的离线自检：不读数据库、不调模型，用导出的全量切块跑和正式导入完全相同的硬校验。

为什么要有它（2026-11-16 复盘）：049 发出前总指挥"本地验过 0 错"，但验的是自己另写的读法，
正式导入脚本读 CSV 时吃掉了单元格里的换行，到 Codex 那里 19 题报错、任务单两次暂缓。
现在两边共用 import_friend_golden.read_rows / check_rows，自检过了，正式 dry-run 就不会因为读法不同而失败。

PYTHONPATH=backend python3 backend/scripts/golden_offline_check.py --csv 指挥/报告/049-新题卷定稿.csv --chunks 指挥/报告/046-切块全量.csv
退出码：0 = 0 错；1 = 有错（逐题打印）。
"""
import argparse
import csv
import importlib.util
import io
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('import_friend_golden', Path(__file__).resolve().parent / 'import_friend_golden.py')
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def exported_chunks(path):
    """读 046 导出的切块全量 CSV（切块原文里的换行导出时写成了字面 \\n）。"""
    chunks = []
    for row in csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'), newline='')):
        meta = json.loads(row.get('章节标题或父级上下文') or '{}')
        chunks.append({'chunk_id': row['chunk_id'], 'document_id': row['doc_id'], 'document_name': row['文档名'],
                       'chunk_text': row['切块原文'].replace('\\n', '\n'), 'parent_chunk_id': meta.get('parent_chunk_id')})
    return chunks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--chunks', type=Path, required=True)
    args = parser.parse_args(argv)
    summary, _ = importer.check_rows(importer.read_rows(args.csv.read_bytes()), exported_chunks(args.chunks))
    return summary


if __name__ == '__main__':
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=1), flush=True)
    sys.exit(1 if result['error_rows'] else 0)
