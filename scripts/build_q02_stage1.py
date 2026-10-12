"""Authorized Q02 staging only: one dual-text embedding, one rerank, no activation/DB writes.

No retry/resume switch. A fresh output is required; a consumed call is never retried.
"""
import argparse
import copy
import json
import os
import re
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.corpus import CorpusStore, current_manifest
from app.full_text import checksum, validate_bundle
from app.golden_v2 import digest, normalize, validate_golden_candidate
from app.knowledge_pipeline import AlibabaProvider
from app.policy import DEFAULT_PIPELINE_CONFIG
from app.retrieval import VectorRetriever
from repair_golden_index_offline import RUN, database_rows, encode

OLD_CORPUS = 'CORPUS-c6bbb042130820be7a1a'
TEXT_STAGE = ROOT / 'output/playwright/golden-index-final/applied/text-staging'
RATE = .5 / 1_000_000


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def verify_patch(old, new, vectors):
    if len(old) != 368 or len(new) != 368 or vectors.shape != (368, 1024):
        raise ValueError('Expected 368 Children and 1024d vectors')
    if [c['chunk_id'] for c in old] != [c['chunk_id'] for c in new]:
        raise ValueError('Child ordering/identity changed')
    changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    if len(changed) != 1 or new[changed[0]]['chunk_id'] != 'DOC-001-C-00134':
        raise ValueError('Only the Q02 Child may change')
    if not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) == 0):
        raise ValueError('Invalid old vectors')
    return changed[0]


class PaidClient(AlibabaProvider):
    def __init__(self, values, output, texts, *, authorized):
        super().__init__(values)
        self.output, self.texts, self.authorized = output, texts, authorized
        self.calls, self.cost, self.expected_rerank = [], 0.0, None

    def _post(self, path, payload):
        model = payload.get('model')
        if not self.authorized or self.cost >= .01 or len(self.calls) >= 2:
            raise ValueError('Provider authorization/budget exhausted')
        if any(c['model'] == model for c in self.calls):
            raise ValueError('Consumed Provider attempt cannot retry')
        if model == 'text-embedding-v4':
            valid = path == '/compatible-mode/v1/embeddings' and payload.get('input') == self.texts and payload.get('dimensions') == 1024 and not self.calls
        elif model == 'qwen3-rerank':
            valid = path == '/compatible-api/v1/reranks' and len(self.calls) == 1 and self.calls[0].get('status') == 'success' and self.expected_rerank == digest(payload)
        else:
            valid = False
        if not valid: raise ValueError('Provider input/model outside frozen scope')
        call = {'model': model, 'status': 'attempted', 'input_digest': digest(payload), 'started_at': datetime.now(timezone.utc).isoformat()}
        self.calls.append(call)
        save(self.output / 'provider-calls.json', self.calls)
        try:
            body = super()._post(path, payload)
            save(self.output / f'{model}-response.json', body)
            tokens = body.get('usage', {}).get('total_tokens')
            call.update(usage=body.get('usage'), request_id=body.get('request_id') or body.get('id'), response_model=body.get('model'))
            if type(tokens) is not int or tokens < 0:
                raise ValueError('Actual Provider usage unavailable; stop')
            call['calculated_list_cost_cny'] = tokens * RATE
            self.cost += call['calculated_list_cost_cny']
            if self.cost > .01: raise ValueError('Actual usage exceeds 0.01 CNY budget')
            if body.get('model') and body['model'] != model: raise ValueError('Response model identity differs')
            call['status'] = 'success'
            return body
        except Exception as error:
            call.update(status='failed', error_type=type(error).__name__)
            raise
        finally:
            save(self.output / 'provider-calls.json', self.calls)


