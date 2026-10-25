"""Read-only offline draft audit. No app imports, Provider calls or database writes."""
import argparse
import copy
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate(draft, snapshot, chunks, manifest):
    errors = []
    def check(condition, message):
        if not condition:
            errors.append(message)
    records = draft['questions']
    by_id = {c['chunk_id']: c for c in chunks}
    originals = {q['id']: q for q in snapshot['questions']}
    check(draft['status'] == 'draft_pending_human_review', 'must remain a draft')
    check(draft['source_snapshot_id'] == snapshot['id'], 'snapshot identity')
    check(draft['source_snapshot_sha256'] == digest(snapshot), 'snapshot hash')
    check(draft['source_corpus_identity'] == snapshot['corpus_fingerprint'] == manifest['knowledge_identity'], 'corpus identity')
    check(draft['scope'] == {'provider_calls': 0, 'database_writes': 0, 'frozen': False, 'approved': False, 'judge_rules_changed': False, 'production_imported': False}, 'draft scope')
    check(len(records) == len({r['number'] for r in records}) == len({r['question_id'] for r in records}) == 50, '50 unique questions')
    check({r['number'] for r in records} == {f'Q{i:02}' for i in range(1, 51)}, 'slot coverage')
    check({r['question_id'] for r in records} == set(snapshot['question_ids']), 'question membership')
    check(Counter(r['test_category'] for r in records) == {'positive': 20, 'ablation': 10, 'negative': 20}, '20/10/20 quota')
    for record in records:
        label = record['number']
        q = originals.get(record['question_id'])
        if q is None:
            errors.append(label + ': unknown question id')
            continue
        old, new = record['original'], record['vnext']
        check(old['question_sha256'] == digest(q), label + ': original question hash')
        check(record['question'] == q['question'] and record['number'] == q['coverage_slot'], label + ': original wording/slot')
        for field in ('test_category', 'negative_subtype', 'user_intent'):
            check(record.get(field) == q.get(field), label + ': preserved ' + field)
        for field, value in record['preserved_context'].items():
            check(value == q.get(field), label + ': preserved ' + field)
        for field in ('reference_answer', 'expected_behavior', 'source_chunk_ids', 'evidence', 'acceptable_evidence', 'coverage_anchor_chunk_ids', 'evidence_locations', 'validation'):
            check(old[field] == q.get(field), label + ': original ' + field)
        canonical_ids = list(dict.fromkeys(i for e in q.get('evidence', []) for i in e['source_chunk_ids']))
        check(record['provenance_audit']['canonical_ids'] == canonical_ids, label + ': canonical identity')
        mismatch = set(q.get('source_chunk_ids', [])) != set(canonical_ids)
        check(record['provenance_audit']['top_level_vs_canonical_mismatch'] == mismatch, label + ': provenance mismatch flag')
        check(new['business_verdicts'] == ['PASS', 'FAIL'] and new['format_is_failure_criterion'] is False, label + ': binary intent contract')
        check(new['expected_behavior'] == q.get('expected_behavior'), label + ': expected behavior')
        if q['test_category'] == 'negative':
            check(new['reference_answer'] is None and not new['answer_support'], label + ': negative must not have ordinary answer')
        else:
            check(isinstance(new['reference_answer'], str) and bool(new['reference_answer'].strip()), label + ': missing draft answer')
            check(new['reference_answer'] != q.get('reference_answer'), label + ': answer not governed')
            check(bool(canonical_ids) and bool(new['answer_support']), label + ': answer without Canonical provenance')
            check([s['answer_line'] for s in new['answer_support']] == new['reference_answer'].splitlines(), label + ': answer support coverage')
            for artifact in ('Lorem ipsum', '\ue258', '类型=', '<sub>', '\\~'):
                check(artifact not in new['reference_answer'], label + ': OCR artifact in answer')
        check(bool(new['required_checks']) and bool(new['prohibited']) and bool(new['acceptable_equivalents']), label + ': missing governance')
        sources = {src['chunk_id']: src for src in record['sources']}
        check(set(canonical_ids + q.get('coverage_anchor_chunk_ids', [])) <= set(sources), label + ': missing original sources')
        for key, src in sources.items():
            chunk = by_id.get(key)
            if chunk is None:
                errors.append(label + ': missing source ' + key)
                continue
            check(src['quote'] == chunk['chunk_text'], label + ': changed quote ' + key)
            check(src['body_sha256'] == hashlib.sha256(chunk['chunk_text'].encode()).hexdigest(), label + ': quote hash ' + key)
            check(src['document_id'] == chunk['document_id'] and src['document'] == chunk['document_name'] and src['product'] == chunk.get('product') and src['version'] == chunk.get('version'), label + ': source scope ' + key)
            check(src['pages'] == [chunk['page_start'], chunk['page_end']] and src['parent_chunk_id'] == chunk.get('parent_chunk_id'), label + ': source location ' + key)
            expected_role = 'canonical_norm' if key in canonical_ids else 'material_anchor_only' if key in q.get('coverage_anchor_chunk_ids', []) else 'draft_supplement_only'
            check(src['role'] == expected_role, label + ': source role ' + key)
        checks = new['required_checks'] + new['conditional_checks']
        check(len({v['id'] for v in checks}) == len(checks), label + ': duplicate checkpoint')
        for value in checks + new['answer_support']:
            refs = value['source_chunk_ids']
            check(bool(refs) and set(refs) <= set(sources), label + ': checkpoint/answer references')
        for value in new['conditional_checks']:
            check(bool(value['trigger']) and bool(value['requirement']), label + ': empty condition')
        check(record['validation']['human_review'] == 'pending' and record['validation']['probe_qc'] == 'not_run', label + ': review not granted')
    return errors


