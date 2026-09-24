import csv
import io
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .ai_service import AiService
from .corpus import CorpusStore
from .config import load_settings
from .evaluation import EvaluationRunner
from .governance import GovernanceStore
from .optimization import OptimizationAgent
from .policy import DEFAULT_PIPELINE_CONFIG, validate_candidate_config
from .providers import DeepSeekProvider


app = FastAPI(title="RAG Evolution Demo API", version="0.1.0")
app.mount("/documents", StaticFiles(directory=Path(__file__).resolve().parents[1] / "documents"), name="documents")
TRUSTED_ORIGINS = ["http://localhost:5174", "http://127.0.0.1:5174"]
app.add_middleware(CORSMiddleware, allow_origins=TRUSTED_ORIGINS, allow_methods=["*"], allow_headers=["*"])
store = GovernanceStore()
corpus = CorpusStore()
ai_service = AiService(store, corpus, DeepSeekProvider(load_settings()), os.getenv("RAG_FORCE_MOCK") == "1")
store.interrupt_revision_runs()


class PreviewRequest(BaseModel):
    question: str = Field(strict=True, min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def non_blank_question(cls, value):
        if not value.strip():
            raise ValueError("Question is required")
        return value.strip()


class EvaluationRequest(BaseModel):
    limit: int = Field(default=40, strict=True, ge=1, le=40)


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|needs_revision)$")
    actor: str = Field(default="local_user", min_length=1, max_length=80)
    reason: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=8)


class RevisionRequest(BaseModel):
    mode: Literal["manual_edit", "ai_regenerate"]
    reason: str = Field(min_length=1, max_length=2000)
    paired: bool = False
    changes: dict[str, dict] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=8)


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
    question_ids: list[str] = Field(min_length=1, max_length=20)
    actor: str = Field(default="local_user", min_length=1, max_length=80)
    confirmed_manual_review: bool = False


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


def require_trusted_origin(request: Request):
    origin = request.headers.get("origin")
    if origin is not None and origin not in TRUSTED_ORIGINS:
        raise HTTPException(status_code=403, detail="Untrusted Origin")


@app.get("/api/overview")
def overview():
    summary = store.dataset_summary()
    production = store.active_production()
    latest = [item for item in store.evaluation_runs() if item["status"] != "legacy_unverified"][:1]
    triggers = store.optimization_triggers()
    return {"data_source": "real", "production": production, "dataset": summary, "latest_evaluation": latest[0] if latest else None, "monitoring": {"events": len(store.monitoring_events()), "pending_triggers": sum(item["status"] == "pending_human_confirm" for item in triggers)}}


@app.get("/api/workspace")
def workspace():
    documents = corpus.documents()
    return {"name": "机器人智能问答评测与优化 Agent", "environment": "Production Baseline", "document_count": len(documents), "chunk_count": sum(item["chunks"] for item in documents), "active_version": (store.active_production() or {}).get("id")}


@app.get("/api/documents")
def documents():
    return corpus.documents()


