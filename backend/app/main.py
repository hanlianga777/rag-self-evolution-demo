from .corpus import manifest_identity
import csv
import io
import hashlib
import marshal
import json
import os
import sqlite3
import logging
import threading
import contextvars
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Query, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .ai_service import AiService
from . import architecture_assets, business_import
from .corpus import CorpusStore, UPLOADS_DIR, current_manifest
from .full_text import CORPUS_LOCK
from .corpus_management import CorpusManager, require_consistent_switch
from .config import load_settings
from .evaluation import EvaluationRunner, gate_details
from .evaluation_contract import policy_current, VERSIONS, BUSINESS_JUDGE_PROMPT, validate_business_judgment
from .governance import GovernanceStore, GENERATION_PROFILES
from .optimization import OptimizationAgent
from .diagnostics import diagnostic_view
from .policy import DEFAULT_PIPELINE_CONFIG, EXCLUDED_AUTOMATIC_PARAMETERS, search_space_contract, validate_candidate_config
from .telemetry import price_config
from .providers import DeepSeekProvider, ProviderTimeout, ProviderUnavailable
from .retrieval import RetrievalUnavailable


from .agent_coverage import plan_coverage, complete_coverage
from .knowledge_pipeline import AlibabaProvider
from .evaluation_stage import perform_stage
from .read_view import read_view

# Fingerprint loaded objects, not source files that may have changed under a live process.
EVALUATION_RUNTIME_CONTRACT = {**VERSIONS, 'judge_prompt_sha256':hashlib.sha256(BUSINESS_JUDGE_PROMPT.encode()).hexdigest(),
    'loaded_code_sha256':{name:hashlib.sha256(marshal.dumps(fn.__code__)).hexdigest() for name,fn in {
        'validator':validate_business_judgment, 'provider_parser':DeepSeekProvider._judge_business,
        'scorer':EvaluationRunner.score_execution, 'batch_runner':EvaluationRunner._execute_baseline,
        'diagnostic_view':diagnostic_view, 'agent_generate':OptimizationAgent.generate.__wrapped__, 'coverage_planner':plan_coverage, 'coverage_apply':complete_coverage, 'alibaba_transport':AlibabaProvider._post_request,
        'alibaba_request':AlibabaProvider._post,'provider_stage':perform_stage,
        'sandbox_resume_guard':GovernanceStore.validate_evaluation_resume,'sandbox_preflight':EvaluationRunner.candidate_resume_plan}.items()}}

app = FastAPI(title="RAG Evolution Demo API", version="0.1.0")
app.mount("/documents", StaticFiles(directory=Path(__file__).resolve().parents[1] / "documents"), name="documents")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR, check_dir=False), name="uploads")
TRUSTED_ORIGINS = ["http://localhost:5174", "http://127.0.0.1:5174"]
app.add_middleware(CORSMiddleware, allow_origins=TRUSTED_ORIGINS, allow_methods=["*"], allow_headers=["*"])
corpus = CorpusStore()
require_consistent_switch(corpus.index_dir, os.getenv("RAG_DEMO_DB_PATH") or None)
store = GovernanceStore(os.getenv("RAG_DEMO_DB_PATH") or None)
ai_service = AiService(store, corpus, DeepSeekProvider(load_settings()), os.getenv("RAG_FORCE_MOCK") == "1")
corpus_manager = CorpusManager(ai_service.retriever, knowledge_pipeline=True, on_knowledge_activated=lambda: start_knowledge_golden())
store.interrupt_revision_runs()
store.interrupt_generation_runs()
store.interrupt_evaluation_runs()
store.interrupt_agent_generations()


_recovery_stop=threading.Event()


def recover_authorized_evaluations():
    def recover(run_id):
        try:EvaluationRunner(store,ai_service).recover_run(run_id)
        except Exception as error:
            run=store.evaluation_run(run_id)
            if run and run['status'] in {'queued','running'}:
                result=run['result'];result['auto_recovery'].update(state='stopped',error=str(error))
                store.finish_evaluation_run(run_id,'partial' if store.evaluation_case_results(run_id) else 'failed',result,str(error))
    for run in store.evaluation_runs(authorized_only=True):
        auto=run['result'].get('auto_recovery',{})
        if run['result'].get('stop_request'):
            store.request_evaluation_stop(run['id']);continue
        if not auto.get('authorized') or auto.get('state')=='stopped':continue
        if run['status']=='running' and auto.get('worker_token'):
            owner=run['result'].get('execution_owner_pid')
            if owner==os.getpid() and any(t.ident==auto.get('worker_thread') and t.is_alive() for t in threading.enumerate()):continue
            if owner!=os.getpid() and type(owner) is int:
                try:os.kill(owner,0)
                except ProcessLookupError:pass
                except PermissionError:continue
                else:continue
        candidate=store.candidate(run['config']['candidate_id']) if run['config'].get('candidate_id') else None
        if run['status'] in {'queued','running'} or run['status']=='completed' and candidate and candidate['status']=='running':
            threading.Thread(target=recover,args=(run['id'],),daemon=True).start()


@app.on_event('startup')
def start_recovery_monitor():
    _recovery_stop.clear()
    def monitor():
        last_retention=0.0
        while not _recovery_stop.is_set():
            if time.monotonic()-last_retention>=60:
                try:
                    from .history import prune_history
                    prune_history(store)
                except Exception:logging.exception('History retention unavailable')
                last_retention=time.monotonic()
            try:recover_authorized_evaluations()
            except Exception:logging.exception('Evaluation recovery monitor unavailable')
            _recovery_stop.wait(5)
    threading.Thread(target=monitor,daemon=True).start()


@app.on_event('shutdown')
def stop_recovery_monitor():
    _recovery_stop.set()


@app.exception_handler(RetrievalUnavailable)
async def retrieval_unavailable(_request: Request, error: RetrievalUnavailable):
    return JSONResponse(status_code=503, content={'detail': {**error.detail, 'message': str(error)}})


class PreviewRequest(BaseModel):
    question: str = Field(strict=True, min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def non_blank_question(cls, value):
        if not value.strip():
            raise ValueError("Question is required")
        return value.strip()


class SchemePreviewRequest(PreviewRequest):
    scheme_id: str = Field(strict=True, min_length=1, max_length=120)


class EvaluationRequest(BaseModel):
    limit: int = Field(default=40, strict=True, ge=1, le=40)


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|needs_revision)$")
    actor: str = Field(default="local_user", min_length=1, max_length=80)
    reason: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=8)
    accept_qc_p0: bool = False


class RevisionRequest(BaseModel):
    mode: Literal["manual_edit", "ai_regenerate"]
    reason: str = Field(min_length=1, max_length=2000)
    paired: bool = False
    changes: dict[str, dict] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=8)
    replacement: bool = False
    actor: str = Field(default='local_user', min_length=1, max_length=80)


class RevisionDraftEditRequest(BaseModel):
    changes: dict[str, dict]
    expected_hashes: dict[str, str]


class RevisionDraftRegenerateRequest(BaseModel):
    question_id: str
    expected_hash: str
    material_mode: Literal["retain", "reselect"] = "retain"
    reason: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=8)
    manual_chunk_ids: list[str] | None = None


class QuestionUpdateRequest(BaseModel):
    question: str = Field(strict=True, min_length=1, max_length=1000)
    reference_answer: str | None = Field(default=None, max_length=4000)
    evidence: list[dict] = Field(default_factory=list)
    actor: str = Field(default="local_user", min_length=1, max_length=80)


class MonitoringEventRequest(BaseModel):
    question: str = Field(strict=True, min_length=1, max_length=1000)
    answer: str = Field(strict=True, min_length=1, max_length=8000)
    bad_case: bool
    severity: str = Field(pattern="^(ordinary|critical)$")
    determinable: bool = True


class MonitoringAssessmentRequest(BaseModel):
    bad_case: bool
    severity: str = Field(pattern="^(ordinary|critical)$")


class BatchReviewRequest(BaseModel):
    question_ids: list[str] = Field(min_length=1)
    actor: str = Field(default="local_user", min_length=1, max_length=80)
    confirmed_manual_review: bool = False


class OwnerDelegatedReviewRequest(BaseModel):
    generation_run_id: str
    authorization_id: str
    reviews: list[dict] = Field(min_length=50,max_length=50)


class DirectReleaseRequest(BaseModel):
    config: dict
    actor: str = Field(default="local_user", min_length=1, max_length=80)


class ExperimentRequest(BaseModel):
    trigger_id: str | None = None


class RecommendationRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=120)
    actor: str = Field(default="local_user", min_length=1, max_length=80)


class AliasRequest(BaseModel):
    alias: str = Field(min_length=1, max_length=120)
    canonical: str = Field(min_length=1, max_length=120)
    actor: str = Field(default="local_user", min_length=1, max_length=80)


class GenerationRequest(BaseModel):
    plan_id: str | None = None
    profile: Literal["mini", "medium", "full"] = "mini"
    strategy: Literal["evidence_v1", "business_v2"] = "evidence_v1"


def require_trusted_origin(request: Request):
    origin = request.headers.get("origin")
    if origin is not None and origin not in TRUSTED_ORIGINS:
        raise HTTPException(status_code=403, detail="Untrusted Origin")


@app.get("/api/overview/architecture/{slot}")
def architecture_metadata(slot: Literal["business", "technical"]):
    path = architecture_assets.asset_path(slot)
    return {"slot": slot, "image_url": f"/api/overview/architecture/{slot}/image?v={path.stat().st_mtime_ns}" if path else None}


@app.get("/api/overview/architecture/{slot}/image")
def architecture_image(slot: Literal["business", "technical"]):
    path = architecture_assets.asset_path(slot)
    if path is None:
        raise HTTPException(status_code=404, detail="尚未上传架构图")
    return FileResponse(path, media_type=architecture_assets.FORMATS[path.suffix[1:]])


