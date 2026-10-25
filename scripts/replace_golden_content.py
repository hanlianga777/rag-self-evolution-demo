"""One-off, scoped Golden replacement. Default prepares; --apply backs up then transacts.

No Provider, approval, freezing, index writes or evaluation execution. Prior artifacts
and all removed records remain recoverable in a verified SQLite Backup API snapshot.
"""
import argparse
import copy
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.golden_v2 import digest, validate_golden_candidate


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def database_audit(connection):
    return {r[0]: {'count': connection.execute('SELECT count(*) FROM "' + r[0] + '"').fetchone()[0],
                  'sha256': digest([tuple(v) for v in connection.execute('SELECT * FROM "' + r[0] + '" ORDER BY rowid')])}
            for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}


def require_idle(connection):
    for table, statuses in [('evaluation_runs', ['running', 'queued']), ('golden_generation_runs', ['queued', 'coverage', 'generating', 'validation', 'probing', 'qc']),
                            ('candidate_revision_runs', ['queued', 'generating', 'validating', 'probing', 'qc']), ('agent_traces', ['running'])]:
        if connection.execute(f"SELECT 1 FROM {table} WHERE status IN ({','.join('?' for _ in statuses)}) LIMIT 1", statuses).fetchone():
            raise ValueError('存在活动任务，禁止替换或归档：' + table)