@app.get("/api/documents/{document_id}")
def document_detail(document_id: str):
    result = corpus.detail(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return result


@app.get("/api/dataset")
def dataset():
    return store.questions()


@app.get("/api/governance/summary")
def governance_summary():
    return store.dataset_summary()


@app.get("/api/governance/questions")
def governance_questions(stage: str | None = None):
    return store.questions(stage)


@app.get("/api/governance/generation-runs")
def generation_runs():
    return store.generation_runs()


@app.get("/api/governance/generation-runs/{run_id}")
def generation_run_status(run_id: str):
    result = store.generation_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Generation run not found")
    return result


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
    lines = [f'# V1 Mini Candidate · {run_id}', ""]
    for item in review["questions"]:
        lines += [f'## {item["slot"]}', "", f'ID: {item["id"]}', f'类型: {item["test_category"]}', f'属性 / 负向行为: {item["raw"].get("ablation_attribute") or item["raw"].get("expected_behavior") or "—"}', f'问题: {item["question"]}', "", f'参考答案: {item["reference_answer"] or "不适用（负向题）"}', "", "Evidence:"]
        if not item["evidence_details"]:
            lines.append("- 无引用证据（负向边界题）")
        for evidence in item["evidence_details"]:
            for chunk in evidence["chunks"]:
                lines += [f'- Document: {chunk["document_name"] or "当前索引未匹配"}', f'  Section: {chunk["section_path"] or "—"}', f'  Page: {chunk["page_start"] or "—"}–{chunk["page_end"] or "—"}', f'  Chunk ID: {chunk["chunk_id"]}', f'  Evidence Text: {chunk["chunk_text"] or "当前索引未匹配"}']
            lines.append(f'  Evidence Key Points: {"；".join(evidence.get("evidence_key_points", [])) or "—"}')
        probe, qc = item["probe"] or {}, item["qc"] or {}
        lines += ["", "Probe:", f'- Score: {probe.get("score", "未运行")} / {probe.get("threshold", 90)}', f'- Status: {item["probe_status"]}', f'- Classification: {probe.get("probe_details", {}).get("classification", "—")}', f'- Reason: {probe.get("reason", "—")}', "", "QC:", f'- Score: {qc.get("score", "未运行")} / {qc.get("threshold", 85)}', f'- Status: {item["qc_status"]}', f'- Priority: {qc.get("priority", "—")}', f'- Reason: {qc.get("reason", "—")}', f'- Issues: {"；".join(qc.get("issues", [])) or "—"}', "", "Human Review:", f'- Status: {item["review_status"]}', ""]
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
def governance_snapshots():
    return store.dataset_snapshots()


@app.post("/api/governance/aliases", status_code=201, dependencies=[Depends(require_trusted_origin)])
def approve_alias(payload: AliasRequest):
    try:
        return store.approve_alias(payload.alias, payload.canonical, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/governance/generate-mini", status_code=202, dependencies=[Depends(require_trusted_origin)])
def generate_mini_golden():
    try:
        run_id = store.start_generation_run(ai_service.model)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_run_mini_generation, args=(run_id, store, ai_service, corpus), daemon=True).start()
    return {"run_id": run_id, "status": "queued"}


def _run_mini_generation(run_id, run_store, service, run_corpus):
    stage = "generation"

    def on_progress(event):
        nonlocal stage
        stage = event["stage"]
        run_store.update_generation_run(run_id, status=stage, coverage_plan=event.get("coverage_plan"), validation={key: event[key] for key in ("slot_audit", "valid_slots", "failed_slots", "hard_validation") if key in event}, progress={key: event[key] for key in ("stage", "slot", "attempt", "completed_slots") if key in event})

    try:
        generated = service.generate_mini_golden(run_corpus.chunks(), on_progress=on_progress)
        if generated["status"] == "failed":
            run_store.update_generation_run(run_id, status="failed", validation={**generated["hard_validation"], "slot_audit": generated["slot_audit"], "failed_slots": generated["failed_slots"], "failed_stage": stage}, progress={"stage": "failed"})
            return
        stage = "candidate_persistence"
        saved = run_store.save_mini_golden_candidates(generated["candidates"], service.model, coverage_plan=generated["coverage_plan"], hard_validation=generated["hard_validation"], slot_audit=generated["slot_audit"], run_id=run_id)
        stage = "probing"
        run_store.update_generation_run(run_id, status="probing", progress={"stage": "probing", "probe_completed": 0, "qc_skipped": 0})
        qc_completed = qc_skipped = 0
        for index, candidate in enumerate(saved, start=1):
            stage = "probing"
            probe = run_store.run_probe(candidate["id"], service.retriever, run_corpus.chunks(), service.answerability_check)
            run_store.update_generation_run(run_id, status="probing", progress={"stage": "probing", "slot": candidate["raw"].get("coverage_slot"), "probe_completed": index})
            if probe["status"] == "passed":
                stage = "qc"
                qc = service.quality_check(run_store.question(candidate["id"]))
                run_store.record_qc(candidate["id"], qc, "passed" if qc["score"] >= 85 else "failed")
                qc_completed += 1
            else:
                qc_skipped += 1
            run_store.update_generation_run(run_id, status="qc", progress={"stage": "qc", "slot": candidate["raw"].get("coverage_slot"), "qc_completed": qc_completed, "qc_skipped": qc_skipped})
        stage = "completed"
        run_store.update_generation_run(run_id, status="completed", progress={"stage": "completed"})
    except Exception as error:
        run_store.update_generation_run(run_id, status="failed", validation={"error": str(error), "failed_stage": stage}, progress={"stage": "failed"})


@app.post("/api/governance/generation-runs/{generation_run_id}/rerun-quality", status_code=202, dependencies=[Depends(require_trusted_origin)])
def rerun_generation_quality(generation_run_id: str):
    try:
        ids = store.update_quality_rerun(generation_run_id, {"status": "running", "stage": "probe", "completed": 0, "total": 20, "probe_passed": 0, "probe_failed": 0, "qc_passed": 0, "qc_failed": 0, "qc_skipped": 0, "slots": {}, "started_at": datetime.now(timezone.utc).isoformat()}, start=True)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Generation run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_run_quality_rerun, args=(generation_run_id, ids, store, ai_service, corpus), daemon=True).start()
    return {"run_id": generation_run_id, "status": "running"}


