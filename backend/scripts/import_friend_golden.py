"""导入总指挥出的朋友同款题卷 CSV（规则总表一，2026-11-16 晚）。

CSV 列（UTF-8，可带 BOM）：
  题号, 题型(positive/ablation/negative), 出题方式(单段标准/跨段综合/统计/桥接/台账事实/口语变体/别名变体/弱关键词变体/跨段变体/负向),
  消融类型(colloquial/alias_entity/weak_keywords/cross_chunk，消融题必填), 原实体, 别名, 配对题号,
  负向子类型, 预期行为, criticality, 问题, 参考答案,
  证据（每行一段，格式：chunk_id｜切块原文中的连续片段）, 考查节点, 考查参数, 难度, 关键词, 备注, 统计条目（统计题必填，用｜分隔）

默认 dry-run：逐题跑朋友同款硬校验（证据逐字定位、答案锚点、跨段校验、统计/桥接/事实构造检查、页码题禁出等），
打印每题错误，不写库；加 --apply 才写入一个新的候选版本（不冻结、不做 Gate 1）。

PYTHONPATH=backend python3 backend/scripts/import_friend_golden.py --csv 指挥/报告/049-新题卷定稿.csv [--apply]
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path

# 桥接、台账事实沿用 Ordinary 构造类型：系统旧的 Bridge/Fact 判定依赖'键：值'行格式，本库表格是'键 | 值'或'参数=…'，
# 会把合格题误拦；这两类的跨段必要性由 validate_friend_content 的跨块校验负责，统计题仍走 Aggregation 逐项核对。
KINDS = {'单段标准': 'Ordinary', '跨段综合': 'Ordinary', '统计': 'Aggregation', '桥接': 'Ordinary', '台账事实': 'Ordinary',
         '口语变体': 'Ordinary', '别名变体': 'Ordinary', '弱关键词变体': 'Ordinary', '跨段变体': 'Ordinary', '负向': 'Ordinary'}


def to_candidate(row):
    group = row['题型'].strip()
    method = row['出题方式'].strip()
    if method not in KINDS:
        raise ValueError(f"{row['题号']} 出题方式无效：{method}")
    evidence = []
    for line in (row.get('证据') or '').splitlines():
        if not line.strip():
            continue
        chunk_id, sep, quote = line.partition('｜')
        if not sep or not chunk_id.strip() or not quote.strip():
            raise ValueError(f"{row['题号']} 证据格式应为 chunk_id｜原文：{line[:40]}")
        evidence.append({'source_chunk_ids': [chunk_id.strip()], 'evidence_key_points': [quote.strip()]})
    candidate = {'coverage_slot': row['题号'].strip(), 'question': row['问题'].strip(), 'user_query': row['问题'].strip(),
                 'reference_answer': row['参考答案'].strip() or None, 'test_category': group, 'evaluation_group': group,
                 'construction_type': KINDS[method], 'generation_method': method, 'evidence': evidence,
                 'test_node': row.get('考查节点', '').strip() or None, 'config_param': row.get('考查参数', '').strip() or None,
                 'difficulty': row.get('难度', '').strip() or None, 'note': row.get('备注', '').strip() or None,
                 'keywords': [k.strip() for k in (row.get('关键词') or '').replace('，', ',').split(',') if k.strip()],
                 'paired_question': row.get('配对题号', '').strip() or None,
                 'golden_contract': 'friend-golden-v1'}
    if method == '统计':
        candidate['aggregation_items'] = [item.strip() for item in (row.get('统计条目') or '').split('｜') if item.strip()]
    if group == 'ablation':
        candidate['ablation_attribute'] = row.get('消融类型', '').strip()
        if candidate['ablation_attribute'] == 'alias_entity':
            candidate['ablation_metadata'] = {'original_entity': row.get('原实体', '').strip(), 'alias_expression': row.get('别名', '').strip()}
    if group == 'negative':
        candidate.update(negative_subtype=row.get('负向子类型', '').strip(), expected_behavior=row.get('预期行为', '').strip(),
                         expected_response=candidate['reference_answer'], evidence=[])
        if row.get('criticality', '').strip():
            candidate['criticality'] = row['criticality'].strip()
    return candidate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    from app.config import load_values
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store
    from app.corpus import CorpusStore
    from app.golden_v2 import validate_golden_candidate
    from app.reviewed_import import FRIEND_CONTRACT, import_batch, validate_friend_content
    data = args.csv.read_bytes()
    # 单元格内有换行（多段证据、分行答案），不能先 splitlines 再交给 csv。
    rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline='')))
    chunks = CorpusStore().chunks()
    report, candidates = [], []
    for row in rows:
        errors = []
        try:
            candidate = to_candidate(row)
            validate_friend_content(candidate, chunks)
            checked = {**candidate, 'evidence': [] if candidate['test_category'] == 'negative' else candidate['evidence']}
            result = validate_golden_candidate(checked, chunks)
            errors.extend(result['blocking_errors'])
            candidates.append(candidate)
        except (ValueError, KeyError) as error:
            errors.append(str(error))
        report.append({'题号': row.get('题号'), 'errors': errors})
    summary = {'rows': len(rows), 'error_rows': sum(bool(r['errors']) for r in report),
               'errors': [r for r in report if r['errors']], 'dry_run': not args.apply}
    if args.apply:
        if summary['error_rows']:
            raise SystemExit(json.dumps(summary, ensure_ascii=False, indent=1))
        receipt = import_batch(store, candidates, hashlib.sha256(data).hexdigest(), str(args.csv),
                               '总指挥按朋友同款结构出题，用户 2026-11-16 授权由总指挥主导出题与审核', contract=FRIEND_CONTRACT)
        summary['receipt'] = receipt
    return summary


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=1), flush=True)