def refresh_plan(old, children, vectors, identity):
    plan = copy.deepcopy(old)
    order = sorted(range(len(children)), key=lambda i: children[i]['chunk_id'])
    sorted_children = [children[i] for i in order]
    normalized = vectors[order] / np.linalg.norm(vectors[order], axis=1)[:, None]
    positions = {c['chunk_id']: i for i, c in enumerate(sorted_children)}
    if set(plan['chunk_clusters']) != set(positions): raise ValueError('Coverage membership differs')
    for cluster in plan['clusters']:
        if any(plan['chunk_clusters'][key] != cluster['cluster_id'] for key in cluster['chunk_ids']):
            raise ValueError('Coverage membership/cluster mismatch')
        cluster['center'] = normalized[[positions[key] for key in cluster['chunk_ids']]].mean(axis=0).tolist()
    plan.update(previous_plan_id=old['plan_id'], corpus_fingerprint=identity,
                chunk_fingerprint=digest(sorted_children), embedding_identity=identity['embedding_artifact_id'],
                embedding_fingerprint=checksum(normalized.tobytes()),
                membership_provenance={'mode': 'controlled_single_child_patch', 'source_plan_id': old['plan_id'], 'reclustered': False},
                created_at=datetime.now(timezone.utc).isoformat())
    plan['plan_id'] = 'PLAN-' + digest({k: v for k, v in plan.items() if k != 'plan_id'})[:24]
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    # One fixed authorization ledger prevents a second run spending the same budget.
    ledger = ROOT / 'output/playwright/golden-q02-stage1-20261012.authorization'
    if args.execute_authorized:
        with ledger.open('x') as stream:
            stream.write(str(output)); stream.flush(); os.fsync(stream.fileno())
    output.mkdir(parents=True, exist_ok=False)
    active = ROOT / 'backend/data/index'
    db_path = ROOT / 'backend/data/demo.db'
    operation = 'Q02-STAGE1-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
    staging = ROOT / 'backend/data/index_versions' / (operation + '-building')
    report = {'operation': operation, 'status': 'preflight', 'paid_requests': 0, 'activated': False, 'golden_binding_modified': False, 'staging': str(staging)}
    client, before, hashes = None, None, {}
    try:
        original = validate_bundle(active, require_full_text=True)
        manifest = original['manifest']
        if manifest['knowledge_identity']['corpus_snapshot_id'] != OLD_CORPUS or manifest['embedding_model'] != 'text-embedding-v4':
            raise ValueError('Active model/Corpus differs from authorized identity')
        if current_manifest()['sources'] != manifest['sources']: raise ValueError('Source PDFs changed')
        with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as db:
            for table in ['evaluation_runs', 'golden_generation_runs', 'agent_traces', 'candidate_revision_runs']:
                if db.execute(f"SELECT 1 FROM {table} WHERE status IN ('running','queued','coverage','generating','validation','probing','qc')").fetchone():
                    raise ValueError('Active task; stop')
            before = database_rows(db)
            with sqlite3.connect(output / 'before.db') as backup: db.backup(backup)
            audit = json.loads(db.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?', (RUN,)).fetchone()[0])
            ids = json.loads(db.execute('SELECT question_ids_json FROM golden_generation_runs WHERE id=?', (RUN,)).fetchone()[0])
            questions = []
            for key in ids:
                row = db.execute('SELECT raw_json,stage,review_status,probe_status,qc_status FROM questions WHERE id=?', (key,)).fetchone()
                if tuple(row[1:]) != ('candidate','human_review_pending','probe_pending','qc_pending'): raise ValueError('Working set qualification changed')
                questions.append(json.loads(row[0]))
        if audit['corpus_fingerprint'] != manifest['knowledge_identity'] or len(questions) != 50:
            raise ValueError('Golden identity/size differs')
        hashes = {str(p.relative_to(ROOT)): checksum(p.read_bytes()) for folder in [ROOT/'backend/documents', active, ROOT/'backend/data/index_versions'] for p in folder.rglob('*') if p.is_file()}
        save(output/'protection-before.json', {'database_rows': before, 'assets': hashes, 'identity': manifest['knowledge_identity']})
        shutil.copytree(active, output/'before-index')
        new_children = json.loads((TEXT_STAGE/'chunks.json').read_text())
        old_vectors = np.load(active/'embeddings.npy', allow_pickle=False)
        row = verify_patch(original['chunks'], new_children, old_vectors)
        old_parents = json.loads((active/'parents.json').read_text())
        new_parents = json.loads((TEXT_STAGE/'parents.json').read_text())
        if [p['chunk_id'] for p in old_parents] != [p['chunk_id'] for p in new_parents] or sum(a != b for a,b in zip(old_parents,new_parents)) != 1:
            raise ValueError('Unexpected Parent patch')
        for name in ['DOC-001-blocks.json','full_text.json']:
            old = json.loads((active/name).read_text()); new = json.loads((TEXT_STAGE/name).read_text())
            left, right = (old, new) if isinstance(old,list) else (old['pages'],new['pages'])
            if len(left) != len(right) or sum(a != b for a,b in zip(left,right)) != 1: raise ValueError('Unexpected Block/page patch')
        q02 = next(q for q in questions if q['coverage_slot'] == 'Q02')
        text, query = new_children[row]['chunk_text'], q02['question']
        expected_text = original['chunks'][row]['chunk_text'].replace('4. 点击用户名的输入栏\n7.', '4. 点击用户名的输入栏\n5. 利用屏幕上的键盘输入用户名，点击回车键完成\n6. 按下“密码”按钮\n7.')
        if text != expected_text: raise ValueError('Patch differs from PDF-verified scope')
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-small-zh-v1.5', local_files_only=True)
        if checksum(tokenizer.backend_tokenizer.to_str().encode()) != manifest['knowledge_config']['tokenizer_artifact_id']:
            raise ValueError('Frozen tokenizer identity differs')
        counter = lambda t: len(tokenizer.encode(t, add_special_tokens=False))
        estimated_tokens = counter(text) + counter(query) + sum(sorted([counter(c['chunk_text']) for c in new_children],reverse=True)[:12]) + 12 * counter(query)
        if estimated_tokens * RATE >= .01 or counter(text) > 400: raise ValueError('Preflight budget/token limit failed')
        # A complete copy is used only inside the independent version directory.
        shutil.copytree(active, staging)
        (staging/'manifest.json').rename(staging/'source-manifest.json')
        for name in ['chunks.json','parents.json','DOC-001-blocks.json','full_text.json']:
            shutil.copyfile(TEXT_STAGE/name, staging/name)
        report.update(old_identity=manifest['knowledge_identity'], source_working_set=RUN,
                      source_plan_id=audit['frozen_plan']['plan_id'], estimated_bge_tokens=estimated_tokens,
                      estimated_cost_cny=estimated_tokens*RATE, budget_cny=.01, changed_child=new_children[row]['chunk_id'])
        if not args.execute_authorized:
            report['status'] = 'preflight_passed; no Provider requests'
            return
        from app.config import load_values
        values = load_values()
        host = urlsplit(values.get('DASHSCOPE_BASE_URL','')).hostname or ''
        if not host.endswith('.cn-beijing.maas.aliyuncs.com') or not values.get('DASHSCOPE_API_KEY'):
            raise ValueError('Authorized Beijing endpoint/credential unavailable')
        client = PaidClient(values, output, [text, query], authorized=True)
        vectors_two = client.embed([text, query], 1024)
        np.save(output/'requested-vectors.npy', vectors_two)
        vectors = old_vectors.copy(); vectors[row] = vectors_two[0]
        keep = [i for i in range(368) if i != row]
        if not np.array_equal(vectors[keep], old_vectors[keep]): raise ValueError('Unchanged vectors differ')
        if np.array_equal(vectors[row],old_vectors[row]): raise ValueError('Changed vector unexpectedly equals old vector')
        new_children[row]['embedding_status'] = 'Indexed'
        save(staging/'chunks.json', new_children)
        np.save(staging/'embeddings.npy', vectors)
        import faiss
        index = faiss.IndexFlatIP(1024); index.add(vectors); faiss.write_index(index,str(staging/'faiss.index'))
        if not np.array_equal(index.reconstruct_n(0,368),vectors): raise ValueError('FAISS/matrix differs')
        config = manifest['knowledge_config']
        identity = {'sources':manifest['sources'], 'chunk_artifact_id':'CHUNK-'+digest([new_parents,new_children])[:20],
                    'embedding_artifact_id':'EMB-'+checksum(vectors.tobytes())[:20], 'index_artifact_id':'IDX-'+checksum((staging/'faiss.index').read_bytes())[:20]}
        identity['pipeline_version_id'] = 'KP-'+digest([config,identity['chunk_artifact_id'],identity['embedding_artifact_id'],identity['index_artifact_id']])[:20]
        identity['corpus_snapshot_id'] = 'CORPUS-'+digest([identity['sources'],identity['pipeline_version_id']])[:20]
        corpus_plan = refresh_plan(json.loads((active/'coverage.json').read_text()),new_children,vectors,identity)
        medium_plan = refresh_plan(audit['frozen_plan'],new_children,vectors,identity)
        save(staging/'coverage.json',corpus_plan)
        revised_manifest = copy.deepcopy(manifest)
        revised_manifest.update(knowledge_identity=identity,coverage_plan_id=corpus_plan['plan_id'])
        revised_manifest['artifacts'] = {p.name:checksum(p.read_bytes()) for p in staging.iterdir() if p.is_file() and p.name!='manifest.json'}
        save(staging/'manifest.json',revised_manifest)
        validate_bundle(staging,require_full_text=True)
        report.update(new_identity=identity,corpus_plan_id=corpus_plan['plan_id'],medium_plan_id=medium_plan['plan_id'],
                      reused_vectors=367,reused_vectors_sha256=checksum(vectors[keep].tobytes()),bundle_integrity=True)
        preview = copy.deepcopy(questions); validations = {}
        for q in preview:
            q['plan_id'] = medium_plan['plan_id']
            result = validate_golden_candidate(q,new_children,medium_plan,{'slot_id':q['coverage_slot'],'seen':[p['question'] for p in preview if p is not q],'corpus_fingerprint':identity})
            validations[q['coverage_slot']] = result
            q.update(validation=result,evidence_locations=result['evidence_locations'],coverage_match=result['coverage_match'])
        save(output/'hard-validation.json',validations)
        if not all(v['valid'] for v in validations.values()): raise ValueError('New Corpus/Plan Hard Validation failed')
        if Counter(q['test_category'] for q in preview) != {'positive':20,'ablation':10,'negative':20}: raise ValueError('Profile differs')
        allowed = {'plan_id','validation','evidence_locations','coverage_match'}
        if any({k:v for k,v in old.items() if k not in allowed} != {k:v for k,v in new.items() if k not in allowed} for old,new in zip(questions,preview)):
            raise ValueError('Question content differs from formal working set')
        report.update(question_content_unchanged=50,revised_questions_preserved=sum(q['revision_audit']['recommendation']!='保留' for q in questions),
                      retained_questions_preserved=sum(q['revision_audit']['recommendation']=='保留' for q in questions),counts=dict(Counter(q['test_category'] for q in preview)))
        report['hard_validation'] = '50/50'
        preview_q02 = next(q for q in preview if q['coverage_slot']=='Q02')
        preview_q02['pdf_supplement'] = {**preview_q02['pdf_supplement'],'status':'verified_in_isolated_new_bundle','blocks_freeze':False,'corpus_fingerprint':identity,'previous_status':q02['pdf_supplement']['status']}
        save(output/'working-set-preview.json',{'questions':preview,'plan':medium_plan,'corpus_fingerprint':identity,'probe_qc':'pending','human_gate':'pending'})
        retriever = VectorRetriever(CorpusStore(staging))
        retriever._index = index
        trace, timings = {}, []
        base_rerank = AlibabaProvider.rerank
        def cached_embed(_self, texts, dimension):
            if texts != [query] or dimension != 1024: raise ValueError('Query cache identity differs; no extra requests')
            return vectors_two[1:2].copy()
        def live_rerank(_self, question, hits):
            save(output/'pre-rerank-trace.json',trace)
            if question != query or not 1 <= len(hits) <= 12 or new_children[row]['chunk_id'] not in [h['chunk_id'] for h in hits]:
                raise ValueError('Q02 absent from actual fused candidate pool')
            client.expected_rerank = digest({'model':'qwen3-rerank','query':question,'documents':[h['content'] for h in hits],'top_n':len(hits)})
            return base_rerank(client,question,hits)
        with patch.object(AlibabaProvider,'embed',cached_embed),patch.object(AlibabaProvider,'rerank',live_rerank):
            final = retriever.retrieve(query,{**DEFAULT_PIPELINE_CONFIG,'knowledge_identity':identity},stages=timings,trace=trace)
        save(output/'retrieval-trace.json',{'trace':trace,'timings':timings})
        target = next((hit for hit in final if hit['parent_chunk_id']=='DOC-001-P-00133'),None)
        if target is None or new_children[row]['chunk_id'] not in target['matched_child_ids']:
            raise ValueError('Q02 absent from actual final context')
        steps = re.findall(r'(?m)^(\d+)\. (.+)$',text)
        if [int(n) for n,_ in steps] != list(range(1,15)): raise ValueError('Q02 source steps incomplete/order differs')
        import pymupdf
        doc = next(d for d in original['documents'] if d['id']=='DOC-001')
        with pymupdf.open(ROOT/'backend/documents'/doc['name']) as pdf:
            source = '\n'.join(pdf[n-1].get_text() for n in [49,50,51])
        checks = []
        for number, sentence in steps:
            fact = normalize(sentence)
            passed = fact in normalize(target['content']) and fact in normalize(source)
            checks.append({'step':int(number),'source_text':sentence,'pdf_pages':[49,50,51],'in_final_context_and_pdf':passed})
        save(output/'q02-fourteen-steps.json',checks)
        if not all(c['in_final_context_and_pdf'] for c in checks): raise ValueError('Full step text not supported by PDF/final context')
        if '如有必要' not in dict(steps)['13']: raise ValueError('Optional permission step lost')
        report.update(q02_fourteen_steps=True,q02_final_parent='DOC-001-P-00133',q02_candidate_rank=next(h['rank'] for h in trace['candidates'] if h['chunk_id']==new_children[row]['chunk_id']))
        # Verify rollback only using disposable copies; never touch the formal pointer or DB.
        from app.corpus_management import CorpusManager
        simulation = output/'rollback-copy'; simulation.mkdir()
        shutil.copytree(active,simulation/'index')
        shutil.copytree(staging,simulation/'new')
        manager = CorpusManager(VectorRetriever(CorpusStore(simulation/'index')),index_dir=simulation/'index')
        def fail(): raise RuntimeError('isolated rollback fault injection')
        try: manager.activate_bundle(simulation/'new','failure',after_activate=fail)
        except RuntimeError: pass
        else: raise ValueError('Injected activation failure did not fail')
        if validate_bundle(simulation/'index',require_full_text=True)['manifest']['knowledge_identity'] != manifest['knowledge_identity']:
            raise ValueError('Isolated old index rollback failed')
        with sqlite3.connect(output/'before.db') as source_db,sqlite3.connect(simulation/'restored.db') as restored_db:
            source_db.backup(restored_db)
            if database_rows(restored_db) != before: raise ValueError('Backup restore differs')
        report.update(index_failure_rollback_verified=True,database_backup_restore_verified=True,status='stage1_passed; switch_awaits_explicit_authorization')
    except Exception as error:
        report.update(status='stopped',failure_type=type(error).__name__,failure=str(error))
        raise
    finally:
        if client:
            report.update(paid_requests=len(client.calls),provider_calls=client.calls,calculated_list_cost_cny=client.cost,actual_account_charge='not_collected')
        if before is not None:
            with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
                report['all_database_rows_unchanged'] = database_rows(db)==before
        if hashes:
            report['all_prior_assets_unchanged'] = all(checksum((ROOT/n).read_bytes())==h for n,h in hashes.items())
            report['protected_prior_asset_count'] = len(hashes)
        report['formal_identity_unchanged'] = json.loads((active/'manifest.json').read_text())['knowledge_identity']['corpus_snapshot_id']==OLD_CORPUS
        protected = all(report.get(k,False) for k in ['all_database_rows_unchanged','all_prior_assets_unchanged','formal_identity_unchanged'])
        if not protected: report.update(status='stopped',failure='Protection check failed')
        save(output/'report.json',report)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        if not protected:
            raise ValueError('Protection check failed; no further work allowed')


if __name__ == '__main__': main()