def _run_quality_rerun(run_id, ids, run_store, service, run_corpus):
    counters = {"completed": 0, "probe_passed": 0, "probe_failed": 0, "qc_passed": 0, "qc_failed": 0, "qc_skipped": 0}
    slots = {}
    try:
        chunks = run_corpus.chunks()
        for index, question_id in enumerate(ids, 1):
            slot = f"Q{index:02d}"
            run_store.update_quality_rerun(run_id, {**counters, "stage": "probe", "slot": slot, "slots": slots})
            try:
                run_store.reset_qc_for_rerun(question_id)
                probe = run_store.run_probe(question_id, service.retriever, chunks, service.answerability_check, fail_on_judge_error=True)
                counters["probe_passed" if probe["status"] == "passed" else "probe_failed"] += 1
                slots[slot] = {"question_id": question_id, "probe": probe["status"], "classification": probe["classification"], "probe_reason": probe["reason"]}
                if probe["status"] == "passed":
                    run_store.update_quality_rerun(run_id, {**counters, "stage": "qc", "slot": slot, "slots": slots})
                    qc = service.quality_check(run_store.question(question_id))
                    saved = run_store.record_qc(question_id, qc, "passed" if qc["score"] >= 85 else "failed")
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
        return store.review_question(question_id, payload.decision, payload.actor, reason=payload.reason, tags=payload.tags)
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/governance/revisions")
def revision_runs(generation_run_id: str | None = None):
    return store.revision_runs(generation_run_id)


@app.get("/api/governance/revisions/{revision_id}")
def revision_status(revision_id: str):
    try:
        return store.revision_run(revision_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error


@app.post("/api/governance/questions/{question_id}/revision", status_code=202, dependencies=[Depends(require_trusted_origin)])
def create_revision(question_id: str, payload: RevisionRequest):
    try:
        run = store.start_revision(question_id, payload.mode, payload.reason, payload.paired, payload.changes, corpus.chunks(), tags=payload.tags)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Candidate not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_prepare_revision, args=(run["id"], store, ai_service, corpus), daemon=True).start()
    return {"id": run["id"], "status": "queued"}


