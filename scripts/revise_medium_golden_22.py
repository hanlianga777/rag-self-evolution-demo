"""One-off, offline revision of the audited Medium snapshot. No Provider imports/calls.

Default prepares files only; --apply appends pending candidates after SQLite backup.
The original rows, snapshot, corpus, evaluations and experiments are never updated.
"""
import argparse
import copy
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.golden_v2 import digest, normalize, validate_golden_candidate

CONFIG = ROOT / 'scripts/data/golden_medium_revision_22.json'


def prepare(snapshot, chunks, config):
    assert snapshot['id'] == config['source_snapshot_id']
    revisions = {r['question_number']: r for r in config['revisions']}
    assert len(revisions) == 22
    assert Counter(r['recommendation'] for r in revisions.values()) == {'轻量修订': 17, '实质修订': 4, '替换': 1}
    questions = sorted(snapshot['questions'], key=lambda q: q['coverage_slot'])
    assert len(questions) == 50
    plan = copy.deepcopy(snapshot['coverage_plan'])
    plan['source_plan_id'] = plan['plan_id']
    now = datetime.now(timezone.utc).isoformat()
    run_id = 'GGEN-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
    work = []
    for original in questions:
        q = copy.deepcopy(original)
        number = q['coverage_slot']
        q.update(copy.deepcopy(revisions.get(number, {}).get('changes', {})))
        if number in revisions:
            q['acceptable_evidence'] = copy.deepcopy(q['evidence'])
            q['source_chunk_ids'] = list(dict.fromkeys(i for e in q['evidence'] for i in e['source_chunk_ids']))
            anchors = q.get('coverage_anchor_chunk_ids') if q['test_category'] == 'negative' else q['source_chunk_ids']
            topics = sorted({plan['chunk_clusters'][i] for i in anchors})
            q['related_clusters'] = topics
            q['topic_cluster'] = q['topic_cluster'] if q['topic_cluster'] in topics else topics[0]
            slot = next(s for s in plan['slots'] if s['slot_id'] == number)
            slot.update(topic_cluster=q['topic_cluster'], related_clusters=topics, material_chunk_ids=anchors,
                        coverage_anchor_chunk_ids=anchors, evidence_chunk_ids=q['source_chunk_ids'], difficulty=q['difficulty'])
        q.update(id=f'V1G-{run_id[-12:]}-{number[1:]}', generation_run_id=run_id,
                 source_reference={'type': 'snapshot_revision_copy', 'snapshot_id': snapshot['id'], 'question_id': original['id']},
                 revision_audit={'mode': 'offline_human_authored', 'source_snapshot_id': snapshot['id'],
                                 'source_question_id': original['id'], 'source_content_hash': digest(original),
                                 'recommendation': revisions.get(number, {}).get('recommendation', '保留'),
                                 'problem': revisions.get(number, {}).get('problem'), 'paid_calls': 0})
        work.append(q)
    q10 = next(q['id'] for q in work if q['coverage_slot'] == 'Q10')
    next(q for q in work if q['coverage_slot'] == 'Q25')['source_positive_id'] = q10
    plan.update(status='revision_draft', created_at=now)
    plan['coverage'] = {**plan.get('coverage', {}), 'anchor_topics': sorted({q['topic_cluster'] for q in work})}
    plan['plan_id'] = 'PLAN-' + digest(plan)[:24]
    validations = {}
    for q in work:
        result = validate_golden_candidate(q, chunks, plan, {'slot_id': q['coverage_slot'], 'seen': [p['question'] for p in work if p is not q]})
        q.update(plan_id=plan['plan_id'], validation=result)
        # Retained content/provenance stays verbatim; only current validation is new.
        if q['coverage_slot'] in revisions:
            q.update(evidence_locations=result['evidence_locations'], coverage_match=result['coverage_match'])
        validations[q['coverage_slot']] = result
    assert Counter(q['test_category'] for q in work) == {'positive': 20, 'ablation': 10, 'negative': 20}
    assert len({normalize(q['question']) for q in work}) == 50
    return {'id': run_id, 'created_at': now, 'source_snapshot_id': snapshot['id'], 'questions': work,
            'plan': plan, 'validations': validations, 'revision_digest': digest(config),
            'counts': dict(Counter(q['test_category'] for q in work)),
            'topics': dict(sorted(Counter(q['topic_cluster'] for q in work).items())),
            'hard_validation': {'status': 'passed' if all(v['valid'] for v in validations.values()) else 'blocked',
                                'blocked_questions': {k: v['blocking_errors'] for k, v in validations.items() if not v['valid']}},
            'probe_qc': 'not_run', 'human_gate': 'pending'}