@app.put("/api/overview/architecture/{slot}", dependencies=[Depends(require_trusted_origin)])
async def architecture_upload(slot: Literal["business", "technical"], request: Request):
    if request.headers.get("content-length") and int(request.headers["content-length"]) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="图片不能超过 10 MB")
    data = await request.body()
    try:
        architecture_assets.save_asset(slot, data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return architecture_metadata(slot)


@app.delete("/api/overview/architecture/{slot}", dependencies=[Depends(require_trusted_origin)])
def architecture_delete(slot: Literal["business", "technical"]):
    architecture_assets.delete_asset(slot)
    return architecture_metadata(slot)


def light_value(value):
    """List projection only; full audit/detail endpoints keep persisted payloads."""
    if isinstance(value, list):return [light_value(item) for item in value]
    if isinstance(value, dict):
        return {key:light_value(item) for key,item in value.items() if not key.endswith('_json') and key not in {'checkpoints','all_bad_case_audit','target_reference_map','target_diagnosis','comparison'}}
    return value


@app.get("/api/overview")
def overview(light: bool = False):
    summary = store.dataset_summary()
    production = store.active_production()
    identity = store.current_baseline_identity()
    baseline = store.evaluation_run(identity["current_baseline_id"], light=light) if identity["current_baseline_id"] else None
    triggers = store.optimization_triggers()
    knowledge_state = knowledge()
    if light:
        knowledge_state = {**knowledge_state, 'index':{key:value for key,value in knowledge_state['index'].items() if key!='coverage'},
            'coverage':{'profile':knowledge_state['coverage']['profile']} if knowledge_state.get('coverage') else None, 'sample_children':[]}
    return {"generation_profiles": GENERATION_PROFILES, "data_source": "real", "production": production, "dataset": summary, "latest_evaluation": baseline, "knowledge": knowledge_state, **identity, "monitoring": {"events": len(store.monitoring_events()), "pending_triggers": sum(item["status"] == "pending_human_confirm" for item in triggers)}}


@app.get("/api/workspace")
def workspace():
    documents = corpus.documents()
    state = corpus_manager.state()
    identity = store.current_baseline_identity()
    stale = identity["requires_new_golden"]
    return {"name": "机器人智能问答评测与优化 Agent", "environment": "Production Baseline", "document_count": len(documents), "chunk_count": sum(item["chunks"] for item in documents), "active_version": (store.active_production() or {}).get("id"), "corpus_changed_at": state.get("changed_at"), "requires_new_golden": stale, "requires_new_baseline": not stale and identity["current_baseline_id"] is None, **identity}


def require_current_baseline(run_id: str | None = None):
    try:
        return store.require_current_baseline(run_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get('/api/knowledge')
def knowledge():
    with CORPUS_LOCK:
        from .knowledge_pipeline import CONFIG, provider_status
        index = corpus.index_info()
        manifest_path = corpus.index_dir/'manifest.json'
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        coverage = index.get('coverage')
        # Profile plans are versioned separately; immutable index artifacts remain unchanged.
        with store.connection() as connection:
            previews = connection.execute('SELECT plan_json FROM coverage_plan_previews ORDER BY created_at DESC').fetchall()
        for preview in previews:
            plan = json.loads(preview['plan_json'])
            if plan['corpus_fingerprint'] == index.get('knowledge_identity') and plan['profile'] == {'name': 'full', **GENERATION_PROFILES['full']}:
                coverage = plan
                break
        index['coverage'] = coverage
        fresh = manifest.get('sources') == current_manifest()['sources']
        operations = [corpus_manager.operation(p.stem) for p in (corpus_manager.data_dir/'corpus_operations').glob('*.json')]
        operation = next(iter(sorted((o for o in operations if o), key=lambda o: o['id'].rsplit('-', 1)[-1], reverse=True)), None)
        updating = bool(operation and operation['status'] == 'running')
        if updating or not fresh: coverage = None
        documents = corpus.documents()
        return {'target_config': index.get('knowledge_config') or CONFIG, 'providers': provider_status(), 'index': index,
                'identity': index.get('knowledge_identity'), 'legacy': not bool(index.get('knowledge_identity')),
                'documents': len(documents), 'pages': sum(d.get('pages') or 0 for d in documents),
                'coverage': coverage, 'coverage_plan_id': coverage.get('plan_id') if coverage else None, 'coverage_status': 'calculating' if updating else 'ready' if coverage else 'pending',
                'operation': operation, 'sample_children': corpus.chunks()[:3] if index.get('knowledge_identity') else []}


@app.get('/api/knowledge/clusters/{cluster_id}')
def knowledge_cluster(cluster_id: str):
    with CORPUS_LOCK:
        state = knowledge(); plan = state['coverage']
        if not plan: raise HTTPException(status_code=409, detail='知识主题覆盖待更新')
        cluster = next((c for c in plan['clusters'] if c['cluster_id'] == cluster_id), None)
        if cluster is None: raise HTTPException(status_code=404, detail='Cluster not found')
        chunks = {c['chunk_id']: c for c in corpus.chunks()}
        return {**cluster, 'identity': state['identity'], 'coverage_plan_id': plan['plan_id'], 'initial_k': plan['initial_k'], 'merge_mapping': plan['merge_mapping'],
                'source_documents': sorted({chunks[key]['document_name'] for key in cluster['chunk_ids']}),
                'representative_children': [chunks[key] for key in cluster['representative_chunk_ids']],
                'slots': [s for s in plan['slots'] if s['topic_cluster'] == cluster_id]}


@app.get('/api/knowledge/slots/{slot_id}')
def knowledge_slot(slot_id: str):
    with CORPUS_LOCK:
        state = knowledge(); plan = state['coverage']
        if not plan: raise HTTPException(status_code=409, detail='知识主题覆盖待更新')
        slot = next((s for s in plan['slots'] if s['slot_id'] == slot_id), None)
        if slot is None: raise HTTPException(status_code=404, detail='Slot not found')
        chunks = {c['chunk_id']: c for c in corpus.chunks()}
        return {**slot, 'identity': state['identity'], 'coverage_plan_id': plan['plan_id'], 'material_children': [chunks[key] for key in slot['material_chunk_ids']], 'golden_candidates': [{key: q.get(key) for key in ('id', 'question', 'reference_answer', 'evidence', 'probe_status', 'qc_status', 'review_status')} for q in store.questions() if q.get('raw', {}).get('plan_id') == plan['plan_id'] and q.get('raw', {}).get('coverage_slot') == slot_id]}


def start_knowledge_golden():
    """Continue real Full construction only; the existing workflow ends at Human Gate 1."""
    if not ai_service.live_enabled: raise ProviderUnavailable('DeepSeek missing; Corpus preserved, Golden not run')
    with CORPUS_LOCK:
        state = knowledge()
        plan = state['coverage']
        if not plan: raise ValueError('Current Knowledge Coverage unavailable')
        from .governance import _json
        with store.connection() as connection:
            connection.execute('INSERT OR IGNORE INTO coverage_plan_previews (id, plan_json, created_at) VALUES (?, ?, ?)', (plan['plan_id'], _json(plan), plan['created_at']))
        run_id = store.start_generation_run(ai_service.model, 'full', coverage_plan=plan)
    threading.Thread(target=_run_mini_generation, args=(run_id, store, ai_service, corpus), daemon=True).start()
    return run_id


@app.post('/api/knowledge/rebuild', status_code=202, dependencies=[Depends(require_trusted_origin)])
def rebuild_knowledge():
    require_idle_corpus()
    try: return corpus_manager.start('rebuild')
    except ValueError as error: raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/documents")
def documents():
    return corpus.documents()


def require_idle_corpus():
    running_generation = any(item["status"] in {"queued", "coverage", "generating", "validation", "probing", "qc"} for item in store.generation_runs())
    running_revision = any(item["status"] in {"queued", "generating", "validating", "probing", "qc"} for item in store.revision_runs())
    running_evaluation = any(item["status"] == "running" for item in store.evaluation_runs())
    if running_generation or running_revision or running_evaluation:
        raise HTTPException(status_code=409, detail="当前有 Generation、Revision 或 Evaluation 正在运行，请结束后再修改 Corpus")


@app.post("/api/documents", status_code=202, dependencies=[Depends(require_trusted_origin)])
async def upload_document(request: Request, filename: str):
    require_idle_corpus()
    if request.headers.get("content-type", "").split(";")[0] != "application/pdf" or int(request.headers.get("content-length", "0") or 0) > 50 * 1024 * 1024:
        raise HTTPException(status_code=415, detail="请选择不超过 50 MB 的 PDF")
    data = await request.body()
    if not data.startswith(b"%PDF-") or len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="PDF 文件无效或超过 50 MB")
    try:
        return corpus_manager.start("upload", filename=filename, data=data)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/corpus-operations/{operation_id}")
def corpus_operation(operation_id: str):
    result = corpus_manager.operation(operation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Operation not found")
    return result


@app.delete("/api/documents/{document_id}", status_code=202, dependencies=[Depends(require_trusted_origin)])
def delete_document(document_id: str):
    require_idle_corpus()
    if not any(item["id"] == document_id for item in corpus.documents()):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        return corpus_manager.start("delete", document_id=document_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/documents/{document_id}")
def document_detail(document_id: str):
    with CORPUS_LOCK:
        result = corpus.detail(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return result


@app.get("/api/dataset")
def dataset(light: bool = False):
    rows = store.working_pool_rows()
    return [{key:value for key,value in row.items() if key not in {'quality_audit','question'}} for row in rows] if light else [store.question(row['id']) for row in rows]


@app.get("/api/governance/summary")
def governance_summary():
    return store.dataset_summary()


@app.get("/api/governance/questions")
def governance_questions(stage: str | None = None):
    return store.questions(stage)


class PoolRunRequest(BaseModel):
    plan_id: str | None = None
    profile: Literal['mini', 'medium', 'full']
    question_ids: list[str] = Field(min_length=1, max_length=max(profile['expected_count'] for profile in GENERATION_PROFILES.values()))


@app.post('/api/governance/coverage-preview', dependencies=[Depends(require_trusted_origin)])
def coverage_preview(payload: GenerationRequest):
    try:
        with CORPUS_LOCK:
            chunks = corpus.chunks()
            return store.coverage_preview(payload.profile, chunks, ai_service._indexed_embeddings(chunks))
    except (ValueError, ProviderUnavailable) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def current_coverage_plan(profile, plan_id):
    with CORPUS_LOCK:
        chunks = corpus.chunks()
        return store.resolve_coverage_plan(profile, chunks, plan_id, ai_service._indexed_embeddings(chunks))


@app.post('/api/governance/generation-runs/from-pool/preview', dependencies=[Depends(require_trusted_origin)])
def preview_pool_run(payload: PoolRunRequest):
    try:
        with CORPUS_LOCK:
            plan = current_coverage_plan(payload.profile, payload.plan_id)
            return store.preview_pool_run(payload.profile, payload.question_ids, corpus.chunks(), plan['plan_id'])
    except (ValueError, KeyError, ProviderUnavailable) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post('/api/governance/generation-runs/from-pool/autofill', dependencies=[Depends(require_trusted_origin)])
def autofill_pool_run(payload: PoolRunRequest):
    try:
        with CORPUS_LOCK:
            plan = current_coverage_plan(payload.profile, payload.plan_id)
            return store.autofill_pool_run(payload.profile, payload.question_ids, corpus.chunks(), plan['plan_id'])
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get('/api/governance/import-template')
def import_template(format: Literal['csv', 'xlsx'] = 'xlsx'):
    content, media_type = business_import.template(format)
    return Response(content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="golden-business-template.{format}"'})


@app.post('/api/governance/imports', dependencies=[Depends(require_trusted_origin)])
async def import_candidates(request: Request, filename: str, confirm: bool = False, allow_partial: bool = False, preview_hash: str | None = None):
    try:
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > 10 * 1024 * 1024:
                raise ValueError("文件超过 10 MB")
        content = bytes(data)
        file_hash = hashlib.sha256(content).hexdigest()
        if confirm and preview_hash and preview_hash != file_hash:
            raise ValueError('文件已变化，请重新预览')
        receipt = store.business_import_receipt(file_hash) if confirm else None
        if receipt: return {**receipt, 'replayed': True, 'created_count': 0}
        with CORPUS_LOCK:
            receipt = store.business_import_receipt(file_hash) if confirm else None
            if receipt: return {**receipt, 'replayed': True, 'created_count': 0}
            plan = current_coverage_plan('mini', None)
            result = business_import.parse_import(content, Path(filename).name, corpus.chunks(), store.questions(), plan)
            if confirm:
                if result['error_count'] and not allow_partial or not result['valid_rows']:
                    raise ValueError('请先修正全部错误，再确认导入')
                result['question_ids'] = store.save_business_candidates(result['valid_rows'], Path(filename).name, result['file_hash'], [row for row in result['rows'] if row['errors']])
                result['imported_count'] = len(result['question_ids'])
                result['created_count'] = result['imported_count']
        return result
    except (ValueError, UnicodeError, OSError, ProviderUnavailable) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post('/api/governance/generation-runs/from-pool', dependencies=[Depends(require_trusted_origin)], status_code=201)
def create_pool_run(payload: PoolRunRequest):
    try:
        with CORPUS_LOCK:
            plan = current_coverage_plan(payload.profile, payload.plan_id)
            return store.create_pool_run(payload.profile, payload.question_ids, corpus.chunks(), plan['plan_id'])
    except (ValueError, KeyError, ProviderUnavailable) as error:
        raise HTTPException(status_code=422, detail=json.loads(str(error)) if str(error).startswith('{') else str(error)) from error


@app.get("/api/governance/generation-runs/{run_id}/naturalness-audit")
def naturalness_audit(run_id: str):
    run = store.generation_run(run_id, qualification=False)
    if not run:
        raise HTTPException(status_code=404, detail="Generation run not found")
    from .business_golden import dataset_quality_audit
    rows = [{**row, 'raw':store.question(row['id']).get('raw', row['raw'])} for row in store.candidate_rows(run['question_ids'])]
    before = [store.question(row['raw']['replaces_question_id']) for row in rows if row['raw'].get('replaces_question_id')]
    return dataset_quality_audit(rows, before)


@app.get("/api/governance/candidates")
def candidate_list(run_id: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100), source: str = "all", group: str = "all", construction: str = "all", search: str = "", status: str = "all"):
    run = store.generation_run(run_id, qualification=False) if run_id else None
    if run_id and run is None:
        raise HTTPException(status_code=404, detail="Generation run not found")
    rows = store.candidate_rows(run['question_ids']) if run else store.working_pool_rows()
    summary = {'total':len(rows), 'ai':sum(row['raw'].get('source')!='business_import' for row in rows), 'business':sum(row['raw'].get('source')=='business_import' for row in rows),
        'machine_qualified':sum(row['qualification_status'] in {'machine_qualified','human_approved','owner_delegated_approved'} for row in rows),
        'needs_processing':sum(row['qualification_status']=='needs_human_review' and row['probe_status']!='probe_pending' and row['qc_status']!='qc_pending' for row in rows),
        'pending_checks':sum(row['qualification_status']=='needs_human_review' and (row['probe_status']=='probe_pending' or row['qc_status']=='qc_pending') for row in rows)}
    types = sorted({row['construction_type'] for row in rows if row['construction_type']})
    candidate_index = [{key:row[key] for key in ('id','stage','review_status','probe_status','qc_status','test_category','raw','slot','topic_cluster','qualification_status','qualification_source','attention_reasons','attention_categories','probe','qc')} for row in rows] if run else []
    version_rows = rows
    risks = any(row['qualification_status']=='needs_human_review' for row in rows)
    rows = [row for row in rows if (status=='all' or status=='attention' and (row['qualification_status']=='needs_human_review' or not risks) or status=='machine' and row['qualification_status']=='machine_qualified' or status=='usable' and row['qualification_status'] in {'machine_qualified','human_approved','owner_delegated_approved'} or status=='govern' and row['qualification_status']=='needs_human_review') and (source=='all' or (row['raw'].get('source') or 'ai_generated')==source) and (group=='all' or row['test_category']==group) and (construction=='all' or row['construction_type']==construction) and search.lower() in row['question'].lower()]
    version = hashlib.sha256(json.dumps([(row['id'],row['updated_at'],row['qualification_status'],row['attention_reasons'],row['quality_audit']) for row in version_rows],sort_keys=True).encode()).hexdigest()
    return {'rows':[{key:value for key,value in row.items() if key!='quality_audit'} for row in rows[offset:offset+limit]], 'candidate_index':candidate_index, 'total':len(rows), 'summary':summary, 'construction_types':types, 'data_version':version, 'corpus_fingerprint':manifest_identity(current_manifest()), 'generation_run_id':run_id, 'profile':run['profile'] if run else None}


@app.get("/api/governance/questions/{question_id}")
def candidate_detail(question_id: str):
    try:
        item = store.question(question_id)
        run_id = item['raw'].get('generation_run_id')
        if run_id and question_id in (store.generation_run(run_id, qualification=False) or {}).get('question_ids', []):
            return store.generation_review(run_id, corpus.chunks(), allow_partial=True, question_id=question_id)['questions'][0]
        return {**item,'probe_history':store.probe_history(question_id),'qc_history':store.qc_history(question_id),'revision_history':store.revision_history(question_id)}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Candidate not found") from error


@app.get("/api/governance/generation-runs")
def generation_runs(light: bool = False):
    if not light:
        return store.generation_runs()
    current = store.working_generation_run()
    runs = [store.generation_run(current['id'])] if current else []
    result = []
    for run in runs[:1]:
        audit = run['artifacts']['hard_validation']
        frozen = audit.get('frozen_plan')
        if frozen:
            frozen = {**frozen, 'clusters':[{key:value for key,value in cluster.items() if key not in {'centroid','center','embedding'}} for cluster in frozen['clusters']]}
        result.append({**{key:run[key] for key in ('id','status','profile','question_ids','created_at','human_gate')}, 'operation_progress':run.get('operation_progress'),
            'artifacts':{'slot_audit':{}, 'question_plan':[], 'coverage_plan':[{'slot':slot.get('slot')} for slot in run['artifacts'].get('coverage_plan',[])],
                'hard_validation':{**{key:value for key,value in audit.items() if key in {'corpus_fingerprint','slot_persistence_v1','progress','quality_rerun'}}, 'frozen_plan':frozen}}})
    return result


@app.get("/api/governance/generation-runs/{run_id}")
def generation_run_status(run_id: str):
    result = store.generation_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Generation run not found")
    return result


@app.get("/api/governance/generation-runs/{run_id}/questions")
def generation_run_questions(run_id: str):
    try:
        return store.generation_review(run_id, corpus.chunks(), allow_partial=True)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Generation run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/governance/generation-runs/{run_id}/export")
def export_generation_run(run_id: str, format: Literal["json", "csv", "markdown"] = "markdown"):
    try:
        review = store.generation_review(run_id, corpus.chunks())
    except KeyError:
        raise HTTPException(status_code=404, detail="Generation run not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    extension = {"json": "json", "csv": "csv", "markdown": "md"}[format]
    headers = {"Content-Disposition": f'attachment; filename="golden_candidate_{run_id}.{extension}"', "Cache-Control": "no-store"}
    if format == "json":
        return Response(json.dumps(review, ensure_ascii=False), media_type="application/json; charset=utf-8", headers=headers)
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "test_category", "question", "reference_answer", "document", "page", "chunk_ids", "probe_score", "probe_status", "qc_score", "qc_status", "review_status"])
        for item in review["questions"]:
            chunks = [chunk for evidence in item["evidence_details"] for chunk in evidence["chunks"]]
            values = [item["id"], item["test_category"], item["question"], item["reference_answer"], "; ".join(dict.fromkeys(chunk["document_name"] or "当前索引未匹配" for chunk in chunks)), "; ".join(dict.fromkeys(f'{chunk["page_start"]}–{chunk["page_end"]}' for chunk in chunks if chunk["page_start"] is not None)), json.dumps([chunk["chunk_id"] for chunk in chunks], ensure_ascii=False), item["probe"]["score"] if item["probe"] else None, item["probe_status"], item["qc"]["score"] if item["qc"] else None, item["qc_status"], item["review_status"]]
            writer.writerow(["'" + str(value) if str(value).lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in values])
        return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)
    profile_name = (store.generation_run(run_id) or {}).get("profile", {}).get("name", "mini").title()
    lines = [f'# V1.3 {profile_name} Candidate · {run_id}', ""]
    for item in review["questions"]:
        lines += [f'## {item["slot"]}', "", f'ID: {item["id"]}', f'类型: {item["test_category"]}', f'属性 / 负向行为: {item["raw"].get("ablation_attribute") or item["raw"].get("expected_behavior") or "—"}', f'问题: {item["question"]}', "", f'参考答案: {item["reference_answer"] or "不适用（负向题）"}', "", "Evidence:"]
        if not item["evidence_details"]:
            lines.append("- 无引用证据（负向边界题）")
        for evidence in item["evidence_details"]:
            for chunk in evidence["chunks"]:
                lines += [f'- Document: {chunk["document_name"] or "当前索引未匹配"}', f'  Section: {chunk["section_path"] or "—"}', f'  Page: {chunk["page_start"] or "—"}–{chunk["page_end"] or "—"}', f'  Chunk ID: {chunk["chunk_id"]}', f'  Evidence Text: {chunk["chunk_text"] or "当前索引未匹配"}']
            lines.append(f'  Evidence Key Points: {"；".join(evidence.get("evidence_key_points", [])) or "—"}')
        probe, qc = item["probe"] or {}, item["qc"] or {}
        lines += ["", "Probe:", f'- Score: {probe.get("score", "未运行")} / {probe.get("threshold") if probe.get("threshold") is not None else "不作为审批阈值"}', f'- Status: {item["probe_status"]}', f'- Classification: {probe.get("probe_details", {}).get("classification", "—")}', f'- Reason: {probe.get("reason", "—")}', "", "QC:", f'- Score: {qc.get("score", "未运行")} / {qc.get("threshold") if qc.get("threshold") is not None else "不作为审批阈值"}', f'- Status: {item["qc_status"]}', f'- Priority: {qc.get("priority", "—")}', f'- Reason: {qc.get("reason", "—")}', f'- Issues: {"；".join(qc.get("issues", [])) or "—"}', "", "Human Review:", f'- Status: {item["review_status"]}', ""]
        if item["revision_history"]:
            lines += ["Revision History:"]
            for revision in item["revision_history"]:
                lines += [f'- {revision["id"]} · {revision["status"]} · v{revision.get("version_from", {}).get(item["id"], 1)} → v{revision.get("version_to", {}).get(item["id"], "—")} · 原因：{revision["reason"]}']
                if item["id"] in revision.get("drafts", {}):
                    before, after = revision["before"][item["id"]], revision["drafts"][item["id"]]
                    lines += [f'  原问题：{before["question"]}', f'  新问题：{after["question"]}', f'  原参考答案：{before["reference_answer"] or "—"}', f'  新参考答案：{after["reference_answer"] or "—"}', f'  变更字段：{"、".join(revision.get("changed_fields", {}).get(item["id"], [])) or "草案未应用"}']
            lines.append("")
    return Response("\n".join(lines), media_type="text/markdown; charset=utf-8", headers=headers)


@app.get("/api/governance/snapshots")
def governance_snapshots(light: bool = False):
    return store.dataset_snapshots(light=light)


@app.post("/api/governance/aliases", status_code=201, dependencies=[Depends(require_trusted_origin)])
def approve_alias(payload: AliasRequest):
    try:
        return store.approve_alias(payload.alias, payload.canonical, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/governance/generate-mini", status_code=202, dependencies=[Depends(require_trusted_origin)])
def generate_mini_golden():
    return generate_golden(GenerationRequest())


@app.post("/api/governance/generate", status_code=202, dependencies=[Depends(require_trusted_origin)])
def generate_golden(payload: GenerationRequest):
    try:
        with CORPUS_LOCK:
            if payload.strategy == 'business_v2':
                from .business_golden import medium_plan, mini_plan
                base = current_coverage_plan(payload.profile, payload.plan_id) if payload.profile == 'mini' else json.loads((corpus.index_dir / 'coverage.json').read_text())
                if base['corpus_fingerprint'] != manifest_identity(current_manifest()):
                    raise ValueError('Topic Plan 已过期')
                planner = mini_plan if payload.profile == 'mini' else medium_plan
                plan = planner(base, corpus.chunks(), {'name':payload.profile, **GENERATION_PROFILES[payload.profile]})
                with store.connection() as connection:
                    connection.execute('INSERT OR IGNORE INTO coverage_plan_previews VALUES (?,?,?)', (plan['plan_id'], json.dumps(plan, ensure_ascii=False), plan['created_at']))
            else:
                plan = current_coverage_plan(payload.profile, payload.plan_id)
            run_id = store.start_generation_run(ai_service.model, payload.profile, coverage_plan=plan)
    except (ValueError, ProviderUnavailable) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_run_mini_generation, args=(run_id, store, ai_service, corpus), daemon=True).start()
    return {"run_id": run_id, "status": "queued", "profile": payload.profile}


@app.post("/api/governance/generation-runs/{generation_run_id}/regenerate-failed", status_code=202, dependencies=[Depends(require_trusted_origin)])
def regenerate_failed(generation_run_id: str):
    try:
        store.claim_regeneration(generation_run_id, manifest_identity(current_manifest()))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Generation run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_run_mini_generation, args=(generation_run_id, store, ai_service, corpus), kwargs={"regenerate": True}, daemon=True).start()
    return {"run_id": generation_run_id, "status": "generating"}


@app.post("/api/governance/generation-runs/{generation_run_id}/resume-quality", status_code=202, dependencies=[Depends(require_trusted_origin)])
def resume_generation_quality(generation_run_id: str):
    try:
        store.claim_quality_resume(generation_run_id, manifest_identity(current_manifest()))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Generation run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_run_mini_generation, args=(generation_run_id, store, ai_service, corpus), kwargs={"resume_quality": True}, daemon=True).start()
    return {"run_id": generation_run_id, "status": "probing"}


