"""导入总指挥出的朋友同款题卷 CSV（规则总表一，2026-11-16 晚）。

CSV 列（UTF-8，可带 BOM）：
  题号, 题型(positive/ablation/negative), 出题方式(单段标准/跨段综合/统计/桥接/台账事实/口语变体/别名变体/弱关键词变体/跨段变体/负向),
  消融类型(colloquial/alias_entity/weak_keywords/cross_chunk，消融题必填), 原实体, 别名, 配对题号,
  负向子类型, 预期行为, criticality, 问题, 参考答案,
  证据（每行一段，格式：chunk_id｜切块原文中的连续片段）, 考查节点, 考查参数, 难度, 关键词, 备注, 业务主题, 业务分组（可空，填写版本化组 ID）, 跨型号（可选）, 统计条目（统计题必填，用｜分隔）,
  题型细分, 负向依据（格式同证据）, 真实问法理由, 必要安全前提, 部分可答, 替换槽位

默认 dry-run：逐题跑朋友同款硬校验（证据逐字定位、答案锚点、跨段校验、统计/桥接/事实构造检查、页码题禁出等），
打印每题错误，不写库；加 --apply 才写入一个新的候选版本（不冻结、不做 Gate 1）。M3 备用池传 --pool backup。

PYTHONPATH=backend python3 backend/scripts/import_friend_golden.py --csv 指挥/报告/049-新题卷定稿.csv [--apply]
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

# 桥接、台账事实沿用 Ordinary 构造类型：系统旧的 Bridge/Fact 判定依赖'键：值'行格式，本库表格是'键 | 值'或'参数=…'，
# 会把合格题误拦；这两类的跨段必要性由 validate_friend_content 的跨块校验负责，统计题仍走 Aggregation 逐项核对。
KINDS = {'单段标准': 'Ordinary', '跨段综合': 'Ordinary', '统计': 'Aggregation', '桥接': 'Ordinary', '台账事实': 'Ordinary',
         '口语变体': 'Ordinary', '别名变体': 'Ordinary', '弱关键词变体': 'Ordinary', '跨段变体': 'Ordinary', '负向': 'Ordinary'}


def parse_quotes(row, column):
    quotes = []
    for line in (row.get(column) or '').splitlines():
        if not line.strip():
            continue
        chunk_id, sep, quote = line.partition('｜')
        if not sep or not chunk_id.strip() or not quote.strip():
            raise ValueError(f"{row['题号']} {column}格式应为 chunk_id｜原文：{line[:40]}")
        quotes.append({'chunk_id': chunk_id.strip(), 'quote': quote})
    return quotes


def to_candidate(row):
    group = row['题型'].strip()
    method = row['出题方式'].strip()
    if method not in KINDS:
        raise ValueError(f"{row['题号']} 出题方式无效：{method}")
    evidence = [{'source_chunk_ids': [entry['chunk_id']], 'evidence_key_points': [entry['quote'].strip()]}
                for entry in parse_quotes(row, '证据')]
    candidate = {'coverage_slot': row['题号'].strip(), 'question': row['问题'].strip(), 'user_query': row['问题'].strip(),
                 'reference_answer': row['参考答案'].strip() or None, 'test_category': group, 'evaluation_group': group,
                 'construction_type': KINDS[method], 'generation_method': method, 'evidence': evidence,
                 'test_node': row.get('考查节点', '').strip() or None, 'config_param': row.get('考查参数', '').strip() or None,
                 'difficulty': row.get('难度', '').strip() or None, 'note': row.get('备注', '').strip() or None,
                 'keywords': [k.strip() for k in (row.get('关键词') or '').replace('，', ',').split(',') if k.strip()],
                 'paired_question': row.get('配对题号', '').strip() or None,
                 'business_topic': (row.get('业务主题') or '').strip() or None,
                 'business_group': (row.get('业务分组') or '').strip() or None,
                 'golden_contract': 'friend-golden-v1'}
    for column, field in (('题型细分', 'question_subtype'), ('真实问法理由', 'realism_note'),
                          ('必要安全前提', 'safety_premise'), ('部分可答', 'partial_answerable'),
                          ('替换槽位', 'replace_slot')):
        value = row.get(column)
        candidate[field] = value if value and value.strip() else None
    candidate['negative_basis'] = parse_quotes(row, '负向依据') or None
    if 'notes' in row:
        candidate['notes'] = row['notes'] or None
    if method == '统计':
        candidate['aggregation_items'] = [item.strip() for item in (row.get('统计条目') or '').split('｜') if item.strip()]
    if group == 'ablation':
        candidate['ablation_attribute'] = row.get('消融类型', '').strip()
        if candidate['ablation_attribute'] == 'alias_entity':
            candidate['ablation_metadata'] = {'original_entity': row.get('原实体', '').strip(), 'alias_expression': row.get('别名', '').strip()}
    if group == 'negative':
        if evidence:
            raise ValueError(f"{row['题号']} 负向题不填证据")
        candidate.update(negative_subtype=row.get('负向子类型', '').strip(), expected_behavior=row.get('预期行为', '').strip(),
                         expected_response=candidate['reference_answer'], acceptable_evidence=[])
        if (row.get('跨型号') or '').strip().casefold() in {'是', '跨型号', 'true', '1', 'yes'}:
            candidate['cross_model'] = True
        if row.get('criticality', '').strip():
            candidate['criticality'] = row['criticality'].strip()
    return candidate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--pool', choices=('main', 'backup'), default='main')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    from app.business_topics import validate_import_groups
    from app.corpus import CorpusStore
    from app.golden_v2 import validate_golden_candidate
    from app.reviewed_import import FRIEND_CONTRACT, import_batch, validate_friend_content
    data = args.csv.read_bytes()
    # 单元格内有换行（多段证据、分行答案），不能先 splitlines 再交给 csv。
    rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline='')))
    corpus = CorpusStore()
    chunks = corpus.chunks()
    report, candidates = [], []
    for row in rows:
        errors = []
        try:
            candidate = to_candidate(row)
            if candidate['test_category'] != 'ablation':
                validate_import_groups([candidate], corpus.index_dir.resolve())
            validate_friend_content(candidate, chunks)
            result = validate_golden_candidate(candidate, chunks)
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
        from app.config import load_values
        from app.governance import GovernanceStore
        database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
        store = GovernanceStore(database.resolve(), migrate=False)
        receipt = import_batch(store, candidates, hashlib.sha256(data).hexdigest(), str(args.csv),
                               '总指挥按朋友同款结构出题，用户 2026-11-16 授权由总指挥主导出题与审核',
                               contract=FRIEND_CONTRACT, pool=args.pool)
        summary['receipt'] = receipt
    return summary


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=1), flush=True)
