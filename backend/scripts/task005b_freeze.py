#!/usr/bin/env python3
"""Task 005B CSV adapter. Preparation/export are offline; writes use product APIs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.task005_golden_check import parse_evidence, parse_requirements
from app.scoring_contract import compile_contract
from app.golden_v2 import validate_content_sources

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '指挥/报告/005B-数据'
# Human-reviewed correspondence: each tuple identifies the CSV evidence paragraph(s)
# supporting that required point. Q17's second point is expanded into explicit OR.
SUPPORT = [
    [(1,), (2,)], [(1,)], [(1,), (2,), (3,)], [(1,), (2,), (2,)], [(1,)],
    [(1,), (2,), (3,)], [(1,), (2,), (2,)], [(1,), (1,), (2,)], [(1,), (1,), (1,)], [(1,), (2,)],
    [(1,)], [(1,), (2,)], [(1,), (3,), (2,)], [(1,)], [(1,), (2,), (3,)],
    [(1,), (1,), (2,)], [(1, 2), (1, 2)], [(1,), (1,), (1,)], [(1,)], [(1,), (1,)],
    [(1,), (2,), (3,)], [(1,), (1,)], [(1,), (2,), (2,)], [(2,), (1,), (2,)], [(2,), (1,), (3,)],
    [(1,), (1,)], [(1,), (1,), (1,)], [(1,), (2,), (2,)], [(1,), (2,), (3,)], [(1,), (2,)],
]


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def build_candidates(path, index_dir):
    rows = read_csv(path)
    if [r['题号'] for r in rows] != [f'Q{i:02}' for i in range(1, 51)]:
        raise ValueError('Need ordered Q01-Q50')
    chunks = json.loads((Path(index_dir) / 'chunks.json').read_text())
    strict = lambda text: re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))
    candidates = []
    for serial, row in enumerate(rows):
        qid = row['题号']
        group = {'正向': 'positive', '消融': 'ablation', '负向': 'negative'}[row['题型']]
        subtype = {'safe_rejection': 'safety_critical', 'prompt_injection_resistance': 'prompt_injection'}.get(row['负向子类'], row['负向子类']) or None
        behavior = {'safety_critical': 'safe_rejection', 'prompt_injection': 'prompt_injection_resistance'}.get(subtype, subtype)
        sources, evidence, numbered = [], [], {}
        claims = dict(parse_evidence(row['证据所在文档和页码']))
        for number, quote in parse_evidence(row['标准证据原文（逐字）']):
            matches = [c for c in chunks if strict(quote) in strict(c.get('chunk_text') or c['text'])
                       and c['document_name'] in claims[number]]
            if not matches:
                raise ValueError(f'{qid} evidence {number} not verbatim in child')
            child = sorted(matches, key=lambda c: c['chunk_id'])[0]
            key = child['chunk_id']; numbered[int(number)] = key
            sources.append({'chunk_id': key, 'quote': quote, 'role': 'canonical_norm',
                            'evidence_number': number, 'csv_location': claims[number],
                            **{k: child[k] for k in ('document_id', 'document_name', 'page_start', 'page_end')}})
            evidence.append({'source_chunk_ids': [key], 'evidence_key_points': [quote]})
        required = []
        for i, point in enumerate(parse_requirements(row['必答要点']), 1):
            ids = list(dict.fromkeys(numbered[n] for n in SUPPORT[serial][i-1])) if group != 'negative' else list(dict.fromkeys(numbered.values()))
            entry = {'id': f'{qid}-R{i}', 'requirement': point, 'source_chunk_ids': ids,
                     'matching': 'semantic_equivalence_not_exact_text'}
            if group == 'negative':
                entry['basis'] = {'safety_critical': 'safety_norm', 'prompt_injection': 'instruction_boundary',
                                  'clarify': 'missing_information', 'insufficient_evidence': 'corpus_boundary_review'}[subtype]
            if qid == 'Q17' and i == 2:
                entry.update(logic='OR', atoms=[
                    {'id': 'Q17-R2.R3', 'requirement': 'R3连接成功后右侧DL指示灯亮', 'source_chunk_ids': [numbered[1]]},
                    {'id': 'Q17-R2.R1', 'requirement': 'R1连接成功后左侧数据传输灯全亮', 'source_chunk_ids': [numbered[2]]}])
            required.append(entry)
        req = {'required_checks': required, 'conditional_checks': [], 'sources': sources,
               'answer_support': [], 'auxiliary_information': [row['加分项']] if row['加分项'] else [],
               'prohibited': [row['禁止项']] if row['禁止项'] else [],
               'acceptable_equivalents': [row['等价说法']] if row['等价说法'] else []}
        candidate = {'display_id': qid, 'coverage_slot': qid, 'question': row['问题'],
                     'reference_answer': row['标准答案全文'], 'expected_response': row['标准答案全文'],
                     'test_category': group, 'evaluation_group': group,
                     'negative_subtype': subtype, 'expected_behavior': behavior if group == 'negative' else None,
                     'construction_type': 'Ordinary', 'ablation_attribute': 'colloquial' if group == 'ablation' else None,
                     'business_requirements': req, 'evidence': evidence, 'acceptable_evidence': evidence,
                     'source_reference': {'source': '任务005修订稿/定稿', 'question_id': qid,
                                          'change_type': row['改动类型'], 'change_note': row['改动说明']},
                     'csv_format': {'required_cell': row['必答要点'], 'original_required': row['原必答要点']}}
        result = validate_content_sources(candidate, chunks)
        if result['status'] != 'passed':
            raise ValueError(f'{qid}: {result}')
        compile_contract(candidate)
        candidates.append(candidate)
    return candidates


def export_snapshot(snapshot, output, fields):
    rows = []
    for raw in snapshot['questions']:
        req = raw['business_requirements']; ref = raw['source_reference']
        # The original cell retains its approved formatting. Verify it describes
        # exactly the persisted role entries before exporting.
        cell = raw['csv_format']['required_cell']
        if parse_requirements(cell) != [r['requirement'] for r in req['required_checks']]:
            raise ValueError('CSV required text diverged from scoring structure')
        rows.append(dict(zip(fields, [raw['display_id'], {'positive': '正向', 'ablation': '消融', 'negative': '负向'}[raw['test_category']],
            {'safety_critical': 'safe_rejection', 'prompt_injection': 'prompt_injection_resistance'}.get(raw.get('negative_subtype'), raw.get('negative_subtype')) or '',
            raw['question'], raw.get('reference_answer') or raw.get('expected_response', ''), cell, '\n'.join(req['auxiliary_information']),
            '\n'.join(req['prohibited']), '\n'.join(req['acceptable_equivalents']),
            '\n\n'.join('【证据 '+s['evidence_number']+'】\n'+s['quote'] for s in req['sources']),
            '\n'.join('【证据 '+s['evidence_number']+'】'+s['csv_location'] for s in req['sources']),
            ref['change_type'], ref['change_note'], raw['csv_format']['original_required']])))
    with Path(output).open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator='\n'); writer.writeheader(); writer.writerows(rows)
    return rows


def api(path, payload=None):
    request = Request('http://127.0.0.1:8010'+path, data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
                      headers={'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1:5174'})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Import, human-confirm and freeze through product endpoints')
    args = parser.parse_args()
    path = DATA / '定稿50.csv'; candidates = build_candidates(path, ROOT / 'backend/data/index')
    if not args.apply:
        print(json.dumps({'compiled': len(candidates), 'paid_calls': 0})); return
    imported = api('/api/governance/reviewed-import', {'candidates': candidates,
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source': '任务005修订稿/定稿', 'review_note': '任务005修订稿已由总指挥审定，红线清单已由用户确认；005B三处修改按任务单执行'})
    api('/api/governance/review-batch', {'question_ids': imported['question_ids'],
        'actor': '用户（对话中确认，Codex 代为执行）', 'confirmed_manual_review': True, 'reason': '任务005红线清单已确认'})
    snapshot = api('/api/governance/generation-runs/'+imported['generation_run_id']+'/snapshot', {})
    rows = export_snapshot(snapshot, DATA / '新题卷50.csv', list(read_csv(path)[0]))
    if rows != read_csv(path):
        raise ValueError('Frozen export differs from approved CSV')
    print(json.dumps({'snapshot_id': snapshot['id'], 'generation_run_id': imported['generation_run_id'], 'compiled': len(rows), 'export_equal': True, 'paid_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