def _run_mini_generation(run_id, run_store, service, run_corpus, *, regenerate=False, resume_quality=False, paid_run=None):
    from .paid_run import controlled_run
    if paid_run is not None and (regenerate or not resume_quality):
        raise ValueError('Controlled paid run only permits existing quality work')
    # Pass the run explicitly: ContextVars are not inherited by background threads.
    with controlled_run(paid_run):
        return _run_mini_generation_work(run_id,run_store,service,run_corpus,regenerate=regenerate,resume_quality=resume_quality)


def _run_mini_generation_work(run_id, run_store, service, run_corpus, *, regenerate=False, resume_quality=False):
    from .paid_run import current_paid_run
    stage = "generation"
    profile = run_store.generation_run(run_id)["profile"]

    def on_progress(event):
        nonlocal stage
        stage = event["stage"]
        if stage == "generating":
            run_store.persist_generation_attempt(run_id, event.get("candidate"), event["slot_audit"], slot=event["slot"], attempt=event["attempt"], model=service.model, slot_complete=event.get("slot_complete"))
        else:
            run_store.update_generation_run(run_id, status=stage, coverage_plan=event.get("coverage_plan"), progress={key: event[key] for key in ("stage", "slot", "attempt", "completed_slots") if key in event})

    try:
        chunks = run_corpus.chunks()
        frozen = run_store.generation_run(run_id)['artifacts']['hard_validation'].get('frozen_plan')
        if frozen:
            from .golden_v2 import digest
            if frozen['corpus_fingerprint'] != manifest_identity(current_manifest()) or frozen['chunk_fingerprint'] != digest(sorted(chunks, key=lambda item: item['chunk_id'])):
                raise ValueError('Coverage Plan 已失效：Corpus 已变化')
        complete = resume_quality
        for round_number in ([] if resume_quality else range(1, 4 if regenerate and not (frozen and frozen.get('generation_strategy') == 'business_v2') else 2)):
            if regenerate:
                run = run_store.generation_run(run_id)
                remaining_before = len(run["artifacts"]["coverage_plan"]) - len(run["question_ids"])
                by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
                passed = [run_store.question(question_id) for question_id in run["question_ids"]]
                existing = [{"coverage_slot": row["raw"]["coverage_slot"], "test_category": row["test_category"], "question": row["question"], "reference_answer": row["reference_answer"], "evidence": row["evidence"], "expected_behavior": row["raw"].get("expected_behavior"), "negative_subtype": row["negative_subtype"], "ablation_attribute": row["raw"].get("ablation_attribute")} for row in passed]
                prior_audit = run["artifacts"]["slot_audit"]
                plan = []
                for slot in run["artifacts"]["coverage_plan"]:
                    source_ids = slot.get("material_chunk_ids") or slot.get("evidence_chunk_ids") or []
                    if not source_ids or any(chunk_id not in by_id for chunk_id in source_ids):
                        raise ValueError(f"{slot['slot']} 原始 Coverage 材料不可用")
                    if not run['artifacts']['hard_validation'].get('frozen_plan') and slot["slot"] in prior_audit and len(prior_audit[slot["slot"]]) > 2 and prior_audit[slot["slot"]][-1]["validation_error"]:
                        original = by_id[source_ids[0]]
                        alternatives = [chunk for chunk in chunks if chunk["chunk_id"] not in source_ids and (chunk.get("document_id") == original.get("document_id") or original.get("product") and chunk.get("product") == original.get("product"))]
                        alternative = next(iter(sorted(alternatives, key=lambda chunk: chunk.get("document_id") != original.get("document_id"))), None)
                        if alternative:
                            source_ids = [alternative["chunk_id"]]
                            slot = {**slot, "material_chunk_ids": source_ids, "evidence_chunk_ids": source_ids if slot["test_category"] != "negative" else [], "selected_reason": "same_product_retry", "structured_type": None}
                    plan.append({**slot, "sources": [by_id[chunk_id] for chunk_id in source_ids]})
                generated = service.generate_mini_golden(chunks, on_progress=on_progress, plan=plan, existing=existing, prior_audit=prior_audit, profile=profile, coverage_plan=run['artifacts']['hard_validation'].get('frozen_plan'))
            else:
                frozen = run_store.generation_run(run_id)['artifacts']['hard_validation'].get('frozen_plan')
                kwargs = {'profile': profile}
                if frozen:
                    from .golden_v2 import digest
                    if frozen['corpus_fingerprint'] != manifest_identity(current_manifest()) or frozen['chunk_fingerprint'] != digest(sorted(chunks, key=lambda item: item['chunk_id'])):
                        raise ValueError('Coverage Plan 已失效：Corpus 已变化')
                    known = {c['chunk_id']: c for c in chunks}
                    kwargs['coverage_plan'] = frozen
                    kwargs['plan'] = [{**slot, 'sources': [known[key] for key in slot['material_chunk_ids']]} for slot in frozen['slots']]
                elif profile.get('name', 'mini') == 'mini':
                    kwargs = {}
                generated = service.generate_mini_golden(chunks, on_progress=on_progress, **kwargs)
            failed_slots = generated.get("failed_slots", [])
            continue_refill = regenerate and not (frozen and frozen.get('generation_strategy') == 'business_v2') and round_number < 3 and 0 < len(failed_slots) < remaining_before
            complete = run_store.complete_generation_slots(run_id, failed_slots=failed_slots, hard_validation=generated["hard_validation"], continue_refill=continue_refill)
            if complete or not continue_refill:
                break
        if not complete:
            return
        saved = [run_store.question(question_id) for question_id in run_store.generation_run(run_id)["question_ids"]]
        stage = "probing"
        run_store.update_generation_run(run_id, status="probing", progress={"stage": "probing", "probe_completed": 0, "qc_skipped": 0})
        qc_completed = qc_skipped = 0
        probe_completed = 0
        business_run = bool(frozen and frozen.get('generation_strategy') == 'business_v2')
        quality_state = run_store.generation_run(run_id, qualification=False)['artifacts']['hard_validation']
        quality_errors = dict(quality_state.get('business_quality_errors', {}))
        business_usage = dict(quality_state.get('business_provider_usage', {}))
        for index, candidate in enumerate(saved, start=1):
            if business_run:
                quality_error = None
                try:
                    from .telemetry import collect_usage
                    with collect_usage() as calls:
                        _business_quality_step(run_store, service, run_corpus, candidate, saved)
                    quality_errors.pop(candidate['id'], None)
                except Exception as error:
                    quality_error = error
                    quality_errors[candidate['id']] = str(error)
                    extra_usage = getattr(error, 'token_usage', [])
                    calls.extend([u for u in extra_usage if u not in calls] if current_paid_run() else extra_usage)
                finally:
                    business_usage[candidate['id']] = [*business_usage.get(candidate['id'], []), *calls]
                checked = run_store.question(candidate['id'])
                probe_completed += checked['probe_status'] != 'probe_pending'
                qc_completed += checked['qc_status'] in {'qc_passed','qc_failed'}
                qc_skipped += checked['probe_status'] not in {'probe_pending','probe_passed'}
                run_store.update_generation_run(run_id, status='qc', progress={'stage':'qc','probe_completed':probe_completed,'qc_completed':qc_completed,'qc_skipped':qc_skipped,'quality_processed':index,'slot':candidate['raw']['coverage_slot']}, validation={'business_quality_errors':quality_errors,'business_provider_usage':business_usage})
                if quality_error is not None and current_paid_run():
                    raise quality_error
                continue
            stage = "probing"
            prior_probe = run_store.probe_history(candidate["id"])[0] if (resume_quality or regenerate) and candidate["probe_status"] == "probe_passed" else None
            _, identity = run_store.capture_quality(candidate["id"])
            reusable = prior_probe and all(prior_probe.get("execution_identity", {}).get(key) == identity[key] for key in ('content_hash', 'active_candidate', 'corpus_fingerprint'))
            prior_qc = run_store.qc_history(candidate["id"])
            if reusable and prior_qc and prior_qc[0]["result"].get("execution_identity") == identity and candidate["qc_status"] == "qc_passed":
                qc_completed += 1
                continue
            probe = {"status": "passed"} if reusable else run_store.run_probe(candidate["id"], service.retriever, run_corpus.chunks(), service.answerability_check, subtype_judge=service.negative_subtype_check, fail_on_judge_error=bool(current_paid_run()))
            _require_probe_execution(probe)
            run_store.update_generation_run(run_id, status="probing", progress={"stage": "probing", "slot": candidate["raw"].get("coverage_slot"), "probe_completed": index})
            if probe["status"] == "passed":
                stage = "qc"
                _quality_check(run_store, service, candidate["id"])
                qc_completed += 1
            else:
                qc_skipped += 1
            run_store.update_generation_run(run_id, status="qc", progress={"stage": "qc", "slot": candidate["raw"].get("coverage_slot"), "qc_completed": qc_completed, "qc_skipped": qc_skipped})
        stage = "completed"
        run_store.update_generation_run(run_id, status="completed", progress={"stage": "completed"})
    except Exception as error:
        if current_paid_run(): current_paid_run().stop(type(error).__name__)
        run_store.update_generation_run(run_id, status="failed", validation={"error": str(error), "failed_stage": stage}, progress={"stage": "failed"})


