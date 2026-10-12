"""Read-only formal preflight; no switch, application import or Provider calls."""
import argparse
import json
import shutil
import socket
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import load_values
from app.full_text import checksum, validate_bundle
from app.golden_v2 import validate_golden_candidate
from repair_golden_index_offline import RUN, database_rows

STAGE1 = ROOT/'output/playwright/golden-q02-stage1-20261012'


def preflight(output):
    output.mkdir(parents=True,exist_ok=False)
    active = ROOT/'backend/data/index'
    stage = json.loads((STAGE1/'report.json').read_text())
    staging = Path(stage['staging'])
    assets = {str(p.relative_to(ROOT)):checksum(p.read_bytes()) for folder in
              [active,ROOT/'backend/data/index_versions',ROOT/'backend/documents'] for p in folder.rglob('*') if p.is_file()}
    old,new = [validate_bundle(p,require_full_text=True) for p in (active,staging)]
    old_id,new_id = [b['manifest']['knowledge_identity'] for b in (old,new)]
    if old_id['corpus_snapshot_id']!='CORPUS-c6bbb042130820be7a1a' or new_id['corpus_snapshot_id']!='CORPUS-38c90d5628b68c76d53e':
        raise ValueError('Expected Corpus identity changed')
    preview = json.loads((STAGE1/'working-set-preview.json').read_text())
    plan,questions = preview['plan'],preview['questions']
    if plan['plan_id']!='PLAN-89801791985fdfe13f1421cf' or plan['corpus_fingerprint']!=new_id:
        raise ValueError('Expected new Plan identity changed')
    with sqlite3.connect((ROOT/'backend/data/demo.db').as_uri()+'?mode=ro',uri=True) as db:
        before = database_rows(db)
        ids = json.loads(db.execute('SELECT question_ids_json FROM golden_generation_runs WHERE id=?',(RUN,)).fetchone()[0])
        audit = json.loads(db.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?',(RUN,)).fetchone()[0])
        if ids!=[q['id'] for q in questions] or len(ids)!=50 or audit['corpus_fingerprint']!=old_id:
            raise ValueError('Formal working set binding changed')
        for table in ['evaluation_runs','golden_generation_runs','agent_traces','candidate_revision_runs']:
            if db.execute(f"SELECT 1 FROM {table} WHERE status IN ('running','queued','coverage','generating','validation','probing','qc')").fetchone():
                raise ValueError('Active task; cannot enter maintenance')
        allowed = {'plan_id','validation','evidence_locations','coverage_match','pdf_supplement'}
        originals = []
        for q in questions:
            saved = db.execute('SELECT raw_json,stage,review_status,probe_status,qc_status FROM questions WHERE id=?',(q['id'],)).fetchone()
            if tuple(saved[1:])!=('candidate','human_review_pending','probe_pending','qc_pending'):
                raise ValueError('Working set quality state changed')
            original = json.loads(saved[0])
            originals.append(original)
            if {k:v for k,v in original.items() if k not in allowed}!={k:v for k,v in q.items() if k not in allowed}:
                raise ValueError('Working set content changed')
        validations = [validate_golden_candidate(q,new['chunks'],plan,{'slot_id':q['coverage_slot'],'corpus_fingerprint':new_id,
                       'seen':[a['question'] for a in questions if a is not q]}) for q in questions]
        hard = sum(v['valid'] for v in validations)
        if hard!=50: raise ValueError('Isolated Hard Validation failed')
        formal_hard = sum(validate_golden_candidate(q,old['chunks'],audit['frozen_plan'],{'slot_id':q['coverage_slot'],'corpus_fingerprint':old_id,
                          'seen':[a['question'] for a in originals if a is not q]})['valid'] for q in originals)
        source_snapshot = json.loads(db.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?',(audit['source_snapshot_id'],)).fetchone()[0])
        prior = {q['coverage_slot']:q for q in source_snapshot['questions']}
        lifecycle = {'id','generation_run_id','plan_id','source_reference','revision_audit','validation'}
        revisions = Counter(q['revision_audit']['recommendation'] for q in originals)
        if dict(revisions)!={'保留':28,'轻量修订':17,'实质修订':4,'替换':1}: raise ValueError('Revision count changed')
        for q in originals:
            if q['revision_audit']['recommendation']=='保留' and {k:v for k,v in q.items() if k not in lifecycle}!={k:v for k,v in prior[q['coverage_slot']].items() if k not in lifecycle}:
                raise ValueError('Retained question content changed')
        history = {t:len(before[t]) for t in ['dataset_versions','evaluation_runs','experiments','candidate_configs','production_versions','agent_traces']}
        if database_rows(db)!=before: raise ValueError('Formal rows changed during preflight')
    import faiss
    vectors = [faiss.read_index(str(p/'faiss.index')).reconstruct_n(0,368) for p in (active,staging)]
    reused = [i for i in range(368) if i!=133]
    if vectors[0][reused].tobytes()!=vectors[1][reused].tobytes(): raise ValueError('Reused vectors differ')
    values = load_values()
    model = values.get('DEEPSEEK_MODEL','deepseek-v4-flash')
    if model not in {'deepseek-v4-flash','deepseek-flash'}: raise ValueError('Pricing model mismatch')
    # Verified 2026-10-12; central parity is a planning conversion, not card settlement.
    usd_cny = 6.7313
    output_tokens = 384000
    envelope = {period:50*output_tokens*rate*usd_cny/1_000_000 for period,rate in [('off_peak',.6),('peak',1.2)]}
    if not all(checksum((ROOT/name).read_bytes())==value for name,value in assets.items()):
        raise ValueError('Protected source assets changed')
    report = {'status':'blocked_before_switch','reason':'Unchanged request has no explicit output bound; 50 mandatory audits alone exceed conservative 20 CNY envelope',
              'formal_identity':old_id,'isolated_identity':new_id,'new_plan':plan['plan_id'],'working_set':RUN,
              'formal_switch':False,'formal_hard_validation':formal_hard,'isolated_hard_validation':hard,'revision_counts':dict(revisions),
              'groups':dict(Counter(q['test_category'] for q in questions)),'topics':len(plan['clusters']),
              'vector_reuse_count':len(reused),'vector_reuse_sha256':checksum(vectors[1][reused].tobytes()),
              'all_formal_rows_unchanged':True,'protected_tables':len(before),'protected_assets':len(assets),'history_counts':history,
              'paid_calls':0,'tokens':0,'cost_yuan':0,'budget_yuan':20,'output_envelope_only_yuan':envelope,
              'model':model,'output_bound_tokens_per_request':output_tokens,'usd_cny_planning_rate':usd_cny,
              'price_sources':['https://api-docs.deepseek.com/quick_start/pricing/','https://help.aliyun.com/zh/model-studio/model-pricing'],
              'fx_source':'https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do?COLLCC=546877760',
              'credentials_configured':{k:bool(values.get(k)) for k in ['DEEPSEEK_API_KEY','DASHSCOPE_API_KEY']},
              'free_disk_bytes':shutil.disk_usage(ROOT).free}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (output/'protected-assets.json').write_text(json.dumps(assets,indent=2))
    (output/'formal-row-digests.json').write_text(json.dumps(before,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    def denied(*args,**kwargs): raise RuntimeError('Preflight forbids network calls')
    socket.socket.connect = denied
    preflight(args.output.resolve())
