"""Explicit 2026-10-14 owner scope; durable serial run, stops before Gate 2."""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
OUTPUT = ROOT / 'output/playwright/medium50-full-20261014'
SOURCE = Path('/Users/zhanghaohan/.codex/attachments/fbaa0811-e5ad-49a4-b3b7-13ad4b266be7/已粘贴的文本.txt')


def save(name, value):
    target = OUTPUT / name
    temporary = target.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, target)


def restore_saved_vectors(service, data, texts):
    from app.corpus import current_manifest, manifest_identity
    import numpy as np
    dimension = service.corpus.index_info()['dimension']
    vector_cache = {}
    for text in texts:
        payload = {'model':'text-embedding-v4','input':[text],'dimensions':dimension}
        digest = hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()
        call = next((c for c in data['calls'] if c['status']=='ok' and c['model']=='text-embedding-v4' and c['request_sha256']==digest and c.get('raw_response_path')),None)
        if call:
            body = json.loads(Path(call['raw_response_path']).read_text())
            vector = np.asarray(body['data'][0]['embedding'],dtype='float32')
            if vector.shape!=(dimension,) or not np.isfinite(vector).all() or np.linalg.norm(vector)==0: raise ValueError('Saved embedding response invalid')
            vector_cache[text] = vector/np.linalg.norm(vector)
    service._revision_vector_identity = json.dumps(service.corpus.index_info().get('knowledge_identity') or manifest_identity(current_manifest()),sort_keys=True)
    service._revision_vectors = vector_cache
    return len(vector_cache)


def continue_revision(main, revision_id, chunks):
    """Resume the existing transaction; completed quality is never repeated."""
    revision = main.store.revision_run(revision_id)
    if revision['status'] == 'interrupted' and revision.get('applied_at'):
        main.store.resume_revision_quality(revision_id)
    elif revision['status'] in {'interrupted', 'queued', 'generating'}:
        main._prepare_revision(revision_id, main.store, main.ai_service, main.corpus)
    revision = main.store.revision_run(revision_id)
    if revision['status'] == 'preview_ready' and revision['validation']['passed']:
        main.store.apply_revision(revision_id, chunks, similarity=main.ai_service.revision_similarity)
    return main.store.revision_run(revision_id)