@app.post("/api/governance/generation-runs/{generation_run_id}/rerun-quality", status_code=202, dependencies=[Depends(require_trusted_origin)])
def rerun_generation_quality(generation_run_id: str, anomalies_only: bool = False):
    try:
        run = store.generation_run(generation_run_id)
        expected = store._expected_count(run) if run else 0
        ids = store.update_quality_rerun(generation_run_id, {"status": "running", "stage": "probe", "completed": 0, "total": expected, "probe_passed": 0, "probe_failed": 0, "qc_passed": 0, "qc_failed": 0, "qc_skipped": 0, "slots": {}, "started_at": datetime.now(timezone.utc).isoformat()}, start=True, anomalies_only=anomalies_only)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Generation run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_run_quality_rerun, args=(generation_run_id, ids, store, ai_service, corpus), daemon=True).start()
    return {"run_id": generation_run_id, "status": "running"}


def _business_quality_step(run_store, service, run_corpus, candidate, peers):
    row = run_store.candidate_rows([candidate['id']])[0]
    if not row['quality_audit']:
        audit = service.business_quality_audit(candidate, [item['question'] for item in peers if item['id'] != candidate['id']])
        run_store.save_quality_audit(candidate['id'], audit)
    if candidate['probe_status'] != 'probe_passed':
        probe = run_store.run_probe(candidate['id'], service.retriever, run_corpus.chunks(), service.answerability_check, subtype_judge=service.negative_subtype_check, fail_on_judge_error=True)
        _require_probe_execution(probe)
        if probe['status'] != 'passed':
            return
    if candidate['qc_status'] not in {'qc_passed','qc_failed'}:
        _quality_check(run_store, service, candidate['id'])