def render_review(draft):
    lines = ['# Golden VNext：Medium50逐题治理草案', '',
             '状态：离线内容草案，待人工复核；不是新的Frozen Golden，也未执行Probe/QC或Judge。', '',
             f"原Snapshot：`{draft['source_snapshot_id']}`；工作Run：`{draft['source_generation_run_id']}`。正向20／消融10／负向20，原问题、ID、难度与场景不变。", '',
             '判定仅PASS／FAIL。必答按语义和用户意图核对，不逐字匹配；条件项仅在触发时适用，辅助项遗漏不单独失败。拒答后的附带操作仍需安全、适用。格式和长度不是正确性判据。', '',
             '来源：Canonical沿现有`full_norms`读取嵌套evidence；负向Anchor只标主题。新增补充来源仅供草案复核，不改历史来源。完整原记录摘要哈希、证据和既有审核事件见JSON。所有引用保留完整Chunk原文，因此源文中的OCR不代表新版答案仍有OCR。', '',
             '离线验证只证明身份、配额、字段保护及引文真实性；答案与检查点的语义适用性由逐题离线阅读形成草案，未获得人工批准或真实模型验收。', '']
    for r in draft['questions']:
        v, old = r['vnext'], r['original']
        lines += [f"## {r['number']} · {r['test_category']} · `{r['question_id']}`", '',
                  '**原问题：** ' + r['question'], '', '**核心意图：** ' + r['governed_intent'], '',
                  '**保留场景与难度：** ' + json.dumps(r['preserved_context'], ensure_ascii=False), '',
                  '**旧版参考答案／预期行为：**', '', '```text', old['reference_answer'] or old['expected_behavior'], '```', '',
                  '**VNext参考答案：**' if v['reference_answer'] else '**VNext预期行为（无普通参考答案）：**', '',
                  v['reference_answer'] or (v['expected_behavior'] + '：' + r['governed_intent']), '', '**必答检查点：**', '']
        lines += ['- ' + c['id'] + '：' + c['requirement'] + '（来源：' + '、'.join(c['source_chunk_ids']) + '）' for c in v['required_checks']]
        lines += ['', '**条件必答项：**', '']
        lines += ['- ' + c['trigger'] + ' → ' + c['requirement'] for c in v['conditional_checks']] or ['无额外条件项；适用安全约束仍按下列禁用操作检查。']
        for title, values in [('辅助信息', v['auxiliary_information']), ('禁止错误／不安全操作', v['prohibited']), ('同义／等价表达示例', v['acceptable_equivalents'])]:
            lines += ['', '**' + title + '：**', ''] + (['- ' + x for x in values] or ['无单独辅助项。'])
        lines += ['', '**来源与关键证据：**', '']
        for src in r['sources']:
            lines += [f"- `{src['chunk_id']}` / {src['document']} / 页{src['pages'][0]}–{src['pages'][1]} / {src['product']} / {src['role']}；版本：{src['version'] or '元数据未提供，不推定'}", '', '```text', src['quote'], '```', '']
        lines += ['**具体修改：** ' + r['change_note'], '', '**来源差异：** ' + ('原顶层ID：' + '、'.join(old['source_chunk_ids']) + '；Canonical ID：' + '、'.join(r['provenance_audit']['canonical_ids']) if r['provenance_audit']['top_level_vs_canonical_mismatch'] else '未发现顶层与嵌套evidence ID集合不一致。'), '',
                  '**校验与审核状态：** 结构与引文验证通过；离线内容审阅已形成草案；人工待审；Probe/QC未执行。原题审核状态：' + json.dumps(old['review_state'], ensure_ascii=False), '',
                  '**待人工复核：** ' + ('；'.join(r['validation']['issues']) if r['validation']['issues'] else '复核新版语义完整性、必答项分级及等价表达；本轮不自动批准。'), '']
        if 'existing_hard_validation' in r['validation']:
            lines += ['**现有Hard Validation原样执行结果：**', '', '```json', json.dumps(r['validation']['existing_hard_validation'], ensure_ascii=False, indent=2), '```', '']
        if 'corpus_boundary_observation' in r['validation']:
            lines += ['**全Corpus边界检索观察：**', '', '```json', json.dumps(r['validation']['corpus_boundary_observation'], ensure_ascii=False, indent=2), '```', '']
    return '\n'.join(line.rstrip() for line in '\n'.join(lines).splitlines()).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-database', type=Path, required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--render-review', action='store_true')
    args = parser.parse_args()
    draft = json.loads((ROOT / 'docs/GOLDEN_VNEXT_50_DRAFT.json').read_text())
    with sqlite3.connect(args.source_database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        snapshot = json.loads(connection.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?', (draft['source_snapshot_id'],)).fetchone()[0])
    index = ROOT / 'backend/data/index'
    chunks = json.loads((index / 'chunks.json').read_text())
    manifest = json.loads((index / 'manifest.json').read_text())
    errors = validate(draft, snapshot, chunks, manifest)
    assert draft['corpus_chunks_sha256'] == hashlib.sha256((index / 'chunks.json').read_bytes()).hexdigest(), 'chunks artifact hash'
    assert not errors, '\n'.join(errors)
    if args.self_test:
        mutations = [lambda d: d['questions'][0].update(question='篡改原题'),
                     lambda d: d['questions'][1].update(question_id=d['questions'][0]['question_id']),
                     lambda d: d['questions'][30]['vnext'].update(reference_answer='虚假普通答案'),
                     lambda d: d['questions'][0]['sources'][0].update(quote='伪造来源'),
                     lambda d: d['questions'][41]['vnext'].update(expected_behavior='safe_rejection'),
                     lambda d: d['questions'][0]['vnext']['required_checks'][0].update(source_chunk_ids=['missing'])]
        for mutation in mutations:
            broken = copy.deepcopy(draft)
            mutation(broken)
            assert validate(broken, snapshot, chunks, manifest), 'corruption was not detected'
        assert all(line == line.rstrip() for line in render_review(draft).splitlines()), 'rendered trailing whitespace'
    if args.render_review:
        (ROOT / 'docs/GOLDEN_VNEXT_50_REVIEW.md').write_text(render_review(draft))
    print(json.dumps({'questions': 50, 'answerable': 30, 'negative': 20, 'quota': '20/10/20', 'structural_and_quote_validation': 'passed', 'corruption_checks': 6 if args.self_test else 0, 'semantic_human_review': 'pending', 'provider_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
