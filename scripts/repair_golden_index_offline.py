"""Controlled Q02 text staging and pending Golden association repair. No activation/Provider.

Run with --apply-links only after reviewing output; SQLite backup precedes writes.
The staged text directory deliberately has no vectors, FAISS or activation manifest.
"""
import argparse
import copy
import json
import shutil
import socket
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.full_text import checksum, validate_bundle
from app.golden_v2 import digest, normalize, validate_golden_candidate
from app.knowledge_pipeline import expand_parents, parent_child
from app.retrieval import VectorRetriever

RUN = 'GGEN-20261012120721324996'


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def database_rows(db):
    return {name: {row[0]: digest(list(row[1:])) for row in db.execute(f'SELECT rowid,* FROM "{name}"')}
            for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def repair_links(questions, plan):
    questions, plan = copy.deepcopy(questions), copy.deepcopy(plan)
    by_slot = {q['coverage_slot']: q for q in questions}
    q = by_slot['Q42']
    anchors = ['DOC-001-C-00031', 'DOC-001-C-00095']
    topics = sorted({plan['chunk_clusters'][key] for key in anchors})
    q.update(coverage_anchor_chunk_ids=anchors, related_clusters=topics, topic_cluster=topics[0])
    slot = next(s for s in plan['slots'] if s['slot_id'] == 'Q42')
    slot.update(coverage_anchor_chunk_ids=anchors, material_chunk_ids=anchors,
                related_clusters=topics, topic_cluster=topics[0], section_path='紧急停机按钮 / 按下紧急停机按钮会发生什么？')
    by_slot['Q16']['source_scope'].update(
        status='pdf_version_and_chapter_verified',
        manual_revision='DOC-002 ©2023; DOC-003 V2.1 / 2025-04-18 R1 chapter',
        pdf_pages={'DOC-002': [14], 'DOC-003': [9, 10, 11, 13]},
        chapter_page_range={'DOC-003': [9, 13]},
        power_beeps={'on': 1, 'off': 2},
        connection_indicator='R1 左侧数传灯全亮；不得套用R3指示灯',
        corpus_metadata_status='unchanged; scope persisted on pending question')
    by_slot['Q22']['source_scope'].update(
        status='pdf_version_and_chapter_verified', pdf_pages={'DOC-003': [1, 2, 4, 13]},
        chapter_page_range={'DOC-003': [2, 8]},
        power_beeps={'on': 2, 'off': 3},
        corpus_metadata_status='unchanged; scope persisted on pending question')
    plan['coverage']['anchor_topics'] = sorted({q['topic_cluster'] for q in questions})
    plan['plan_id'] = 'PLAN-' + digest({k: v for k, v in plan.items() if k != 'plan_id'})[:24]
    for q in questions:
        q['plan_id'] = plan['plan_id']
    return questions, plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply-links', action='store_true')
    args = parser.parse_args()
    # Reject every network connection, including accidental Provider or model downloads.
    def denied(*args, **kwargs):
        raise RuntimeError('Offline repair forbids network/Provider calls')
    socket.socket.connect = denied
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'before.db').exists():
        raise ValueError('Choose a fresh output directory; never overwrite an existing backup')
    index = ROOT / 'backend/data/index'
    bundle = validate_bundle(index, require_full_text=True)
    manifest, children = bundle['manifest'], bundle['chunks']
    parents = json.loads((index / 'parents.json').read_text())
    blocks = json.loads((index / 'DOC-001-blocks.json').read_text())
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        audit = json.loads(db.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?', (RUN,)).fetchone()[0])
        ids = json.loads(db.execute('SELECT question_ids_json FROM golden_generation_runs WHERE id=?', (RUN,)).fetchone()[0])
        questions = [json.loads(db.execute('SELECT raw_json FROM questions WHERE id=?', (key,)).fetchone()[0]) for key in ids]
        with sqlite3.connect(output / 'before.db') as backup:
            db.backup(backup)
        before = database_rows(db)
    assert all(q['generation_run_id'] == RUN for q in questions)
    assert audit['corpus_fingerprint'] == manifest['knowledge_identity']
    originals = copy.deepcopy(questions)
    questions, plan = repair_links(questions, audit['frozen_plan'])
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        snapshot = json.loads(db.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?', (audit['source_snapshot_id'],)).fetchone()[0])
    old_by_slot = {q['coverage_slot']: q for q in snapshot['questions']}
    lifecycle = {'id', 'generation_run_id', 'plan_id', 'source_reference', 'revision_audit', 'validation'}
    for q in questions:
        if q['revision_audit']['recommendation'] == '保留':
            assert {k: v for k, v in q.items() if k not in lifecycle} == {k: v for k, v in old_by_slot[q['coverage_slot']].items() if k not in lifecycle}
    parent = next(p for p in parents if p['chunk_id'] == 'DOC-001-P-00133')
    footnote = next(b for b in blocks if b['block_id'] == 'DOC-001-BLOCK-00690')
    assert footnote['page'] == 50 and len(footnote['raw']['image_footnote']) == 2
    import pymupdf
    document = next(d for d in bundle['documents'] if d['id'] == 'DOC-001')
    with pymupdf.open(ROOT / 'backend/documents' / document['name']) as pdf:
        for quote in footnote['raw']['image_footnote']:
            assert normalize(quote) in normalize(pdf[49].get_text())
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-small-zh-v1.5', local_files_only=True)
    counter = lambda text: len(tokenizer.encode(text, add_special_tokens=False))
    _, _, parsed = parent_child(document, [footnote['raw']], counter)
    corrected = copy.deepcopy(children)
    child = next(c for c in corrected if c['chunk_id'] == 'DOC-001-C-00134')
    restored = parsed[0]['text']
    old_text = child['text']
    new_text = old_text.replace('4. 点击用户名的输入栏\n7.', '4. 点击用户名的输入栏\n' + restored + '\n7.')
    assert new_text != old_text and counter(new_text) <= 400
    assert parent['text'] == old_text
    for item in (child, parent):
        item.update(text=new_text, chunk_text=new_text, token_count=counter(new_text))
        item['block_ids'].insert(item['block_ids'].index('DOC-001-BLOCK-00689') + 1, footnote['block_id'])
    child['embedding_status'] = 'Pending; changed text requires text-embedding-v4'
    footnote['text'] = restored
    full = copy.deepcopy(bundle['full_text'])
    page = next(p for p in full['pages'] if p['document_id'] == 'DOC-001' and p['page'] == 50)
    page['text'] = '\n'.join(b['text'] for b in blocks if b['page'] == 50)
    page['text_checksum'] = checksum(page['text'].encode())
    staging = output / 'text-staging'
    staging.mkdir(exist_ok=True)
    for name, value in [('chunks.json', corrected), ('parents.json', parents), ('DOC-001-blocks.json', blocks), ('full_text.json', full)]:
        (staging / name).write_text(encode(value) + '\n')
    assert not (staging / 'faiss.index').exists() and not (staging / 'manifest.json').exists()
    validations, preview = {}, {}
    for q in questions:
        validations[q['coverage_slot']] = validate_golden_candidate(q, children, plan, {'slot_id': q['coverage_slot'], 'seen': [p['question'] for p in questions if p is not q]})
        preview[q['coverage_slot']] = validate_golden_candidate(q, corrected)
        q['validation'] = validations[q['coverage_slot']]
        if q['coverage_slot'] == 'Q42':
            q['coverage_match'] = q['validation']['coverage_match']
    assert [k for k, v in validations.items() if not v['valid']] == ['Q02']
    assert all(v['valid'] for v in preview.values())
    retriever = VectorRetriever([])
    retriever._bundle = {'chunks': corrected}
    q02 = next(q for q in questions if q['coverage_slot'] == 'Q02')
    ranked = sorted(retriever._bm25(q02['question']).items(), key=lambda x: x[1], reverse=True)
    rank = [key for key, score in ranked].index(child['chunk_id']) + 1
    expanded = expand_parents([{**child, 'score': 1.0, 'content': child['chunk_text']}], parents, 4)
    assert all(f'{n}. ' in expanded[0]['content'] for n in range(1, 15))
    assert rank <= 12, 'Q02 not recalled by offline BM25 CandidateK=12'
    by_child = {c['chunk_id']: c for c in children}
    traces = []
    for old, q in zip(originals, questions):
        for field in ['question', 'reference_answer', 'expected_response', 'evidence', 'acceptable_evidence', 'answer_contract']:
            assert old.get(field) == q.get(field), (q['coverage_slot'], field)
        refs = q.get('source_chunk_ids', []) + q.get('coverage_anchor_chunk_ids', [])
        for key in set(refs):
            c = by_child[key]
            doc = next(d for d in bundle['documents'] if d['id'] == c['document_id'])
            assert 1 <= c['page_start'] <= c['page_end'] <= doc['pages']
            assert (ROOT / 'backend/documents' / doc['name']).is_file()
        traces.append({'question': q['coverage_slot'], 'child_ids': sorted(set(refs)), 'negative_anchor_is_evidence': False})
    revised = [q for q in questions if q['revision_audit']['recommendation'] != '保留']
    assert len(revised) == 22 and len(questions) - len(revised) == 28
    assert len({q['topic_cluster'] for q in questions}) == 9
    assets = [p for folder in [ROOT/'backend/documents', ROOT/'backend/data/index', ROOT/'backend/data/index_versions'] for p in folder.rglob('*') if p.is_file()]
    hashes = {str(p.relative_to(ROOT)): checksum(p.read_bytes()) for p in assets}
    report = {'run_id': RUN, 'formal_hard_validation': '49/50', 'text_only_preview': '50/50; no embedding/index qualification',
              'old_corpus_fingerprint': manifest['knowledge_identity'], 'new_corpus_fingerprint': None,
              'staged_text_fingerprint': digest([parents, corrected]), 'paid_calls': 0,
              'embedding_required': {'model': 'text-embedding-v4', 'dimension': 1024, 'changed_children': [child['chunk_id']],
                                     'count': 1, 'bge_tokenizer_tokens': counter(new_text), 'payload_characters': len(new_text),
                                     'billable_tokens': 'not_collected', 'query_embedding_for_live_retrieval': 1},
              'bm25_rank': rank, 'parent_steps': list(range(1, 15)), 'hybrid_vector_rerank': 'not_run',
              'counts': dict(Counter(q['test_category'] for q in questions)),
              'formal_switch': 'blocked; preserve old version until paid embedding authorized and complete bundle validated',
              'quality': 'Probe/QC/Human pending', 'backup': str(output/'before.db'), 'backup_sha256': checksum((output/'before.db').read_bytes())}
    report.update(revised_questions_preserved=22, retained_questions_preserved=28,
                  question_answer_evidence_content_unchanged=50, pdf_chunk_traceability=traces)
    (output/'working-set-preview.json').write_text(encode({'questions': questions, 'plan': plan, 'validation': validations, 'text_preview_validation': preview}))
    if args.apply_links:
        shutil.copytree(index, output/'before-index', dirs_exist_ok=True)
        with sqlite3.connect(args.database) as db:
            db.execute('BEGIN IMMEDIATE')
            assert database_rows(db) == before, 'Database changed since backup'
            for table in ['evaluation_runs', 'golden_generation_runs', 'agent_traces', 'candidate_revision_runs']:
                assert not db.execute(f"SELECT 1 FROM {table} WHERE status IN ('running','queued','coverage','generating','validation','probing','qc')").fetchone(), 'Active job'
            assert db.execute('SELECT count(*) FROM questions WHERE id IN (' + ','.join('?' for _ in ids) + ") AND (stage!='candidate' OR review_status!='human_review_pending' OR probe_status!='probe_pending' OR qc_status!='qc_pending')", ids).fetchone()[0] == 0
            now = datetime.now(timezone.utc).isoformat()
            for q in questions:
                db.execute('UPDATE questions SET raw_json=?,updated_at=? WHERE id=?', (encode(q), now, q['id']))
            audit.update(frozen_plan=plan, association_repair={'mode': 'offline', 'questions': ['Q16', 'Q22', 'Q42'], 'backup': str(output/'before.db'), 'paid_calls': 0})
            db.execute('UPDATE golden_generation_artifacts SET coverage_plan_json=?,hard_validation_json=? WHERE generation_run_id=?', (encode(plan['slots']), encode(audit), RUN))
            after = database_rows(db)
            allowed = {'questions': set(ids), 'golden_generation_artifacts': {RUN}}
            for table in before:
                assert before[table].keys() == after[table].keys()
                for rowid, value in before[table].items():
                    if value != after[table][rowid]:
                        key = db.execute(f'SELECT * FROM "{table}" WHERE rowid=?', (rowid,)).fetchone()[0]
                        assert key in allowed.get(table, set()), (table, key)
            report['history_protection'] = {'tables': len(before), 'unchanged_rows_except_current_workset_and_artifact': True}
        with sqlite3.connect(output/'before.db') as backup, sqlite3.connect(output/'rollback-verification.db') as restored_db:
            backup.backup(restored_db)
            assert database_rows(restored_db) == before
        report['rollback_backup_verified'] = True
    assert all(checksum((ROOT/name).read_bytes()) == value for name, value in hashes.items())
    report['protected_asset_files'] = len(hashes)
    (output/'asset-hashes.json').write_text(encode(hashes))
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'pdf_chunk_traceability'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
