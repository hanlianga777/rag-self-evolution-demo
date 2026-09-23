import os
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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


class BatchReviewRequest(BaseModel):
    question_ids: list[str] = Field(min_length=1, max_length=20)
    actor: str = Field(default="local_user", min_length=1, max_length=80)


class DirectReleaseRequest(BaseModel):
    config: dict
    actor: str = Field(default="local_user", min_length=1, max_length=80)


class ExperimentRequest(BaseModel):
    trigger_id: str | None = None


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


@app.post("/api/governance/aliases", status_code=201, dependencies=[Depends(require_trusted_origin)])
def approve_alias(payload: AliasRequest):
    try:
        return store.approve_alias(payload.alias, payload.canonical, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/governance/generate-mini", status_code=201, dependencies=[Depends(require_trusted_origin)])
def generate_mini_golden():
    try:
        candidates = ai_service.generate_mini_golden(corpus.chunks())
        saved = store.save_mini_golden_candidates(candidates, ai_service.model)
        for candidate in saved:
            probe = store.run_probe(candidate["id"], ai_service.retriever, corpus.chunks())
            if probe["status"] == "passed":
                qc = ai_service.quality_check(store.question(candidate["id"]))
                store.record_qc(candidate["id"], qc, "passed" if qc["score"] >= 85 else "failed")
        return {"profile": {"positive": 8, "ablation": 4, "negative": 8}, "candidates": [store.question(item["id"]) for item in saved]}
    except Exception as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/governance/questions/{question_id}/review", dependencies=[Depends(require_trusted_origin)])
def review_question(question_id: str, payload: ReviewRequest):
    try:
        return store.review_question(question_id, payload.decision, payload.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/governance/review-batch", dependencies=[Depends(require_trusted_origin)])
def review_mini_batch(payload: BatchReviewRequest):
    """A single explicit operator action writes individual, auditable Human Review decisions."""
    try:
        candidates = [store.question(question_id) for question_id in payload.question_ids]
        runs = {item["raw"].get("generation_run_id") for item in candidates}
        if len(candidates) != 20 or len(runs) != 1 or None in runs or any(item["raw"].get("generation_profile") != "v1-mini-8-4-8" for item in candidates):
            raise ValueError("Batch review only accepts one complete V1 Mini generation run")
        reviewed = [store.review_question(question_id, "approved", payload.actor) for question_id in payload.question_ids]
        return {"reviewed": reviewed, "snapshot": store.create_dataset_snapshot()}
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.put("/api/governance/questions/{question_id}", dependencies=[Depends(require_trusted_origin)])
def update_question(question_id: str, payload: QuestionUpdateRequest):
    try:
        return store.update_question(question_id, payload.question.strip(), payload.reference_answer, payload.evidence, payload.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="Golden question not found")


@app.post("/api/governance/questions/{question_id}/probe", dependencies=[Depends(require_trusted_origin)])
def probe_question(question_id: str):
    try:
        result = store.run_probe(question_id, ai_service.retriever, corpus.chunks())
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
        return store.record_qc(question_id, {"score": 0, "priority": "P0", "reason": str(error), "model": ai_service.model}, "failed")


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
    return {"status": "not_run", "data_source": "real", "message": "需先完成真实 Baseline Evaluation"}


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
    try:
        return store.approve("candidate", candidate_id, payload.decision, payload.actor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/candidates/{candidate_id}/release-approval", dependencies=[Depends(require_trusted_origin)])
def approve_release(candidate_id: str, payload: ReviewRequest):
    if store.candidate(candidate_id) is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
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
    return ai_service.preview(payload.question)


@app.post("/api/preview/baseline", dependencies=[Depends(require_trusted_origin)])
def preview_baseline(payload: PreviewRequest):
    return ai_service.baseline_preview(payload.question)


@app.post("/api/preview/candidate", dependencies=[Depends(require_trusted_origin)])
def preview_candidate(payload: PreviewRequest):
    return ai_service.candidate_preview(payload.question)


@app.post("/api/evaluations/live", dependencies=[Depends(require_trusted_origin)])
def live_evaluation(payload: EvaluationRequest):
    raise HTTPException(status_code=410, detail="旧评测接口已停用；请使用 /api/evaluations/run 创建可审计正式评测")
