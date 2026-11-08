"""Read-only Golden table projection from frozen questions and saved assessments."""
import json

from .diagnostic_categories import DIAGNOSTIC_CATEGORIES


def probe_subject(question):
    # Scoring rubrics do not determine question validity or evidence retrieval.
    raw = question.get('raw') or question
    return {key:question.get(key, raw.get(key)) for key in
            ('question','evidence','test_category','negative_subtype','expected_behavior','ablation_attribute')}


def project_question_rows(store, rows, *, snapshot=None):
    if not rows:
        return rows
    identity = store.current_baseline_identity()
    with store.connection() as db:
        if snapshot is None:
            saved = db.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?',(identity.get('current_golden_id'),)).fetchone()
            snapshot = json.loads(saved[0]) if saved else {}
        parent_id = snapshot.get('scoring_revision', {}).get('parent_id')
        saved = db.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?',(parent_id,)).fetchone() if parent_id else None
        parent = json.loads(saved[0]) if saved else None
        frozen = {q['id']:q for q in snapshot.get('questions', [])}
        prior = {q['id']:q for q in (parent or {}).get('questions', [])}
        ids = [r['id'] for r in rows]
        placeholders = ','.join('?' for _ in ids)
        probes = {r['question_id']:dict(r) for r in db.execute(f"""SELECT p.question_id,p.id,
            json_extract(result_json,'$.score') score,
            json_extract(result_json,'$.probe_details.classification') classification,
            json_extract(result_json,'$.probe_details.probe_execution_status') execution_status,
            json_extract(result_json,'$.execution_identity.corpus_fingerprint') corpus
            FROM probe_results p WHERE p.id=(SELECT MAX(id) FROM probe_results WHERE question_id=p.question_id)
            AND p.question_id IN ({placeholders})""",ids)}
        qcs = {r['question_id']:{'score':r['score']} for r in db.execute(f"""SELECT q.question_id,json_extract(result_json,'$.score') score FROM qc_results q
            WHERE q.id=(SELECT MAX(id) FROM qc_results WHERE question_id=q.question_id) AND q.question_id IN ({placeholders})""",ids)}
        cases = {r['question_id']:{'passed':bool(r['passed']) if r['passed'] is not None else None,
            'diagnosis_category':r['category'] or {'Retrieval':'检索层问题','Ranking':'检索层问题','Generation':'生成层问题','Safety':'安全边界问题','Performance':'性能问题'}.get(r['root'])}
            for r in db.execute("""SELECT question_id,json_extract(result_json,'$.passed') passed,
                json_extract(result_json,'$.diagnostic_view.diagnosis_category') category,
                json_extract(result_json,'$.primary_root_cause') root FROM evaluation_case_results WHERE run_id=?""",(identity.get('current_baseline_id'),))}
    result = []
    for row in rows:
        q = frozen.get(row['id']) or {**(row.get('raw') or {}), **row}
        requirements = q.get('business_requirements') or (q.get('raw') or {}).get('business_requirements') or {}
        sources = requirements.get('sources') or []
        labels = []
        for source in sources:
            if source.get('document_name') and source.get('page_start') is not None:
                pages = str(source['page_start']) + (f"–{source['page_end']}" if source.get('page_end') not in (None,source['page_start']) else '')
                labels.append(f"{source['document_name']} · 第 {pages} 页")
        probe = probes.get(row['id'])
        source_id = snapshot.get('id')
        if parent:
            # Inheritance is allowed only for an unchanged Probe subject/corpus.
            eligible = (row['id'] in prior and probe_subject(prior[row['id']]) == probe_subject(q)
                        and parent.get('corpus_fingerprint') == snapshot.get('corpus_fingerprint'))
            if not eligible:
                probe = None
            else:
                source_id = parent_id
        if probe:
            if probe['corpus'] and json.loads(probe['corpus']) != snapshot.get('corpus_fingerprint'):
                probe = None
            else:
                probe = {'id':probe['id'],'score':probe['score'],'classification':probe['classification'],
                    'execution_status':probe['execution_status'], 'association':{'source_dataset_id':source_id,
                    'target_dataset_id':snapshot.get('id'),'reason':'题目、证据、题型、预期行为、消融属性及知识身份一致；评分要点不参与Probe'}}
        category = cases.get(row['id'], {}).get('diagnosis_category')
        if category not in {r['label'] for r in DIAGNOSTIC_CATEGORIES}:
            category = None
        result.append({**row, 'probe':probe, 'qc':qcs.get(row['id'],row.get('qc')),
            'knowledge_topic':(q.get('topic_cluster') or (row.get('raw') or {}).get('topic_cluster')),
            'source_summary':'；'.join(dict.fromkeys(labels)) or ('不适用（负向题（Negative）无标准证据）' if q.get('test_category')=='negative' else None),
            'scoring_summary':{'required':len(requirements['required_checks']),'auxiliary':len(requirements.get('auxiliary_information',[]))} if 'required_checks' in requirements else None,
            'baseline_result':{**cases[row['id']], 'diagnosis_category':category} if row['id'] in cases else None})
    return result