def _prepare_revision(revision_id, run_store, service, run_corpus):
    try:
        chunks = run_corpus.chunks()
        run = run_store.revision_run(revision_id)
        generated = run.get("generated_drafts") if run["mode"] == "ai_regenerate" else None
        if run["mode"] == "ai_regenerate":
            run_store.update_revision(revision_id, status="generating", stage="generating")
            def progress(index, total, item_id, drafts):
                run_store.update_revision(revision_id, stage="generating", progress={"current": index, "total": total}, generated_drafts=drafts)
            if not generated or len(generated) < len(run["question_ids"]):
                generated = service.generate_revision_drafts(run, chunks, on_progress=progress, existing=generated)
            run_store.update_revision(revision_id, status="queued", stage="generated")
        run_store.prepare_revision(revision_id, chunks, similarity=service.revision_similarity, generated=generated)
    except Exception as error:
        run_store.update_revision(revision_id, status="failed", stage="failed", error=str(error))


@app.post("/api/governance/revisions/{revision_id}/apply", status_code=202, dependencies=[Depends(require_trusted_origin)])
def apply_revision(revision_id: str):
    try:
        run = store.apply_revision(revision_id, corpus.chunks())
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=_run_revision_quality, args=(revision_id, store, ai_service, corpus), daemon=True).start()
    return {"id": run["id"], "status": run["status"]}