def append_working_set(database, draft, output):
    """Append atomically; refuse active jobs and repeat import. Backup before writes."""
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        if any(json.loads(r[0]).get('revision_digest') == draft['revision_digest'] for r in connection.execute('SELECT hard_validation_json FROM golden_generation_artifacts')):
            raise ValueError('此修订包已入库，不重复追加')
        with sqlite3.connect(output / 'before.db') as backup:
            connection.backup(backup)
        connection.execute('BEGIN IMMEDIATE')
        for table, statuses in [('evaluation_runs', ['running','queued']), ('golden_generation_runs', ['queued','coverage','generating','validation','probing','qc']), ('agent_traces', ['running']), ('candidate_revision_runs', ['running'])]:
            if connection.execute(f"SELECT 1 FROM {table} WHERE status IN ({','.join('?' for _ in statuses)}) LIMIT 1", statuses).fetchone():
                raise ValueError('存在活动任务，未写入')
        now, run = draft['created_at'], draft['id']
        profile = {'name':'medium','positive_count':20,'ablation_count':10,'negative_count':20,'expected_count':50}
        encode = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
        status = 'completed' if draft['hard_validation']['status'] == 'passed' else 'failed'
        connection.execute('INSERT INTO golden_generation_runs VALUES (?,?,?,?,?,?)', (run,encode(profile),'offline-audited-revision',status,encode([q['id'] for q in draft['questions']]),now))
        audit = {'status':draft['hard_validation']['status'], 'hard_validation':draft['hard_validation'],
                 'revision_digest':draft['revision_digest'], 'source_snapshot_id':draft['source_snapshot_id'],
                 'corpus_fingerprint':draft['plan']['corpus_fingerprint'], 'frozen_plan':draft['plan'],
                 'offline_revision':True, 'quality_not_run':True, 'paid_calls':0,
                 'progress':{'stage':status,'completed_slots':50,'total_slots':50,'finished_at':now},
                 'counts':draft['counts']}
        if status == 'failed':
            audit.update(failed_stage='validation', error='离线修订已保存50题；正式Corpus证据缺失，Hard Validation阻断，未执行Probe/QC')
        question_plan = [{'question_id':q['id'],'coverage_slot':q['coverage_slot'],'test_category':q['test_category'],'negative_subtype':q.get('negative_subtype'),'ablation_attribute':q.get('ablation_attribute')} for q in draft['questions']]
        connection.execute('INSERT INTO golden_generation_artifacts VALUES (?,?,?,?)', (run,encode(draft['plan']['slots']),encode(question_plan),encode(audit)))
        for q in draft['questions']:
            connection.execute('INSERT INTO questions (id,stage,legacy_question_type,test_category,negative_subtype,review_status,probe_status,qc_status,question,reference_answer,evidence_json,raw_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (q['id'],'candidate','v1_mini',q['test_category'],q.get('negative_subtype'),'human_review_pending','probe_pending','qc_pending',q['question'],q.get('reference_answer'),encode(q['evidence']),encode(q),now,now))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    with sqlite3.connect(args.source_database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        row = connection.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?', (config['source_snapshot_id'],)).fetchone()
        if not row: raise ValueError('找不到当前审计Snapshot')
        snapshot = json.loads(row[0])
    chunks = json.loads((ROOT / 'backend/data/index/chunks.json').read_text())
    draft = prepare(snapshot, chunks, config)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'working-set.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2)+'\n')
    if args.apply: append_working_set(args.source_database, draft, args.output)
    print(json.dumps({k:draft[k] for k in ['id','counts','topics','hard_validation','probe_qc','human_gate']}, ensure_ascii=False))


if __name__ == '__main__': main()