def prepare(connection, draft, chunks, manifest):
    source = json.loads(connection.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?', (draft['source_snapshot_id'],)).fetchone()[0])
    assert digest(source) == draft['source_snapshot_sha256'], '原Snapshot已变化'
    assert source['corpus_fingerprint'] == manifest['knowledge_identity'] == draft['source_corpus_identity']
    ids = source['question_ids']
    assert len(ids) == len(set(ids)) == len(draft['questions']) == 50
    assert set(ids) == {q['question_id'] for q in draft['questions']}
    by_source = {q['id']: q for q in source['questions']}
    content_id = 'GCONTENT-' + digest({'content': [q['vnext'] for q in draft['questions']], 'question_ids': ids, 'corpus': manifest['knowledge_identity']})[:24]
    run_id, snapshot_id = 'GGEN-' + content_id, 'GD-' + content_id
    now = datetime.now(timezone.utc).isoformat()
    questions, validations = [], {}
    for record in draft['questions']:
        key = record['question_id']; old = by_source[key]; v = record['vnext']
        row = connection.execute('SELECT question,reference_answer,evidence_json,raw_json FROM questions WHERE id=?', (key,)).fetchone()
        if not row or row[0] != old['question'] or row[1] != old.get('reference_answer') or json.loads(row[2]) != old['evidence']:
            raise ValueError('工作题目已变化或已替换：' + key)
        assert record['question'] == old['question'] and record['test_category'] == old['test_category']
        assert v['expected_behavior'] == old.get('expected_behavior')
        assert v['business_verdicts'] == ['PASS', 'FAIL'] and v['format_is_failure_criterion'] is False
        assert v['reference_answer'] is None if old['test_category'] == 'negative' else bool(v['reference_answer'])
        raw = copy.deepcopy(old)
        # Coverage/topic anchors remain distinct; only actual answer Evidence is flattened.
        selected = [s for s in record['sources'] if s['role'] != 'material_anchor_only']
        evidence = [] if old['test_category'] == 'negative' else [
            {'source_chunk_ids': [s['chunk_id']], 'evidence_key_points': [s['quote']],
             'document_id': s['document_id'], 'product': s['product'], **({'version': s['version']} if s.get('version') else {})} for s in selected]
        requirements = {k: copy.deepcopy(v[k]) for k in ('required_checks', 'conditional_checks', 'auxiliary_information', 'prohibited', 'acceptable_equivalents', 'answer_support', 'business_verdicts', 'format_is_failure_criterion')}
        requirements['sources'] = copy.deepcopy(selected)
        # Negative behavior is grounded in its actual missing information/corpus/instruction boundary.
        # The stored Topic anchor stays in raw; it is never fabricated answer Evidence.
        requirements['corpus_review_scope'] = copy.deepcopy(manifest['knowledge_identity'])
        raw.update(reference_answer=v['reference_answer'], evidence=evidence, acceptable_evidence=copy.deepcopy(evidence),
                   source_chunk_ids=list(dict.fromkeys(i for e in evidence for i in e['source_chunk_ids'])),
                   business_requirements=requirements, generation_run_id=run_id, generation_method='offline_content_revision', generation_model=None,
                   content_identity=content_id,
                   content_revision={'source_snapshot_id': source['id'], 'source_generation_run_id': source['generation_run_id'],
                                     'original_question_sha256': digest(old), 'edited_at': now,
                                     'authored_by': 'Codex', 'human_approval': False,
                                     'source_field_disposition': 'answer ids regenerated from Evidence; persisted Topic anchors unchanged'})
        validation = validate_golden_candidate(raw, chunks, source['coverage_plan'], {'slot_id': raw['coverage_slot']})
        if validation['source_validation']['status'] != 'passed' or set(validation['blocking_errors']) != {'answer content requires human review'}:
            raise ValueError(key + ': ' + encode(validation['blocking_errors']))
        raw.update(validation={k: value for k, value in validation.items() if k != 'normalized_candidate'}, evidence_locations=validation['evidence_locations'])
        questions.append(raw); validations[key] = raw['validation']
    assert {category: sum(q['test_category'] == category for q in questions) for category in ('positive','ablation','negative')} == {'positive':20,'ablation':10,'negative':20}
    old_runs = [r[0] for r in connection.execute('SELECT id FROM golden_generation_runs')]
    all_questions = [r[0] for r in connection.execute('SELECT id FROM questions')]
    if any(r[0] not in old_runs for r in connection.execute("SELECT DISTINCT json_extract(raw_json,'$.generation_run_id') FROM questions")):
        raise ValueError('存在独立来源题目，不能扩大归档范围')
    old_snapshots = [r[0] for r in connection.execute("SELECT id FROM dataset_versions WHERE status='approved'")]
    eval_ids = [r[0] for r in connection.execute('SELECT id FROM evaluation_runs WHERE dataset_version_id IN (' + ','.join('?' for _ in old_snapshots) + ')', old_snapshots)]
    if connection.execute('SELECT count(*) FROM evaluation_runs').fetchone()[0] != len(eval_ids):
        raise ValueError('存在独立评测，需缩小清理范围')
    experiment_ids = [r[0] for r in connection.execute('SELECT id FROM experiments WHERE baseline_run_id IN (' + ','.join('?' for _ in eval_ids) + ')', eval_ids)]
    # Never remove records bound to releases, approvals or rollback lineage.
    if connection.execute('SELECT 1 FROM production_versions WHERE evaluation_run_id IS NOT NULL OR dataset_version_id IS NOT NULL LIMIT 1').fetchone():
        raise ValueError('发现历史发布绑定；停止删除，需改为定向归档方案')
    snapshot = {'id': snapshot_id, 'content_identity': content_id, 'generation_run_id': run_id,
                'profile': source['profile'], 'questions': questions, 'question_ids': ids,
                'corpus_fingerprint': source['corpus_fingerprint'], 'coverage_plan': source['coverage_plan'],
                'status': 'draft_pending_review', 'human_review': 'pending', 'probe_qc': 'not_run', 'frozen': False}
    return {'content_id': content_id, 'run_id': run_id, 'snapshot': snapshot, 'questions': questions,
            'validations': validations, 'old_runs': old_runs, 'old_snapshots': old_snapshots,
            'old_questions': all_questions, 'evaluation_ids': eval_ids, 'experiment_ids': experiment_ids, 'created_at': now}


def apply(connection, plan, output):
    before = database_audit(connection)
    require_idle(connection)
    backup_path = output / 'before.db'
    with closing(sqlite3.connect(backup_path)) as backup:
        connection.backup(backup)
        assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert database_audit(backup) == before
    backup_sha256 = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    # Persist recovery evidence before the first mutation.
    (output / 'backup-manifest.json').write_text(json.dumps({'backup': str(backup_path.resolve()), 'sha256': backup_sha256, 'tables': before}, ensure_ascii=False, indent=2)+'\n')
    # Independent audit remains recoverable even when existing startup retention
    # later prunes references to retired questions or experiments.
    columns = {t: [r[1] for r in connection.execute('PRAGMA table_info(' + t + ')')] for t in ('approvals', 'review_events')}
    audit_archive = {t: [dict(zip(columns[t], r)) for r in connection.execute('SELECT * FROM ' + t + ' ORDER BY id')] for t in columns}
    (output / 'original-audit-records.json').write_text(json.dumps(audit_archive, ensure_ascii=False, indent=2)+'\n')
    connection.execute('BEGIN IMMEDIATE')
    try:
        require_idle(connection)
        assert database_audit(connection) == before, '备份后数据库变化，停止写入'
        preserved = {t: before[t] for t in ('approvals','production_versions','rollback_history','alias_mappings','tool_registry','monitoring_events')}
        removed = {}
        def delete(table, field, ids):
            if not ids: return
            marks=','.join('?' for _ in ids)
            removed[table] = connection.execute(f'DELETE FROM {table} WHERE {field} IN ({marks})', ids).rowcount
        delete('recommendations','experiment_id',plan['experiment_ids'])
        for table in ('tool_calls','agent_traces','candidate_configs'): delete(table,'experiment_id',plan['experiment_ids'])
        for table in ('bad_cases','evaluation_case_results'): delete(table,'run_id',plan['evaluation_ids'])
        delete('experiments','id',plan['experiment_ids'])
        delete('evaluation_runs','id',plan['evaluation_ids'])
        for table in ('probe_results','qc_results','question_quality_audits'): delete(table,'question_id',plan['old_questions'])
        delete('candidate_revision_runs','generation_run_id',plan['old_runs'])
        delete('golden_generation_artifacts','generation_run_id',plan['old_runs'])
        delete('golden_generation_runs','id',plan['old_runs'])
        keep = {q['id'] for q in plan['questions']}
        delete('questions','id',[i for i in plan['old_questions'] if i not in keep])
        for key in plan['old_snapshots']:
            connection.execute("UPDATE dataset_versions SET status='archived' WHERE id=?", (key,))
        for q in plan['questions']:
            connection.execute("UPDATE questions SET stage='candidate',review_status='human_review_pending',probe_status='probe_pending',qc_status='qc_pending',reference_answer=?,evidence_json=?,raw_json=?,updated_at=? WHERE id=?", (q.get('reference_answer'),encode(q['evidence']),encode(q),plan['created_at'],q['id']))
            connection.execute('INSERT INTO review_events(question_id,gate,decision,actor,created_at,metadata_json) VALUES (?,?,?,?,?,?)', (q['id'],'dataset','invalidated','Codex',plan['created_at'],encode({'reason':'content_replaced_old_quality_invalidated','content_identity':plan['content_id'],'human_approval':False,'source_snapshot':q['content_revision']['source_snapshot_id']})))
        s = plan['snapshot']
        connection.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)',(s['id'],'draft','offline_content_revision',encode(s),plan['created_at']))
        connection.execute('INSERT INTO golden_generation_runs VALUES (?,?,?,?,?,?)',(plan['run_id'],encode(s['profile']),'offline-content-revision','candidate_generated',encode(s['question_ids']),plan['created_at']))
        audit={'corpus_fingerprint':s['corpus_fingerprint'],'frozen_plan':s['coverage_plan'],'slot_persistence_v1':True,
               'content_identity':plan['content_id'],'status':'needs_human_review','source_validation':'passed',
               'probe_qc':'not_run','human_gate':'pending','quality_not_run':True,'paid_calls':0,
               'progress':{'stage':'candidate_generated','completed_slots':50,'total_slots':50}}
        connection.execute('INSERT INTO golden_generation_artifacts VALUES (?,?,?,?)',(plan['run_id'],encode(s['coverage_plan']['slots']),encode([{'question_id':q['id'],'coverage_slot':q['coverage_slot']} for q in plan['questions']]),encode(audit)))
        after = database_audit(connection)
        assert all(after[t] == value for t,value in preserved.items()), '独立审批/发布/配置审计发生变化'
        assert after['questions']['count']==50 and connection.execute("SELECT count(*) FROM dataset_versions WHERE status='approved'").fetchone()[0]==0
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    result={'content_id':plan['content_id'],'working_run_id':plan['run_id'],'draft_snapshot_id':plan['snapshot']['id'],
            'backup_sha256':backup_sha256,'backup_path':str(backup_path.resolve()),'removed_from_live_database':removed,
            'archived_snapshot_ids':plan['old_snapshots'],'preserved_audit_tables':preserved,'after_tables':after,
            'questions':50,'source_validation_passed':50,'semantic_review_pending':50,'probe_qc':'not_run','frozen':False,'provider_calls':0}
    (output/'execution.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    draft=json.loads((ROOT/'docs/GOLDEN_VNEXT_50_DRAFT.json').read_text())
    chunks=json.loads((ROOT/'backend/data/index/chunks.json').read_text())
    manifest=json.loads((ROOT/'backend/data/index/manifest.json').read_text())
    with closing(sqlite3.connect(args.database.resolve().as_uri()+('?mode=rw' if args.apply else '?mode=ro'),uri=True)) as connection:
        require_idle(connection)
        plan=prepare(connection,draft,chunks,manifest)
        (args.output/'prepared.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
        result=apply(connection,plan,args.output) if args.apply else {'status':'prepared','content_id':plan['content_id'],'questions':50,'source_validation_passed':50,'semantic_review_pending':50,'database_writes':0}
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