@app.post("/api/governance/revisions/{revision_id}/resume", status_code=202, dependencies=[Depends(require_trusted_origin)])
def resume_revision(revision_id: str):
    try:
        run = store.revision_run(revision_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Revision Run not found") from error
    if run["status"] != "interrupted":
        raise HTTPException(status_code=409, detail="仅中断的 Revision Run 可继续")
    if run.get("applied_at"):
        store.update_revision(revision_id, status="probing", stage="probe")
        worker = _run_revision_quality
    else:
        store.update_revision(revision_id, status="queued", stage="queued")
        worker = _prepare_revision
    threading.Thread(target=worker, args=(revision_id, store, ai_service, corpus), daemon=True).start()
    return {"id": revision_id, "status": "queued"}


def _run_revision_quality(revision_id, run_store, service, run_corpus):
    results = {}
    try:
        chunks = run_corpus.chunks()
        run = run_store.revision_run(revision_id)
        for index, item_id in enumerate(run["question_ids"], 1):
            run_store.update_revision(revision_id, status="probing", stage="probe", progress={"current": index - 1, "total": len(run["question_ids"])}, quality_results=results)
            run_store.reset_qc_for_rerun(item_id)
            probe = run_store.run_probe(item_id, service.retriever, chunks, service.answerability_check, fail_on_judge_error=True)
            results[item_id] = {"probe": probe["status"], "probe_reason": probe.get("reason")}
            if probe["status"] == "passed":
                run_store.update_revision(revision_id, status="qc", stage="qc", quality_results=results)
                qc = service.quality_check(run_store.question(item_id))
                saved = run_store.record_qc(item_id, qc, "passed" if qc["score"] >= 85 else "failed")
                results[item_id].update({"qc": saved["status"], "qc_reason": qc.get("reason")})
            else:
                results[item_id]["qc"] = "skipped"
            run_store.update_revision(revision_id, status="probing", stage="probe", progress={"current": index, "total": len(run["question_ids"])}, quality_results=results)
        run_store.finish_revision_quality(revision_id, results)
    except Exception as error:
        run_store.finish_revision_quality(revision_id, results, error=str(error))


@app.post("/api/governance/review-batch", dependencies=[Depends(require_trusted_origin)])
def review_mini_batch(payload: BatchReviewRequest):
    """A single explicit operator action writes individual, auditable Human Review decisions."""
    try:
        return store.review_generation_batch(payload.question_ids, payload.actor, confirmed_manual_review=payload.confirmed_manual_review)
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


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
        return store.update_question(question_id, payload.question.strip(), payload.reference_answer, payload.evidence, payload.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/governance/questions/{question_id}/probe", dependencies=[Depends(require_trusted_origin)])
def probe_question(question_id: str):
    try:
        result = store.run_probe(question_id, ai_service.retriever, corpus.chunks(), ai_service.answerability_check)
        return {"status": store.question(question_id)["probe_status"], **result}
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")


@app.post("/api/governance/questions/{question_id}/qc", dependencies=[Depends(require_trusted_origin)])
def qc_question(question_id: str):
    try:
        item = store.question(question_id)
        if item["probe_status"] != "probe_passed":
            raise HTTPException(status_code=409, detail="Probe Passed 后才能运行 QC")
        result = ai_service.quality_check(item)
        return store.record_qc(question_id, result, "passed" if result["score"] >= 85 else "failed")
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/evaluation")
def evaluation():
    runs = [item for item in store.evaluation_runs() if item["status"] != "legacy_unverified"]
    return runs[0] if runs else {"status": "not_run", "data_source": "real", "message": "暂无真实实验数据"}


@app.get("/api/bad-cases")
def bad_cases():
    return store.bad_case_rows()


@app.get("/api/bad-cases/{case_id}")
def bad_case(case_id: str):
    for item in store.bad_case_rows():
        if item["id"] == case_id:
            return item
    raise HTTPException(status_code=404, detail="Bad case not found")


@app.get("/api/optimization")
def optimization():
    experiment = store.latest_experiment()
    if experiment is None:
        return {"status": "not_run", "data_source": "real", "message": "需先完成真实 Baseline Evaluation"}
    return {**experiment, "data_source": "real", "recommendation": store.recommendation(experiment["id"])}


@app.get("/api/versions")
def versions():
    return store.production_versions()


@app.get("/api/monitoring")
def monitoring():
    return {"events": store.monitoring_events(), "triggers": store.optimization_triggers()}


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
    completed = next((item for item in store.evaluation_runs() if item["status"] == "completed"), None)
    if completed is None:
        raise HTTPException(status_code=409, detail="需先完成真实 Baseline Evaluation")
    try:
        return OptimizationAgent(store, ai_service.provider).generate(completed["id"], payload.trigger_id if payload else None)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/direct-release", status_code=201, dependencies=[Depends(require_trusted_origin)])
def start_direct_release(payload: DirectReleaseRequest):
    baseline = next((item for item in store.evaluation_runs() if item["status"] == "completed"), None)
    if baseline is None:
        raise HTTPException(status_code=409, detail="Direct Release 仍需先完成真实 Baseline Evaluation")
    config = {**DEFAULT_PIPELINE_CONFIG, **payload.config}
    check = validate_candidate_config(config, prior_configs=[item["config"] for item in store.candidates()], completed_evals=0)
    if not check["valid"]:
        raise HTTPException(status_code=409, detail="Direct Release Config 不符合冻结 Search Space：" + "; ".join(check["errors"]))
    return store.create_direct_release_candidate(baseline["id"], config, payload.actor)


@app.get("/api/experiments/{run_id}")
def experiment(run_id: str):
    result = store.experiment(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result


@app.post("/api/experiments/{run_id}/continue", dependencies=[Depends(require_trusted_origin)])
def continue_experiment(run_id: str):
    experiment = store.experiment(run_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    try:
        return OptimizationAgent(store, ai_service.provider).generate(experiment["baseline_run_id"], experiment_id=run_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/experiments/{run_id}/recommendation", dependencies=[Depends(require_trusted_origin)])
def select_recommendation(run_id: str, payload: RecommendationRequest):
    if store.experiment(run_id) is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    try:
        return store.select_recommendation(run_id, payload.candidate_id, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/candidates/{candidate_id}/run", status_code=201, dependencies=[Depends(require_trusted_origin)])
def run_candidate(candidate_id: str):
    runner = EvaluationRunner(store, ai_service)
    try:
        run_id, approved, config, candidate, baseline = runner.start_candidate(candidate_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=runner.execute_candidate, args=(run_id, approved, config, candidate, baseline), daemon=True).start()
    return {"id": run_id, "candidate_id": candidate_id, "status": "running", "run_mode": "real", "data_source": "real"}


@app.post("/api/candidates/{candidate_id}/approval", dependencies=[Depends(require_trusted_origin)])
def approve_candidate(candidate_id: str, payload: ReviewRequest):
    candidate = store.candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if payload.decision == "approved" and candidate["status"] != "evaluated":
        raise HTTPException(status_code=409, detail="Candidate 必须先完成 Sandbox")
    if payload.decision == "approved" and not candidate["result"].get("qualification", {}).get("qualified"):
        raise HTTPException(status_code=409, detail="Candidate 必须通过 11/11 Gate、Regression 与有效提升后才能进入 Human Release")
    if payload.decision == "approved":
        store.refresh_recommendation(candidate["experiment_id"])
        if error := store.release_gate_error(candidate):
            raise HTTPException(status_code=409, detail=error)
    try:
        return store.approve("candidate", candidate_id, payload.decision, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/candidates/{candidate_id}/release-approval", dependencies=[Depends(require_trusted_origin)])
def approve_release(candidate_id: str, payload: ReviewRequest):
    candidate = store.candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if payload.decision == "approved":
        store.refresh_recommendation(candidate["experiment_id"])
        if error := store.release_gate_error(candidate):
            raise HTTPException(status_code=409, detail=error)
    if (store.latest_approval("candidate", candidate_id) or {}).get("decision") != "approved":
        raise HTTPException(status_code=409, detail="需要 Candidate Approval")
    try:
        return store.approve("release", candidate_id, payload.decision, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/candidates/{candidate_id}/publish", status_code=201, dependencies=[Depends(require_trusted_origin)])
def publish_candidate(candidate_id: str, payload: ReviewRequest):
    try:
        return store.publish_candidate(candidate_id, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/versions/{version_id}/rollback", dependencies=[Depends(require_trusted_origin)])
def rollback_version(version_id: str, payload: ReviewRequest):
    try:
        return store.rollback_to(version_id, payload.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="Production version not found")


@app.get("/api/tools")
def tools():
    return store.tools()


@app.post("/api/versions/{version_id}/activate")
def activate_version(version_id: str):
    raise HTTPException(status_code=409, detail="发布需通过 Release Approval")


@app.get("/api/evaluations")
def evaluation_runs():
    return store.evaluation_runs()


@app.get("/api/evaluations/{run_id}")
def evaluation_run(run_id: str):
    run = next((item for item in store.evaluation_runs() if item["id"] == run_id), None)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return {**run, "cases": store.evaluation_case_results(run_id)}


@app.post("/api/evaluations/run", status_code=201, dependencies=[Depends(require_trusted_origin)])
def start_evaluation():
    runner = EvaluationRunner(store, ai_service)
    try:
        run_id, approved, config = runner.start_baseline()
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    threading.Thread(target=runner.execute_baseline, args=(run_id, approved, config), daemon=True).start()
    return {"id": run_id, "status": "running", "run_mode": "real", "data_source": "real"}


@app.post("/api/preview", dependencies=[Depends(require_trusted_origin)])
def preview(payload: PreviewRequest):
    result = ai_service.preview(payload.question)
    baseline = result.get("baseline", {})
    if result.get("mode") in {"live", "local"} and not result.get("fallback_reason"):
        event = store.record_monitoring_event(question=payload.question, answer=baseline.get("answer", ""), bad_case=False, severity="ordinary", determinable=False)
        result["monitoring_event_id"] = event["id"]
    return result


@app.post("/api/preview/baseline", dependencies=[Depends(require_trusted_origin)])
def preview_baseline(payload: PreviewRequest):
    return ai_service.baseline_preview(payload.question)


@app.post("/api/preview/candidate", dependencies=[Depends(require_trusted_origin)])
def preview_candidate(payload: PreviewRequest):
    return ai_service.candidate_preview(payload.question)


@app.post("/api/evaluations/live", dependencies=[Depends(require_trusted_origin)])
def live_evaluation(payload: EvaluationRequest):
    raise HTTPException(status_code=410, detail="旧评测接口已停用；请使用 /api/evaluations/run 创建可审计正式评测")