def execute(stage):
    from app.corpus import current_manifest, manifest_identity
    from app.full_text import validate_bundle
    from app.paid_run import PaidRun, REQUEST_LIMITS, accounting_only, controlled_run
    current = manifest_identity(current_manifest())
    if stage == 'generate':
        OUTPUT.mkdir(parents=True, exist_ok=False)
        with sqlite3.connect(ROOT / 'backend/data/demo.db') as db:
            for table in ('golden_generation_runs', 'evaluation_runs', 'agent_traces', 'candidate_revision_runs'):
                if db.execute(f"SELECT 1 FROM {table} WHERE status IN ('running','queued','coverage','generating','validation','probing','qc')").fetchone():
                    raise RuntimeError('Active task; refused new owner run')
            with sqlite3.connect(OUTPUT / 'before.db') as backup:
                db.backup(backup)
        shutil.copytree(ROOT / 'backend/data/index', OUTPUT / 'index-before')
        shutil.copy2(ROOT / 'backend/data/corpus_state.json', OUTPUT / 'corpus-state-before.json')
        validate_bundle(ROOT / 'backend/data/index', require_full_text=True)
        protected = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('backend/documents','backend/data/index') for p in (ROOT / folder).rglob('*') if p.is_file()}
        save('protected-assets.json', protected)
        save('source-authorization.json', {'source_file':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'scope':'new_medium50_single_abc_round','source':'direct_user_instruction','actor':'Codex','currency_cap':None,'stop_before':'Gate 2'})
    state = json.loads((OUTPUT / 'state.json').read_text()) if (OUTPUT / 'state.json').exists() else {}
    from app import main
    if not main.ai_service.live_enabled:
        raise RuntimeError('Live Provider unavailable')
    if stage == 'generate':
        from app.business_golden import medium_plan
        from app.governance import GENERATION_PROFILES
        base = json.loads((main.corpus.index_dir / 'coverage.json').read_text())
        plan = medium_plan(base, main.corpus.chunks(), {'name':'medium', **GENERATION_PROFILES['medium']})
        run_id = main.store.start_generation_run(main.ai_service.model, 'medium', coverage_plan=plan)
        identity = {'generation_run_id':run_id,'corpus':current,'plan_id':plan['plan_id']}
        state = {**identity,'status':'generating','pid':os.getpid()}
        save('state.json', state)
        auth = {'authorization_id':'OWNER-MEDIUM50-20261014-'+run_id,'source':'direct_user_instruction','generation_run_id':run_id,'delegated_by':'project_owner','actor':'Codex','expires_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'source_file':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'corpus':current,'plan_id':plan['plan_id'],'profile':plan['profile'],'output_limits':REQUEST_LIMITS}
        # The existing server-owned verifier reads this exact scoped file.
        auth_path = main.store.database_path.parent / 'owner-delegated-review.json'
        if auth_path.exists(): shutil.copy2(auth_path, OUTPUT / 'previous-owner-delegation.json')
        auth_path.write_text(json.dumps(auth,ensure_ascii=False,indent=2)); auth_path.chmod(0o600)
        save('owner-delegation.json', auth)
        ledger = PaidRun(OUTPUT / 'provider-ledger.json', None, {}, identity, identity_check=lambda:identity if manifest_identity(current_manifest())==current else None, output_limits=REQUEST_LIMITS)
        print('GENERATION_STARTED '+run_id,flush=True)
        with accounting_only(), controlled_run(ledger):
            main._run_mini_generation_work(run_id,main.store,main.ai_service,main.corpus)
        result = main.store.generation_run(run_id)
        save('generation-result.json', result)
        save('questions.json', [main.store.question(key) for key in result['question_ids']])
        state.update(status=result['status']); save('state.json', state)
        print('GENERATION_FINISHED '+result['status'],flush=True)
        return
    if current != state['corpus']:
        raise RuntimeError('Corpus identity changed')
    if stage in {'refill','replacement-2','repair-drafts'}:
        identity = {key:state[key] for key in ('generation_run_id','corpus','plan_id')}
        data = json.loads((OUTPUT / 'provider-ledger.json').read_text())
        if any(call['status'] != 'ok' for call in data['calls']):
            raise RuntimeError('Unresolved Provider request; no duplicate paid refill')
        run = main.store.generation_run(state['generation_run_id'], qualification=False)
        expected_prior = {'refill':0,'replacement-2':1,'repair-drafts':2}[stage]
        if run['artifacts']['hard_validation'].get('regeneration_count', 0) != expected_prior:
            raise RuntimeError('Finite failed-Slot replacement already consumed or out of order')
        # Reuse successful evidence-blind Negative designs rejected by the old verifier wording.
        recovered = json.loads((OUTPUT / 'failed-design-recovered.json').read_text())
        audit = run['artifacts']['slot_audit']
        frozen = run['artifacts']['hard_validation']['frozen_plan']
        failed = set(run['artifacts']['hard_validation'].get('failed_slots', []))
        main.store.claim_regeneration(state['generation_run_id'], current)
        for slot in frozen['slots']:
            attempts = audit.get(slot['slot'], [])
            design = next((entry['business_design'] for entry in recovered if entry['slot']==slot['slot'] and entry['attempt']==1), None)
            if stage=='refill' and slot['slot'] in failed and slot['test_category']=='negative' and design and len(attempts)==2:
                audit[slot['slot']] = [*attempts, {'attempt':3,'business_design':design,'validation_error':'evidence_verification_pending','reuses_successful_design':True}]
                main.store.persist_generation_attempt(state['generation_run_id'],None,audit,slot=slot['slot'],attempt=3,model=main.ai_service.model,slot_complete=False)
        ledger = PaidRun.load_accounting(OUTPUT / 'provider-ledger.json',lambda:identity if manifest_identity(current_manifest())==current else None)
        if stage == 'replacement-2':
            ledger.golden_replacement_round = 2
            ledger.golden_replacement_run_id = state['generation_run_id']
            ledger.stages.append({'stage':'replacement-2','generation_run_id':state['generation_run_id'],'allowed_slots':sorted(failed),'max_new_attempts_per_slot':1,'authorization_source_sha256':json.loads((OUTPUT/'source-authorization.json').read_text())['source_sha256']})
        if stage == 'repair-drafts':
            revisions = json.loads((OUTPUT/'manual-draft-repairs.json').read_text())
            if set(revisions) != failed or any(len(audit[key]) != 4 for key in revisions):
                raise RuntimeError('Draft revision scope changed')
            ledger.golden_revision_run_id = state['generation_run_id']
            ledger.golden_draft_revisions = revisions
            ledger.stages.append({'stage':'controlled-draft-content-revision','generation_run_id':state['generation_run_id'],'allowed_slots':sorted(failed),'max_revisions_per_candidate':1,'new_candidate_replacement':False})
        with accounting_only(), controlled_run(ledger):
            main._run_mini_generation_work(state['generation_run_id'],main.store,main.ai_service,main.corpus,regenerate=True)
        result = main.store.generation_run(state['generation_run_id'])
        save(stage+'-result.json', result)
        save('questions.json', [main.store.question(key) for key in result['question_ids']])
        state['status']=result['status']; save('state.json',state)
        print('REFILL_FINISHED '+result['status'],flush=True)
        return
    if stage in {'independent-repair','independent-resume'}:
        identity = {key:state[key] for key in ('generation_run_id','corpus','plan_id')}
        data = json.loads((OUTPUT/'provider-ledger.json').read_text())
        unresolved = [i for i,call in enumerate(data['calls']) if call['status'] != 'ok']
        if unresolved:
            if stage != 'independent-resume' or len(unresolved)!=1 or data['calls'][unresolved[0]]['status']!='unknown':
                raise RuntimeError('Unresolved paid request; stopped')
            auth = json.loads((OUTPUT/'finite-independent-resume-authorization.json').read_text())
            if auth['held_call_indices'] != unresolved or auth['request_sha256'] != [data['calls'][i]['request_sha256'] for i in unresolved] or auth['identity'] != identity or auth['max_unknown_request_retries'] != 0:
                raise RuntimeError('Exact independent continuation scope differs')
        backup_path = OUTPUT/(stage+'-before.db')
        if not backup_path.exists():
            with sqlite3.connect(main.store.database_path) as db, sqlite3.connect(backup_path) as backup:
                db.backup(backup)
        ledger = PaidRun.load_accounting(OUTPUT/'provider-ledger.json',lambda:identity if manifest_identity(current_manifest())==current else None)
        if stage == 'independent-resume':
            ledger.stopped = None
            ledger.stages.append({'stage':stage,'authorization':auth,'unknown_cost':'retained','unknown_request_retries':0})
            ledger.save()
        designs = json.loads((OUTPUT/'independent-revision-designs.json').read_text())
        records = json.loads((OUTPUT/'independent-repair-records.json').read_text()) if (OUTPUT/'independent-repair-records.json').exists() else {}
        run = main.store.generation_run(state['generation_run_id'],qualification=False)
        plan = run['artifacts']['hard_validation']['frozen_plan']
        chunks = main.corpus.chunks(); known = {c['chunk_id']:c for c in chunks}
        texts = list(dict.fromkeys([q['question'] for q in main.store.questions()] + [r['business_design']['question'] for r in designs['changes'].values()] + [q['question'] for revision in main.store.revision_runs(state['generation_run_id']) for q in revision['before'].values()]))
        restored = restore_saved_vectors(main.ai_service,data,texts)
        save('restored-embedding-checkpoint.json',{'restored_texts':restored,'method':'exact request SHA256 + actual raw response','unknown_request_retried':False})
        with accounting_only(), controlled_run(ledger):
            # Exact same failed preparation can recover from saved vectors, not a repeated request.
            if stage == 'independent-resume':
                for revision in main.store.revision_runs(state['generation_run_id']):
                    if revision['status']=='failed' and revision.get('error_type')=='ProviderNetworkError' and not revision.get('applied_at'):
                        save('preparation-failure-'+revision['id']+'.json',revision)
                        main.store.update_revision(revision['id'],status='interrupted',stage='interrupted',preparation_recovery={'previous_error':revision.get('error'),'actor':'Codex','max_attempts':1,'unknown_request_retries':0})
            # Import marks formerly active revisions interrupted; recover the same transaction.
            for revision in main.store.revision_runs(state['generation_run_id']):
                if revision['status']=='interrupted':
                    key = next(iter(revision['before']))
                    if revision.get('applied_at'):
                        main.store.resume_revision_quality(revision['id'])
                    else:
                        main._prepare_revision(revision['id'],main.store,main.ai_service,main.corpus)
                        prepared = main.store.revision_run(revision['id'])
                        if prepared['status']=='preview_ready' and prepared['validation']['passed']:
                            main.store.apply_revision(revision['id'],chunks,similarity=main.ai_service.revision_similarity)
                    records[key] = {'slot':main.store.question(key)['raw']['coverage_slot'],'revision_id':revision['id'],'status':main.store.revision_run(revision['id'])['status']}
                    save('independent-repair-records.json',records)
            for key,change in designs['changes'].items():
                if key in records: continue
                item = main.store.question(key)
                slot = next(s for s in plan['slots'] if s['slot']==change['slot'])
                slot = {**slot,'sources':[known[k] for k in slot['material_chunk_ids']]}
                fields = {**change['business_design'],'difficulty':change['difficulty']}
                if item['test_category'] != 'negative':
                    from app.paid_run import provider_task
                    try:
                        checkpoint = OUTPUT/('independent-verified-'+change['slot']+'.json')
                        if checkpoint.exists():
                            verified = json.loads(checkpoint.read_text())
                            if verified['business_design']!=change['business_design']: raise ValueError('Verified design identity differs')
                        else:
                            with provider_task('revision'):
                                verified = main.ai_service.business_question_first(slot,[],[],None,prior_design=change['business_design'])
                        fields.update(reference_answer=verified['reference_answer'],source_chunk_ids=[c['chunk_id'] for c in verified['verified_sources']])
                        save('independent-verified-'+change['slot']+'.json',verified)
                    except ValueError as error:
                        records[key] = {'slot':change['slot'],'status':'evidence_verification_failed','reason':str(error)}
                        save('independent-repair-records.json',records); continue
                revision = main.store.start_revision(key,'manual_edit',change['reason'],False,{key:fields},chunks,tags=['其他'],actor='Codex AI Agent / Owner Delegated AI Review')
                main._prepare_revision(revision['id'],main.store,main.ai_service,main.corpus)
                prepared = main.store.revision_run(revision['id'])
                if ledger.stopped: raise RuntimeError('Paid revision preparation stopped: '+str(prepared.get('error')))
                if prepared['status']=='preview_ready' and prepared['validation']['passed']:
                    main.store.apply_revision(revision['id'],chunks,similarity=main.ai_service.revision_similarity)
                records[key] = {'slot':change['slot'],'revision_id':revision['id'],'status':main.store.revision_run(revision['id'])['status']}
                save('independent-repair-records.json',records)
                print('REVISION '+change['slot']+' '+records[key]['status'],flush=True)
            # All question edits are persisted before peer-aware quality checks.
            for key,record in records.items():
                if record['status'] != 'probing': continue
                revision = main.store.revision_run(record['revision_id'])
                if revision['status'] in {'probing','qc'}:
                    main._run_revision_quality(revision['id'],main.store,main.ai_service,main.corpus)
                finished = main.store.revision_run(revision['id'])
                save('independent-revision-'+record['slot']+'.json',finished)
                record['status']=finished['status']; save('independent-repair-records.json',records)
                print('QUALITY '+record['slot']+' '+finished['status'],flush=True)
                if finished.get('error'): raise RuntimeError('Revision Provider/engineering failure: '+finished['error'])
        run = main.store.generation_run(state['generation_run_id'],qualification=False)
        save('questions.json',[main.store.question(k) for k in run['question_ids']])
        save('machine-candidates.json',main.store.candidate_rows(run['question_ids']))
        return
    if stage == 'replacements-1':
        identity = {key:state[key] for key in ('generation_run_id','corpus','plan_id')}
        ledger = PaidRun.load_accounting(OUTPUT/'provider-ledger.json',lambda:identity if manifest_identity(current_manifest())==current else None)
        if ledger.stopped:
            data=json.loads((OUTPUT/'provider-ledger.json').read_text())
            auth=json.loads((OUTPUT/'finite-replacements-authorization.json').read_text())
            held=[i for i,c in enumerate(data['calls']) if c['status']!='ok']
            if held!=auth['held_call_indices'] or auth['identity']!=identity or auth['max_unknown_request_retries']!=0 or auth['request_sha256']!=[data['calls'][i]['request_sha256'] for i in held] or any(data['calls'][i]['status']!='unknown' for i in held):
                raise RuntimeError('Exact held-request continuation scope differs')
            ledger.stopped=None;ledger.stages.append({'stage':stage,'authorization':auth,'unknown_request_retries':0});ledger.save()
        backup_path = OUTPUT/'replacements-1-before.db'
        if not backup_path.exists():
            with sqlite3.connect(main.store.database_path) as db,sqlite3.connect(backup_path) as backup:db.backup(backup)
        targets = json.loads((OUTPUT/'replacement-1-targets.json').read_text())
        records = json.loads((OUTPUT/'replacement-1-records.json').read_text()) if (OUTPUT/'replacement-1-records.json').exists() else {}
        chunks=main.corpus.chunks()
        data=json.loads((OUTPUT/'provider-ledger.json').read_text())
        restore_saved_vectors(main.ai_service,data,[q['question'] for q in main.store.questions()])
        with accounting_only(),controlled_run(ledger):
            for key,reason in targets.items():
                if key in records:
                    resumed = continue_revision(main, records[key]['revision_id'], chunks)
                    records[key]['status'] = resumed['status']
                    save('replacement-1-records.json', records)
                    if ledger.stopped:raise RuntimeError('Provider failure in replacement recovery')
                    continue
                created = main.store.start_revision(key,'ai_regenerate',reason,False,{},chunks,tags=['其他'],replacement=True,actor='Codex AI Agent / Owner Delegated AI Review')
                records[key]={'revision_id':created['id'],'slot':main.store.question(key)['raw']['coverage_slot'],'status':'queued'}
                save('replacement-1-records.json',records)
                main._prepare_revision(created['id'],main.store,main.ai_service,main.corpus)
                prepared=main.store.revision_run(created['id'])
                save('replacement-1-preview-'+records[key]['slot']+'.json',prepared)
                records[key]['status']=prepared['status'];save('replacement-1-records.json',records)
                if ledger.stopped:raise RuntimeError('Provider failure in independent replacement')
                if prepared['status']=='preview_ready' and prepared['validation']['passed']:
                    applied=main.store.apply_revision(created['id'],chunks,similarity=main.ai_service.revision_similarity)
                    records[key].update(status=applied['status'],new_question_ids=applied['question_ids']);save('replacement-1-records.json',records)
                print('REPLACEMENT '+records[key]['slot']+' '+records[key]['status'],flush=True)
            for key,record in records.items():
                revision=main.store.revision_run(record['revision_id'])
                if revision['status'] in {'probing','qc'}:main._run_revision_quality(revision['id'],main.store,main.ai_service,main.corpus)
                finished=main.store.revision_run(revision['id']);record['status']=finished['status'];save('replacement-1-records.json',records)
                save('replacement-1-quality-'+record['slot']+'.json',finished)
                print('REPLACEMENT_QUALITY '+record['slot']+' '+finished['status'],flush=True)
                if finished.get('error') or ledger.stopped or finished['status'] in {'queued','generating','interrupted','probing','qc'}:raise RuntimeError('Independent replacement execution stopped')
        run=main.store.generation_run(state['generation_run_id'],qualification=False)
        save('questions.json',[main.store.question(k) for k in run['question_ids']]);save('machine-candidates.json',main.store.candidate_rows(run['question_ids']))
        return
    if stage in {'final-content','r3-scope'}:
        identity = {key:state[key] for key in ('generation_run_id','corpus','plan_id')}
        ledger = PaidRun.load_accounting(OUTPUT/'provider-ledger.json',lambda:identity if manifest_identity(current_manifest())==current else None)
        backup_path = OUTPUT/(stage+'-before.db')
        if not backup_path.exists():
            with sqlite3.connect(main.store.database_path) as db,sqlite3.connect(backup_path) as backup:db.backup(backup)
        changes = json.loads((OUTPUT/(stage+'-changes.json')).read_text())
        records = json.loads((OUTPUT/(stage+'-records.json')).read_text()) if (OUTPUT/(stage+'-records.json')).exists() else {}
        chunks = main.corpus.chunks()
        data = json.loads((OUTPUT/'provider-ledger.json').read_text())
        texts = list(dict.fromkeys([q['question'] for q in main.store.questions()] + [r['fields'].get('question',main.store.question(k)['question']) for k,r in changes.items()]))
        restore_saved_vectors(main.ai_service,data,texts)
        with accounting_only(),controlled_run(ledger):
            for key,change in changes.items():
                if key in records:
                    resumed = continue_revision(main, records[key]['revision_id'], chunks)
                    records[key]['status'] = resumed['status']
                    save(stage+'-records.json', records)
                    if ledger.stopped:raise RuntimeError('Provider failure in content recovery')
                    continue
                if change.get('resume_revision_id'):
                    revision = main.store.revision_run(change['resume_revision_id'])
                    if revision['status']!='failed' or revision.get('applied_at') or revision.get('changes')!={key:change['fields']} or revision.get('preparation_recovery'):
                        raise RuntimeError('Exact finite preparation recovery differs or already attempted')
                    save('preparation-failure-'+revision['id']+'.json',revision)
                    main.store.update_revision(revision['id'],status='interrupted',stage='interrupted',preparation_recovery={'previous_error':revision.get('error'),'actor':'Codex','max_attempts':1,'unknown_request_retries':0})
                else:
                    revision = main.store.start_revision(key,'manual_edit',change['reason'],False,{key:change['fields']},chunks,tags=['其他'],replacement=change.get('replacement',False),actor='Codex AI Agent / Owner Delegated AI Review')
                records[key]={'revision_id':revision['id'],'slot':main.store.question(key)['raw']['coverage_slot'],'status':revision['status']}
                save(stage+'-records.json',records)
                main._prepare_revision(revision['id'],main.store,main.ai_service,main.corpus)
                prepared = main.store.revision_run(revision['id'])
                records[key]={'revision_id':revision['id'],'slot':main.store.question(key)['raw']['coverage_slot'],'status':prepared['status']}
                save(stage+'-records.json',records)
                if ledger.stopped:raise RuntimeError('Provider preparation stopped')
                if prepared['status']=='preview_ready' and prepared['validation']['passed']:
                    applied=main.store.apply_revision(revision['id'],chunks,similarity=main.ai_service.revision_similarity)
                    records[key]['status']=applied['status'];save(stage+'-records.json',records)
                print('FINAL_CONTENT '+records[key]['slot']+' '+records[key]['status'],flush=True)
            for key,record in records.items():
                revision = main.store.revision_run(record['revision_id'])
                if revision['status'] in {'probing','qc'}:main._run_revision_quality(revision['id'],main.store,main.ai_service,main.corpus)
                finished=main.store.revision_run(revision['id']);record['status']=finished['status'];save(stage+'-records.json',records)
                save(stage+'-'+record['slot']+'.json',finished)
                print('FINAL_QUALITY '+record['slot']+' '+finished['status'],flush=True)
                if finished.get('error') or ledger.stopped or finished['status'] in {'queued','generating','interrupted','probing','qc'}:raise RuntimeError('Final revision execution incomplete: '+str(finished.get('error')))
        run=main.store.generation_run(state['generation_run_id'],qualification=False)
        save('questions.json',[main.store.question(k) for k in run['question_ids']]);save('machine-candidates.json',main.store.candidate_rows(run['question_ids']))
        return
    if stage == 'evaluate':
        # Reviews are independently authored by Codex after all actual PDF/quality checks.
        auth = json.loads((OUTPUT / 'owner-delegation.json').read_text())
        reviews = json.loads((OUTPUT / 'independent-reviews.json').read_text())
        if not state.get('snapshot'):
            result = main.store.review_owner_delegated_batch(state['generation_run_id'],auth['authorization_id'],reviews)
            save('gate1-result.json', result)
            state['snapshot'] = result; save('state.json',state)
        identity = {key:state[key] for key in ('generation_run_id','corpus','plan_id')}
        ledger = PaidRun.load_accounting(OUTPUT / 'provider-ledger.json',lambda:identity if manifest_identity(current_manifest())==current else None)
        from app.evaluation import EvaluationRunner
        from app.optimization import OptimizationAgent
        runner = EvaluationRunner(main.store, main.ai_service)
        with accounting_only(), controlled_run(ledger):
            if not state.get('baseline_id'):
                run_id, questions, config = runner.start_baseline(automatic=True)
                state['baseline_id']=run_id; save('state.json',state)
                result = runner.execute_baseline(run_id,questions,config)
                save('baseline-result.json',result)
            baseline = main.store.evaluation_run(state['baseline_id'])
            if baseline['status'] != 'completed':raise RuntimeError('Baseline incomplete')
            if not state.get('experiment_id'):
                result=OptimizationAgent(main.store,main.ai_service.provider).generate(baseline['id'])
                save('agent-result.json',result)
                state['experiment_id']=result['id']; save('state.json',state)
            experiment=main.store.experiment(state['experiment_id'])
            candidates=experiment['candidates']
            for candidate in sorted(candidates,key=lambda item:item['reasoning'].get('candidate_label','')):
                if candidate['status']=='evaluated':continue
                if candidate['status']!='generated':raise RuntimeError('Candidate requires checkpoint recovery')
                result=runner.run_candidate(candidate['id'],automatic=True)
                save('sandbox-'+candidate['reasoning']['candidate_label']+'.json',result)
                if result['status']!='evaluated':raise RuntimeError('Sandbox incomplete')
        state['status']='completed_before_gate2' if len(candidates)==3 else 'insufficient_candidates'
        save('state.json',state)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('generate','refill','replacement-2','repair-drafts','independent-repair','independent-resume','replacements-1','final-content','r3-scope','evaluate'),required=True)
    args=parser.parse_args()
    try:execute(args.stage)
    except Exception as error:
        if OUTPUT.exists():save('execution-error.json',{'type':type(error).__name__,'error':str(error),'at':datetime.now(timezone.utc).isoformat()})
        raise