def _require_probe_execution(probe):
    from .paid_run import current_paid_run
    if current_paid_run() and (probe.get('classification') == 'RETRIEVAL_EXECUTION_FAILED' or probe.get('probe_details',{}).get('probe_execution_status') == 'failed'):
        raise ProviderUnavailable('Probe retrieval execution failed; controlled paid run stopped')


def _quality_check(run_store, service, question_id):
    item, execution = run_store.capture_quality(question_id, qc=True)
    qc = service.quality_check(item)
    return qc, run_store.record_qc(question_id, qc, "failed" if qc.get("priority") == "P0" else "passed", execution=execution)


def _run_quality_rerun(run_id, ids, run_store, service, run_corpus):
    counters = {"completed": 0, "probe_passed": 0, "probe_failed": 0, "qc_passed": 0, "qc_failed": 0, "qc_skipped": 0}
    slots = {}
    try:
        chunks = run_corpus.chunks()
        for index, question_id in enumerate(ids, 1):
            slot = run_store.question(question_id).get("raw", {}).get("coverage_slot") or f"Q{index:02d}"
            run_store.update_quality_rerun(run_id, {**counters, "stage": "probe", "slot": slot, "slots": slots})
            try:
                item = run_store.question(question_id)
                anomaly_run = run_store.generation_run(run_id)["artifacts"]["hard_validation"].get("quality_rerun", {}).get("scope") == "anomalies"
                run_store.reset_qc_for_rerun(question_id)
                prior_probe = run_store.probe_history(question_id)
                _, identity = run_store.capture_quality(question_id)
                reusable = anomaly_run and item["probe_status"] == "probe_passed" and prior_probe and all(prior_probe[0].get("execution_identity", {}).get(key) == identity[key] for key in ("content_hash", "active_candidate", "corpus_fingerprint"))
                probe = {**prior_probe[0], "status": "passed", "classification": prior_probe[0].get("classification") or prior_probe[0].get("probe_details", {}).get("classification", "not_recorded")} if reusable else run_store.run_probe(question_id, service.retriever, chunks, service.answerability_check, subtype_judge=service.negative_subtype_check, fail_on_judge_error=True)
                counters["probe_passed" if probe["status"] == "passed" else "probe_failed"] += 1
                slots[slot] = {"question_id": question_id, "probe": probe["status"], "classification": probe["classification"], "probe_reason": probe["reason"]}
                if probe["status"] == "passed":
                    run_store.update_quality_rerun(run_id, {**counters, "stage": "qc", "slot": slot, "slots": slots})
                    qc, saved = _quality_check(run_store, service, question_id)
                    counters["qc_passed" if saved["status"] == "qc_passed" else "qc_failed"] += 1
                    slots[slot]["qc"] = saved["status"]
                    slots[slot]["qc_reason"] = qc["reason"]
                else:
                    counters["qc_skipped"] += 1
                    slots[slot]["qc"] = "skipped"
                counters["completed"] += 1
                run_store.update_quality_rerun(run_id, {**counters, "stage": "qc" if probe["status"] == "passed" else "probe", "slot": slot, "slots": slots})
            except Exception as error:
                slots[slot] = {**slots.get(slot, {"question_id": question_id}), "error": str(error), "failed_stage": "qc" if slots.get(slot, {}).get("probe") == "passed" else "probe"}
                raise
        run_store.update_quality_rerun(run_id, {**counters, "status": "completed", "stage": "completed", "slots": slots, "finished_at": datetime.now(timezone.utc).isoformat()})
    except Exception as error:
        run_store.update_quality_rerun(run_id, {**counters, "status": "failed", "stage": "failed", "slots": slots, "error": str(error), "finished_at": datetime.now(timezone.utc).isoformat()})


@app.post("/api/governance/questions/{question_id}/review", dependencies=[Depends(require_trusted_origin)])
def review_question(question_id: str, payload: ReviewRequest):
    try:
        return store.review_question(question_id, payload.decision, payload.actor, reason=payload.reason, tags=payload.tags, accept_qc_p0=payload.accept_qc_p0)
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/governance/revisions")
def revision_runs(generation_run_id: str | None = None, active_only: bool = False):
    return store.revision_runs(generation_run_id,active_only=active_only)


@app.get("/api/governance/revisions/{revision_id}")
def revision_status(revision_id: str):
    try:
        return store.revision_run(revision_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error


@app.post("/api/governance/questions/{question_id}/revision", status_code=202, dependencies=[Depends(require_trusted_origin)])
def create_revision(question_id: str, payload: RevisionRequest):
    if len(payload.tags) != 1 or payload.tags[0] not in {"业务价值偏低", "题型不纯", "表达过于接近原文", "证据不足", "答案不完整", "Subtype 错误", "与其他题重复", "其他"} or not payload.reason.strip():
        raise HTTPException(status_code=422, detail="请选择一项修订原因并填写说明")
    try:
        run = store.start_revision(question_id, payload.mode, payload.reason, payload.paired, payload.changes, corpus.chunks(), tags=payload.tags, replacement=payload.replacement, actor=payload.actor)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Candidate not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=contextvars.copy_context().run, args=(_prepare_revision,run["id"], store, ai_service, corpus), daemon=True).start()
    return {"id": run["id"], "status": "queued"}


def _prepare_revision(revision_id, run_store, service, run_corpus):
    try:
        chunks = run_corpus.chunks()
        run = run_store.revision_run(revision_id)
        generated = run.get("generated_drafts") if run["mode"] == "ai_regenerate" else None
        if run["mode"] == "ai_regenerate":
            if not run.get("material_selection"):
                selection = service.select_revision_material(run, chunks)
                run_store.update_revision(revision_id, material_selection=selection, stage="material_selected")
                run = run_store.revision_run(revision_id)
            run_store.update_revision(revision_id, status="generating", stage="generating")
            def progress(index, total, item_id, drafts):
                run_store.update_revision(revision_id, stage="generating", progress={"current": index, "total": total}, generated_drafts=drafts)
            generated = _generate_revision_with_weak_keyword_repair(run, run_store, service, chunks, generated, progress)
            run_store.update_revision(revision_id, status="queued", stage="generated")
        run_store.prepare_revision(revision_id, chunks, similarity=service.revision_similarity, generated=generated)
    except Exception as error:
        stage = run_store.revision_run(revision_id)["stage"]
        run_store.update_revision(revision_id, status="failed", stage="failed", failed_stage=stage, error=str(error), error_type=type(error).__name__, error_detail=str(error.__cause__ or error))


def _generate_revision_with_weak_keyword_repair(run, run_store, service, chunks, existing=None, on_progress=None):
    # Compatibility name for existing callers; V1.2 has no weak-keyword repair gate.
    generated = dict(existing or {})
    attempts = list(run.get("generation_attempts", []))
    draft_attempt = (run.get("active_draft") or {}).get("number")
    attempts_allowed = (1,) if any(item['raw'].get('generation_path')=='business_question_first' for item in run['before'].values()) else (1,2)
    for attempt in attempts_allowed:
        prompt_run = {**run, 'repair_error': '；'.join(errors) if attempt > 1 else None}
        try:
            generated = _revision_attempt(run_store, run['id'], 'generating', service, lambda: service.generate_revision_drafts(prompt_run, chunks, existing=generated, **({'on_progress': on_progress} if on_progress else {})))
        except Exception as error:
            attempts.append({'question_ids': run['question_ids'], 'draft_attempt': draft_attempt, 'attempt': attempt, 'error': str(error), 'at': datetime.now(timezone.utc).isoformat()})
            run_store.update_revision(run['id'], generation_attempts=attempts)
            raise
        _, errors, _, _ = run_store._validate_revision_drafts(run, chunks, service.revision_similarity, generated)
        attempts.append({'question_ids': run['question_ids'], 'draft_attempt': draft_attempt, 'attempt': attempt, 'at': datetime.now(timezone.utc).isoformat(), 'drafts': generated, 'validation_errors': errors})
        run_store.update_revision(run["id"], generation_attempts=attempts, generated_drafts=generated)
        if not errors or attempt == attempts_allowed[-1]:
            break
        failed_ids = {key for key in run['question_ids'] if any(error.startswith(key + ':') for error in errors)}
        generated = {key: value for key, value in generated.items() if key not in failed_ids}
        run_store.update_revision(run["id"], generated_drafts=generated)
    return generated


@app.post("/api/governance/revisions/{revision_id}/edit-draft", dependencies=[Depends(require_trusted_origin)])
def edit_revision_draft(revision_id: str, payload: RevisionDraftEditRequest):
    try:
        return store.edit_revision_preview(revision_id, payload.changes, payload.expected_hashes, corpus.chunks(), similarity=ai_service.revision_similarity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/governance/revisions/{revision_id}/regenerate-draft", status_code=202, dependencies=[Depends(require_trusted_origin)])
def regenerate_revision_draft(revision_id: str, payload: RevisionDraftRegenerateRequest):
    try:
        run = store.begin_revision_regeneration(revision_id, payload.question_id, payload.expected_hash, material_mode=payload.material_mode, reason=payload.reason, tags=payload.tags, manual_chunk_ids=payload.manual_chunk_ids)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_regenerate_revision_draft, args=(revision_id, store, ai_service, corpus), daemon=True).start()
    return {"id": run["id"], "status": run["status"]}


def _regenerate_revision_draft(revision_id, run_store, service, run_corpus):
    try:
        run = run_store.revision_run(revision_id)
        active = run["active_draft"]
        target = active["question_ids"][0]
        existing = {item_id: run_store._draft_change(run["drafts"][item_id]) for item_id in run["question_ids"] if item_id != target}
        selected = run_store._draft_change(run["drafts"][target])["source_chunk_ids"]
        material = dict(run.get("material_selection") or {})
        if active["kind"] == "reselect":
            manual = active.get("manual_chunk_ids")
            excluded = set(selected) | {key for source in run["before"][target]["evidence"] for key in source.get("source_chunk_ids", [])}
            prompt_run = {**run, "reason": active["reason"], "tags": active["tags"], "changes": {**run["changes"], target: {"context_chunk_ids" if run["before"][target]["test_category"] == "negative" else "source_chunk_ids": manual} if manual is not None else {}}, "force_reselect": True, "exclude_chunk_ids": {target: sorted(excluded)}}
            selection = {target: active["material_selection"]} if active.get("material_selection") else service.select_revision_material({**prompt_run, "question_ids": [target]}, run_corpus.chunks())
            material[target] = selection[target]
            if not active.get("material_selection"):
                run_store.update_revision(revision_id, active_draft={**active, "material_selection": selection[target]}, draft_attempts=[*run["draft_attempts"][:-1], {**run["draft_attempts"][-1], "material_selection": selection[target]}], stage="material_selected")
            selected = selection[target]["chunk_ids"]
        elif target in material and selected:
            material[target] = {**material[target], "chunk_ids": selected}
        prompt_run = {**run, "reason": active.get("reason", run["reason"]), "changes": {**run["changes"], target: {"source_chunk_ids": selected}}, "material_selection": material}
        run_store.update_revision(revision_id, stage="generating")
        generated = _generate_revision_with_weak_keyword_repair(prompt_run, run_store, service, run_corpus.chunks(), existing)
        run_store.finish_revision_regeneration(revision_id, {target: generated[target]}, run_corpus.chunks(), similarity=service.revision_similarity)
    except Exception as error:
        run_store.fail_revision_regeneration(revision_id, str(error))


@app.post("/api/governance/revisions/{revision_id}/discard", dependencies=[Depends(require_trusted_origin)])
def discard_revision_draft(revision_id: str):
    try:
        return store.discard_revision(revision_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/governance/revisions/{revision_id}/apply", status_code=202, dependencies=[Depends(require_trusted_origin)])
def apply_revision(revision_id: str):
    try:
        run = store.apply_revision(revision_id, corpus.chunks(), similarity=ai_service.revision_similarity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=contextvars.copy_context().run, args=(_run_revision_quality,revision_id, store, ai_service, corpus), daemon=True).start()
    return {"id": run["id"], "status": run["status"]}


@app.post("/api/governance/revisions/{revision_id}/resume", status_code=202, dependencies=[Depends(require_trusted_origin)])
def resume_revision(revision_id: str):
    try:
        run = store.revision_run(revision_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error
    if run.get("applied_at"):
        try:
            store.resume_revision_quality(revision_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        worker = _run_revision_quality
    elif run["status"] != "interrupted":
        raise HTTPException(status_code=409, detail="仅中断的 Revision Run 可继续")
    elif run.get("active_draft", {}).get("kind") in {"regenerate", "reselect"}:
        store.update_revision(revision_id, status="generating", stage="generating")
        worker = _regenerate_revision_draft
    elif run.get("active_draft", {}).get("kind") == "edit":
        store.update_revision(revision_id, status="validating", stage="hard_validation")
        worker = _resume_revision_edit
    else:
        store.update_revision(revision_id, status="queued", stage="queued")
        worker = _prepare_revision
    threading.Thread(target=worker, args=(revision_id, store, ai_service, corpus), daemon=True).start()
    return {"id": revision_id, "status": store.revision_run(revision_id)["status"]}


def _resume_revision_edit(revision_id, run_store, service, run_corpus):
    run = run_store.revision_run(revision_id)
    try:
        run_store._finish_preview_attempt(revision_id, run["active_draft"]["changes"], run_corpus.chunks(), similarity=service.revision_similarity)
    except Exception as error:
        run_store.fail_revision_regeneration(revision_id, str(error))


def _run_revision_quality(revision_id, run_store, service, run_corpus):
    results = {}
    try:
        chunks = run_corpus.chunks()
        run = run_store.revision_run(revision_id)
        results = dict(run.get("quality_results") or {})
        for index, item_id in enumerate(run["question_ids"], 1):
            candidate = run_store.question(item_id)
            if candidate['raw'].get('generation_strategy') == 'business_v2' and not run_store.candidate_rows([item_id])[0]['quality_audit']:
                peers = [run_store.question(key)['question'] for key in run_store.generation_run(run['generation_run_id'], qualification=False)['question_ids'] if key != item_id]
                audit = _revision_attempt(run_store, revision_id, 'business_audit', service, lambda: service.business_quality_audit(candidate, peers))
                run_store.save_quality_audit(item_id, audit)
            completed = run_store.revision_quality_step(run, item_id)
            if completed == "done":
                results[item_id] = {"probe": "passed", "qc": "qc_passed"}
                run_store.update_revision(revision_id, progress={"current": index, "total": len(run["question_ids"])}, quality_results=results)
                continue
            if completed == "qc":
                run_store.update_revision(revision_id, status="qc", stage="qc", progress={"current": index - 1, "total": len(run["question_ids"])}, quality_results=results)
            else:
                run_store.update_revision(revision_id, status="probing", stage="probe", progress={"current": index - 1, "total": len(run["question_ids"])}, quality_results=results)
                run_store.reset_qc_for_rerun(item_id)
                probe = _revision_attempt(run_store, revision_id, "probe", service, lambda: run_store.run_probe(item_id, service.retriever, chunks, service.answerability_check, subtype_judge=service.negative_subtype_check, fail_on_judge_error=True))
                results[item_id] = {"probe": probe["status"], "probe_reason": probe.get("reason")}
            if completed == "qc":
                results[item_id] = {"probe": "passed", "probe_reason": (run.get("quality_results") or {}).get(item_id, {}).get("probe_reason")}
            if results[item_id]["probe"] == "passed":
                run_store.update_revision(revision_id, status="qc", stage="qc", quality_results=results)
                qc, saved = _revision_attempt(run_store, revision_id, "qc", service, lambda: _quality_check(run_store, service, item_id))
                results[item_id].update({"qc": saved["status"], "qc_reason": qc.get("reason")})
            else:
                results[item_id]["qc"] = "skipped"
            run_store.update_revision(revision_id, status="probing", stage="probe", progress={"current": index, "total": len(run["question_ids"])}, quality_results=results)
        run_store.finish_revision_quality(revision_id, results)
    except Exception as error:
        run_store.finish_revision_quality(revision_id, results, error=str(error), error_type=type(error).__name__, error_detail=str(error.__cause__ or error))


def _revision_attempt(run_store, revision_id, stage, service, work):
    from .paid_run import current_paid_run
    for attempt in ((1,) if current_paid_run() else (1,2)):
        started = time.perf_counter()
        error = None
        try:
            from .telemetry import collect_usage
            with collect_usage() as usage:
                return work()
        except Exception as caught:
            error = caught
            if current_paid_run() or not isinstance(caught, ProviderTimeout) or attempt == 2:
                raise
        finally:
            run = run_store.revision_run(revision_id)
            history = list(run.get("runtime_attempts") or [])
            history.append({"stage": stage, "attempt": attempt, "error_type": type(error).__name__ if error else None, "error": str(error.__cause__ or error) if error else None, "elapsed_ms": round((time.perf_counter() - started) * 1000), "result": "failed" if error else "passed", "provider": "DeepSeek" if getattr(service, "model", None) else None, "model": getattr(service, "model", None), "token_usage":usage})
            run_store.update_revision(revision_id, runtime_attempts=history)


@app.post("/api/governance/review-batch", dependencies=[Depends(require_trusted_origin)])
def review_mini_batch(payload: BatchReviewRequest):
    """A single explicit operator action writes individual, auditable Human Review decisions."""
    try:
        return store.review_generation_batch(payload.question_ids, payload.actor, confirmed_manual_review=payload.confirmed_manual_review)
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except sqlite3.Error as error:
        logging.getLogger(__name__).exception("Golden freeze database request failed")
        raise HTTPException(status_code=503, detail="Golden 冻结数据库请求失败，请刷新核对 Snapshot 后重试") from error


@app.post('/api/governance/owner-delegated-review',dependencies=[Depends(require_trusted_origin)])
def owner_delegated_review(payload: OwnerDelegatedReviewRequest):
    try:
        return store.review_owner_delegated_batch(payload.generation_run_id,payload.authorization_id,payload.reviews)
    except KeyError as error:
        raise HTTPException(status_code=404,detail='Delegated working set not found') from error
    except (ValueError,OSError) as error:
        raise HTTPException(status_code=409,detail=str(error)) from error


@app.post("/api/governance/generation-runs/{generation_run_id}/snapshot", status_code=201, dependencies=[Depends(require_trusted_origin)])
def create_generation_snapshot(generation_run_id: str):
    try:
        return store.create_generation_snapshot(generation_run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Generation run not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.put("/api/governance/questions/{question_id}", dependencies=[Depends(require_trusted_origin)])
def update_question(question_id: str, payload: QuestionUpdateRequest):
    try:
        return store.update_question(question_id, payload.question.strip(), payload.reference_answer, payload.evidence, payload.actor, chunks=corpus.chunks(), similarity=ai_service.revision_similarity)
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/governance/questions/{question_id}/probe", dependencies=[Depends(require_trusted_origin)])
def probe_question(question_id: str):
    try:
        store.require_generation_ready(question_id)
        result = store.run_probe(question_id, ai_service.retriever, corpus.chunks(), ai_service.answerability_check, subtype_judge=ai_service.negative_subtype_check)
        return {"status": store.question(question_id)["probe_status"], **result}
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/governance/questions/{question_id}/qc", dependencies=[Depends(require_trusted_origin)])
def qc_question(question_id: str):
    try:
        store.require_generation_ready(question_id)
        _, saved = _quality_check(store, ai_service, question_id)
        return saved
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def persisted_evaluation_progress(run):
    if run and run['status']!='completed':
        with store.connection() as connection:
            completed=connection.execute('SELECT count(DISTINCT question_id) FROM evaluation_case_results WHERE run_id=?',(run['id'],)).fetchone()[0]
        result={**run.get('result',{}),'completed':completed,'total':len((run.get('dataset_snapshot') or json.loads(run.get('dataset_snapshot_json','{}'))).get('question_ids',[]))}
        return {**run,'result':result}
    return run


@app.get("/api/evaluation")
def evaluation(active_task: bool = False, light: bool = False):
    identity = store.current_baseline_identity()
    run = store.evaluation_run(identity["current_baseline_id"], light=light) if identity["current_baseline_id"] else None
    if active_task or run is None:
        with store.connection() as connection:
            latest = connection.execute("""SELECT id FROM evaluation_runs WHERE dataset_version_id=?
                AND json_extract(config_json,'$.run_target')='baseline'""" +
                ("" if active_task else " AND status IN ('running','partial','failed')") +
                " ORDER BY created_at DESC,rowid DESC LIMIT 1",(identity['current_golden_id'],)).fetchone()
        if latest:run=persisted_evaluation_progress(store.evaluation_run(latest['id'],light=light))
    return {"runtime_contract":EVALUATION_RUNTIME_CONTRACT, **(run or {"status": "not_run", "data_source": "real", "message": identity["baseline_unavailable_reason"]}), **identity, **({"requires_policy_upgrade":not policy_current(run.get("judge",{}))} if run else {})}


def case_list_row(row, *, light=False):
    result = {**row['result'],'diagnostic_view':row.get('diagnostic_view') or diagnostic_view(row['result'])}
    if light:
        result = {key:value for key,value in result.items() if key!='retrieved_chunks'}
        result['programmatic_metrics'] = {key:value for key,value in result.get('programmatic_metrics',{}).items() if not isinstance(value,(dict,list)) or key=='evidence_coverage'}
        judge = result.get('judge_result',{})
        result['judge_result'] = {key:judge[key] for key in ('correctness','faithfulness','completeness','reason','verdict','behavior_pass') if key in judge}
        result['judge_result']['checks'] = [{key:check[key] for key in ('requirement','met') if key in check} for check in judge.get('checks',[])]
    return {**{k:v for k,v in row.items() if k not in {'result_json','diagnostic_view'}},'result':result, **({'details_loaded':False} if light else {})}


@app.get("/api/bad-cases")
@read_view()
def bad_cases(light: bool = False):
    current=store.current_baseline_identity()['current_baseline_id']
    return [case_list_row(row,light=light) for row in store.bad_case_rows(current) if row["run_id"]==current]


@app.get("/api/bad-cases/{case_id}")
@read_view()
def bad_case(case_id: str):
    with store.connection() as connection:
        row = connection.execute('SELECT * FROM bad_cases WHERE id=?',(case_id,)).fetchone()
    if row is None:raise HTTPException(status_code=404, detail="Bad case not found")
    item = {**dict(row),'result':{**json.loads(row['result_json']),'run_id':row['run_id'],'question_id':row['question_id']}}
    run = store.evaluation_run(row['run_id'])
    return {**case_list_row(item),'dataset_snapshot':json.loads(run['dataset_snapshot_json']) if run else {}}


def experiment_resume_view(experiment):
    runner=EvaluationRunner(store,ai_service)
    candidates=[]
    for candidate in experiment['candidates']:
        if candidate['status']=='failed':
            try:plan=runner.candidate_resume_plan(candidate['id'],manual_resume=True)
            except ValueError as error:plan={'can_resume':False,'reason':str(error)}
            candidate={**candidate,'resume_plan':plan}
        candidates.append(candidate)
    return {**experiment,'candidates':candidates}


@app.get("/api/optimization")
@read_view()
def optimization(light: bool = False, planning: bool = False):
    identity = store.current_baseline_identity()
    experiment, coverage, rows = None, None, []
    if identity['current_experiment_id']:
        if planning or not light:
            from .agent_coverage import coverage_inputs
            experiment, _, rows, _, coverage = coverage_inputs(store, identity['current_experiment_id'])
        else:
            experiment = store.experiment(identity['current_experiment_id'])
    if experiment is None:
        return {"status": "not_run", **({"bad_cases":bad_cases(light=True)} if planning else {}), "data_source": "real", "message": identity["baseline_unavailable_reason"] or "当前 Baseline 尚未运行 Optimization Agent", **identity}
    if light:
        result = light_value({**(experiment_resume_view(experiment) if planning else experiment),
            'data_source':'real','recommendation':store.recommendation(experiment['id']),**identity})
        if planning:
            result.update(coverage_plan=coverage, bad_cases=[case_list_row(row,light=True) for row in rows])
        return result
    return {**experiment_resume_view(experiment), "coverage_plan":coverage, "data_source": "real", "recommendation": store.recommendation(experiment["id"]), **identity}


@app.get("/api/versions")
def versions(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=50)):
    rows=sorted(store.production_versions(),key=lambda r:r['status']!='active')
    return rows[(page-1)*limit:page*limit]


@app.get("/api/pipeline")
def pipeline():
    knowledge_state = knowledge()
    identity = store.current_baseline_identity()
    baseline = store.evaluation_run(identity["current_baseline_id"]) if identity["current_baseline_id"] else None
    active = store.active_production()
    draft = store.pipeline_draft()
    return {
        **identity,
        "config_draft": draft,
        "data_version": hashlib.sha256(json.dumps([identity, draft, active["id"] if active else None, knowledge_state["identity"], knowledge_state["coverage_status"]], sort_keys=True).encode()).hexdigest(),
        "draft_identity": identity,
        "frozen_models": {"generation": ai_service.provider.settings.model, "judge": ai_service.provider.settings.model},
        "draft_stale": bool(draft and draft["identity"] != identity),
        "active_version_id": active["id"] if active else None,
        "config": active["config"] if active else DEFAULT_PIPELINE_CONFIG,
        "baseline_id": baseline["id"] if baseline else None,
        "baseline_config": baseline["config"] if baseline else None,
        "search_space": search_space_contract(),
        "locked_parameters": sorted(EXCLUDED_AUTOMATIC_PARAMETERS),
        "index": knowledge_state["index"],
        "knowledge": knowledge_state,
        "pricing": price_config(),
        "last_execution_metrics": next((row.get("metrics") for row in store.monitoring_events() if row.get("metrics", {}) and row["metrics"].get("stages")), None),
    }


class PipelineDraftRequest(BaseModel):
    config: dict | None = None
    identity: dict


@app.post("/api/pipeline/draft", dependencies=[Depends(require_trusted_origin)])
def save_pipeline_draft(payload: PipelineDraftRequest):
    identity = store.current_baseline_identity()
    if payload.identity != identity:
        raise HTTPException(status_code=409, detail="配置基准已变化，请刷新后保存草稿")
    if payload.config is not None:
        validation = validate_candidate_config(payload.config)
        if not validation["valid"]:
            raise HTTPException(status_code=422, detail="；".join(validation["errors"]))
    draft = store.save_pipeline_draft({"config": payload.config, "identity": identity} if payload.config is not None else None)
    return {"config_draft": draft, "identity": identity}


@app.get("/api/monitoring")
def monitoring(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=50)):
    all_events = store.monitoring_events()
    events=all_events[(page-1)*limit:page*limit]
    active = store.active_production()
    confirmed = [e for e in all_events if e.get('bad_case') and e.get('determinable') and e.get('source', {}).get('production_version_id') == (active or {}).get('id')]
    event_ids={e['id'] for e in events};triggers={}
    for trigger in store.optimization_triggers():
        if trigger['event_id'] in event_ids:triggers.setdefault(trigger['event_id'],trigger)
    return {"events": events, "triggers": list(triggers.values()), "recommendation": {"status": "needs_human_review" if confirmed else "insufficient_signal", "event_ids": [e['id'] for e in confirmed], "reason": "已有人工判定QA失败，建议核对影响与兼容回滚范围；不自动回滚" if confirmed else "已有QA信号不足以建议回滚；不产生额外监测或Judge调用"}, **store.current_baseline_identity()}


@app.post("/api/monitoring/events", status_code=201, dependencies=[Depends(require_trusted_origin)])
def record_monitoring_event(payload: MonitoringEventRequest):
    try:
        event = store.record_monitoring_event(question=payload.question, answer=payload.answer, bad_case=payload.bad_case, severity=payload.severity, determinable=payload.determinable)
        return {"event": event, "trigger": store.optimization_trigger_for_event(event["id"])}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/monitoring/events/{event_id}/assessment", dependencies=[Depends(require_trusted_origin)])
def assess_monitoring_event(event_id: str, payload: MonitoringAssessmentRequest):
    try:
        event = store.assess_monitoring_event(event_id, bad_case=payload.bad_case, severity=payload.severity)
        return {"event": event, "trigger": store.optimization_trigger_for_event(event_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Monitoring event not found")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/monitoring/triggers/{trigger_id}/confirm", dependencies=[Depends(require_trusted_origin)])
def confirm_monitoring_trigger(trigger_id: str, payload: ReviewRequest):
    if payload.decision != "approved":
        raise HTTPException(status_code=422, detail="Human Confirm 必须为 approved；拒绝时保留 Pending Trigger 供人工处理")
    try:
        return store.confirm_optimization_trigger(trigger_id, payload.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="Optimization Trigger not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/readiness")
def readiness():
    return ai_service.readiness()


@app.post("/api/ai-readiness/probe", dependencies=[Depends(require_trusted_origin)])
def probe_readiness():
    return ai_service.probe()


@app.post("/api/experiments/run", status_code=201, dependencies=[Depends(require_trusted_origin)])
def run_experiments(payload: ExperimentRequest | None = None):
    completed = require_current_baseline()
    try:
        return OptimizationAgent(store, ai_service.provider).generate(completed["id"], payload.trigger_id if payload else None)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/direct-release", status_code=201, dependencies=[Depends(require_trusted_origin)])
def start_direct_release(payload: DirectReleaseRequest):
    raise HTTPException(status_code=409, detail='V1.2 请经过 A/B/C Sandbox、Gate 2 报告确认及 D 决策后发布；历史 Direct Release 仅保留审计')


@app.get("/api/experiments/{run_id}")
def experiment(run_id: str):
    result = store.experiment(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result


class CoveragePlanRequest(BaseModel):
    binding: str


@app.post("/api/experiments/{run_id}/complete-plan", dependencies=[Depends(require_trusted_origin)])
def complete_experiment_plan(run_id: str, payload: CoveragePlanRequest):
    from .agent_coverage import complete_coverage
    try:
        backup=store.database_path.parent/'audit_backups'/f"coverage-{datetime.now().strftime('%Y%m%d%H%M%S%f')}.db"
        return complete_coverage(store,run_id,expected_binding=payload.binding,backup_path=backup)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/continue", dependencies=[Depends(require_trusted_origin)])
def continue_experiment(run_id: str):
    experiment = store.experiment(run_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    require_current_baseline(experiment["baseline_run_id"])
    try:
        return OptimizationAgent(store, ai_service.provider).generate(experiment["baseline_run_id"], experiment_id=run_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/recommendation", dependencies=[Depends(require_trusted_origin)])
def select_recommendation(run_id: str, payload: RecommendationRequest):
    experiment = store.experiment(run_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    require_current_baseline(experiment["baseline_run_id"])
    try:
        return store.select_recommendation(run_id, payload.candidate_id, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


class PaidActionRequest(BaseModel):
    authorize_provider: bool = False


@app.post('/api/experiments/{run_id}/composite', dependencies=[Depends(require_trusted_origin)])
def create_composite(run_id: str, payload: PaidActionRequest | None = None):
    experiment = store.experiment(run_id)
    if experiment is not None:
        require_current_baseline(experiment["baseline_run_id"])
    try:
        return store.create_composite(run_id, ai_service.provider, bool(payload and payload.authorize_provider))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/candidates/{candidate_id}/preflight")
def candidate_preflight(candidate_id: str):
    try:
        approved, config, candidate, baseline = EvaluationRunner(store, ai_service).candidate_inputs(candidate_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    resume=EvaluationRunner(store,ai_service).candidate_resume_plan(candidate_id,manual_resume=True)
    return {"resume_plan":resume,"can_start":resume["can_resume"],"candidate_id": candidate["id"], "baseline_run_id": baseline["id"],
            "snapshot_id": baseline["dataset_version_id"], "question_count": len(approved),
            "evaluation_identity": baseline["judge"]["evaluation_identity"], "judge": baseline["judge"],
            "request_limits": baseline["judge"].get("execution_snapshot", {}).get("request_limits"), "config": config}


@app.post("/api/candidates/{candidate_id}/run", status_code=201, dependencies=[Depends(require_trusted_origin)])
def run_candidate(candidate_id: str, payload: PaidActionRequest | None = None):
    if not payload or not payload.authorize_provider:
        raise HTTPException(409,detail="Sandbox启动与续跑须重新明确付费授权；预检不产生费用")
    candidate = store.candidate(candidate_id)
    if candidate:
        experiment = store.experiment(candidate["experiment_id"])
        if experiment:
            require_current_baseline(experiment["baseline_run_id"])
    runner = EvaluationRunner(store, ai_service)
    try:
        run_id, approved, config, candidate, baseline = runner.start_candidate(candidate_id,automatic=True,manual_resume=payload.authorize_provider)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=contextvars.copy_context().run, args=(runner.execute_candidate,run_id, approved, config, candidate, baseline), daemon=True).start()
    return {"id": run_id, "candidate_id": candidate_id, "status": "running", "run_mode": "real", "data_source": "real"}


@app.post("/api/candidates/{candidate_id}/publish", status_code=201, dependencies=[Depends(require_trusted_origin)])
def publish_candidate(candidate_id: str, payload: ReviewRequest):
    candidate = store.candidate(candidate_id)
    if candidate:
        experiment = store.experiment(candidate["experiment_id"])
        if experiment:
            require_current_baseline(experiment["baseline_run_id"])
    if payload.decision != "approved":
        raise HTTPException(status_code=422, detail="确认发布需要明确批准")
    try:
        return store.publish_candidate(candidate_id, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/versions/{version_id}/rollback", dependencies=[Depends(require_trusted_origin)])
def rollback_version(version_id: str, payload: ReviewRequest):
    if payload.decision != 'approved':
        raise HTTPException(409, '回滚需要明确人工确认')
    try:
        return store.rollback_to(version_id, payload.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="Production version not found")
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.get("/api/tools")
def tools():
    return store.tools()


@app.post("/api/versions/{version_id}/activate")
def activate_version(version_id: str):
    raise HTTPException(status_code=409, detail="版本切换请使用受保护的发布或回滚流程")


@app.get("/api/evaluations")
def evaluation_runs(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=50), active_only: bool = False):
    return store.evaluation_history(page,limit,active_only=active_only)


@app.get("/api/evaluations/{run_id}")
@read_view()
def evaluation_run(run_id: str):
    run = store.evaluation_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    run=persisted_evaluation_progress(run)
    cases = [{**case,"diagnostic_view":diagnostic_view(case)} for case in store.evaluation_case_results(run_id)]
    return {**run, "dataset_snapshot": json.loads(run["dataset_snapshot_json"]), "cases": cases,"requires_policy_upgrade":not policy_current(run.get("judge",{})), "gate_details": gate_details(cases, run.get("result", {}).get("gates", {}).get("gates", []))}


@app.post('/api/evaluations/{run_id}/stop', dependencies=[Depends(require_trusted_origin)])
def stop_evaluation(run_id: str):
    if store.evaluation_run(run_id) is None:
        raise HTTPException(status_code=404,detail='Evaluation run not found')
    store.request_evaluation_stop(run_id)
    return evaluation_run(run_id)


@app.get('/api/evaluations/{source_id}/judge-replay/preflight')
def judge_replay_preflight(source_id: str):
    try:return EvaluationRunner(store,ai_service).judge_replay_preflight(source_id)
    except (ValueError,KeyError) as error:raise HTTPException(409,str(error)) from error


@app.post('/api/evaluations/{source_id}/judge-replay',status_code=201,dependencies=[Depends(require_trusted_origin)])
def judge_replay(source_id: str,payload: PaidActionRequest):
    if not payload.authorize_provider:raise HTTPException(409,'新版Judge-only Baseline会产生Judge费用，必须明确授权；禁止生成模型调用')
    try:
        runner=EvaluationRunner(store,ai_service)
        run_id,items,config=runner.start_judge_replay(source_id)
    except (ValueError,KeyError) as error:raise HTTPException(409,str(error)) from error
    threading.Thread(target=contextvars.copy_context().run,args=(runner.execute_baseline,run_id,items,config),daemon=True).start()
    return {'id':run_id,'status':'running','execution_kind':'judge_only_baseline','generation_calls':0}


class DiagnosticBatchRequest(BaseModel):
    authorize_provider: bool = False
    question_ids: list[str] | None = None
    expected_binding: str
    authorization_id: str
    max_calls: int
    budget_yuan: float
    price_snapshot: dict


@app.get('/api/evaluations/{run_id}/diagnostic-plan')
def get_diagnostic_plan(run_id: str):
    from .evidence_resolver import diagnostic_plan
    try:return diagnostic_plan(store,run_id)
    except ValueError as error:raise HTTPException(409,str(error)) from error


@app.post('/api/evaluations/{run_id}/resolve-diagnostics',dependencies=[Depends(require_trusted_origin)])
def resolve_diagnostic_batch(run_id: str,payload: DiagnosticBatchRequest):
    if not payload.authorize_provider:raise HTTPException(409,'批量补证需要独立费用授权，不能沿用Agent或Baseline授权')
    from .evidence_resolver import execute_diagnostic_batch
    try:
        return execute_diagnostic_batch(store,run_id,ai_service,question_ids=payload.question_ids,expected_binding=payload.expected_binding,
            authorization_id=payload.authorization_id,max_calls=payload.max_calls,budget_yuan=payload.budget_yuan,price_snapshot=payload.price_snapshot)
    except (ValueError,KeyError,TypeError,RuntimeError) as error:raise HTTPException(409,str(error)) from error


@app.get('/api/evaluations/{run_id}/cases/{question_id}/diagnostic-evidence')
def diagnostic_evidence_preflight(run_id: str,question_id: str):
    from .evidence_resolver import resolve_persisted
    from .diagnostics import _current_corpus
    run=store.evaluation_run(run_id)
    if not run:raise HTTPException(404,'Run not found')
    chunks,fingerprint=_current_corpus({'corpus_fingerprint':json.loads(run['dataset_snapshot_json'])['corpus_fingerprint']})
    try:return resolve_persisted(store,run_id,question_id,chunks,fingerprint)
    except ValueError as error:raise HTTPException(409,str(error)) from error


@app.post('/api/evaluations/{run_id}/cases/{question_id}/resolve-diagnostics',dependencies=[Depends(require_trusted_origin)])
def resolve_diagnostics(run_id: str,question_id: str,payload: PaidActionRequest):
    if not payload.authorize_provider:raise HTTPException(409,'语义补证必须明确授权；不会修改历史成绩')
    from .paid_run import current_paid_run
    if current_paid_run() is None:raise HTTPException(409,'请使用批量补证入口冻结题目、调用上限及独立费用预算')
    from .evidence_resolver import resolve_persisted
    from .diagnostics import _current_corpus
    run=store.evaluation_run(run_id)
    if not run:raise HTTPException(404,'Run not found')
    chunks,fingerprint=_current_corpus({'corpus_fingerprint':json.loads(run['dataset_snapshot_json'])['corpus_fingerprint']})
    try:return resolve_persisted(store,run_id,question_id,chunks,fingerprint,semantic=ai_service.resolve_diagnostic,persist=True)
    except ValueError as error:raise HTTPException(409,str(error)) from error


@app.post('/api/evaluations/{source_id}/replay', dependencies=[Depends(require_trusted_origin)])
def replay_evaluation(source_id: str, payload: PaidActionRequest):
    if not payload.authorize_provider:
        raise HTTPException(409, '历史答案评分会调用Judge产生Token费用，请明确授权')
    try:
        runner = EvaluationRunner(store, ai_service)
        run_id, items, executions = runner.start_replay(source_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    threading.Thread(target=runner.execute_replay, args=(run_id, items, executions), daemon=True).start()
    return {'id': run_id, 'status': 'running', 'execution_kind': 'answer_replay', 'release_eligible': False}


def require_baseline_corpus():
    if corpus_manager.state():
        snapshots = store.dataset_snapshots()
        if not snapshots or snapshots[0]['snapshot'].get('corpus_fingerprint') != manifest_identity(current_manifest()):
            raise ValueError('Corpus 已变化；请基于当前知识库重新生成并确认 Golden 测试集')


@app.get('/api/evaluation/preflight')
def baseline_preflight(resume_source_id: str | None = None):
    try:
        require_baseline_corpus()
    except ValueError as error:
        return {'can_start':False,'can_resume':False,'resume_source_id':None,'reason':str(error),'resume_reason':None}
    result=EvaluationRunner(store,ai_service).baseline_preflight(resume_source_id)
    return {**result,'entry_code_sha256':{name:hashlib.sha256(marshal.dumps(fn.__code__,0)).hexdigest() for name,fn in {
        'preflight':EvaluationRunner.baseline_preflight,'start_guard':GovernanceStore.validate_evaluation_start,
        'resume_guard':GovernanceStore.validate_evaluation_resume}.items()}}


class BaselineRunRequest(BaseModel):
    resume_source_id: str | None = None
    fresh: bool = False


@app.post("/api/evaluations/run", status_code=201, dependencies=[Depends(require_trusted_origin)])
def start_evaluation(payload: BaselineRunRequest | None = None):
    runner = EvaluationRunner(store, ai_service)
    try:
        require_baseline_corpus()
        if not payload or not (payload.fresh or payload.resume_source_id):
            raise ValueError('请显式指定fresh:true或resume_source_id，禁止隐式恢复历史任务')
        if payload.fresh and payload.resume_source_id:
            raise ValueError('fresh与resume_source_id不能同时指定')
        source_id = payload.resume_source_id if payload else None
        run_id, approved, config = runner.start_baseline(source_id,automatic=True)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=contextvars.copy_context().run, args=(runner.execute_baseline,run_id, approved, config), daemon=True).start()
    return {"id": run_id, "status": "running", "run_mode": "real", "data_source": "real"}


@app.post("/api/preview", dependencies=[Depends(require_trusted_origin)])
def preview(payload: PreviewRequest):
    result = ai_service.preview(payload.question)
    baseline = result.get("baseline", {})
    if result.get("mode") in {"live", "local"} and not result.get("fallback_reason"):
        event = store.record_monitoring_event(question=payload.question, answer=baseline.get("answer", ""), bad_case=False, severity="ordinary", determinable=False, source={"production_version_id": baseline["version"], "production_config": baseline["config"], "corpus_fingerprint": baseline.get("corpus_fingerprint")} if baseline.get("version") and baseline.get("config") else None, metrics={key: baseline.get(key) for key in ("stages", "token_usage", "estimated_cost", "cost_estimation", "ttft_ms", "retrieval_trace", "latency_ms", "input_tokens", "output_tokens")})
        result["monitoring_event_id"] = event["id"]
    return result


@app.post("/api/preview/baseline", dependencies=[Depends(require_trusted_origin)])
def preview_baseline(payload: PreviewRequest):
    return ai_service.baseline_preview(payload.question)


@app.post("/api/preview/candidate", dependencies=[Depends(require_trusted_origin)])
def preview_candidate(payload: PreviewRequest):
    return ai_service.candidate_preview(payload.question)


@app.post("/api/preview/scheme", dependencies=[Depends(require_trusted_origin)])
def preview_scheme(payload: SchemePreviewRequest):
    scheme_id = payload.scheme_id
    if scheme_id == "baseline":
        identity = store.current_baseline_identity()
        run = store.evaluation_run(identity["current_baseline_id"]) if identity["current_baseline_id"] else None
        if not run:
            raise HTTPException(status_code=404, detail="Baseline not found")
        config, version, source = run["config"], run["id"], "baseline"
    else:
        candidate = store.candidate(scheme_id)
        version_row = next((row for row in store.production_versions() if row["id"] == scheme_id), None)
        if candidate:
            config, version, source = candidate["config"], candidate["id"], "candidate"
        elif version_row:
            config, version, source = version_row["config"], version_row["id"], "production"
        else:
            raise HTTPException(status_code=404, detail="Scheme not found")
    if source == 'candidate':
        execution = store.evaluation_run(candidate.get('result', {}).get('evaluation_run_id'))
        bound = (execution or {}).get('config', {}).get('knowledge_identity')
    elif source == 'production': bound = version_row.get('snapshot', {}).get('knowledge_identity')
    else: bound = config.get('knowledge_identity')
    result = ai_service.answer(payload.question, {**config, **({'knowledge_identity': bound} if bound else {})})
    return {"pipeline": source, "question": payload.question, "scheme_id": scheme_id, "version": version, "config": config, "status": "completed", **result, "evidence": result["retrieval"], "fallback_reason": None}


@app.post("/api/evaluations/live", dependencies=[Depends(require_trusted_origin)])
def live_evaluation(payload: EvaluationRequest):
    raise HTTPException(status_code=410, detail="旧评测接口已停用；请使用 /api/evaluations/run 创建可审计正式评测")
