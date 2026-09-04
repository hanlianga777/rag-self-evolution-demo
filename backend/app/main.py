import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .seed import SeedStore
from .ai_service import AiService
from .config import load_settings
from .providers import DeepSeekProvider
from .services import DemoService


app = FastAPI(title="RAG Evolution Demo API", version="0.1.0")
TRUSTED_ORIGINS = ["http://localhost:5174", "http://127.0.0.1:5174"]
app.add_middleware(CORSMiddleware, allow_origins=TRUSTED_ORIGINS, allow_methods=["*"], allow_headers=["*"])
store = SeedStore()
service = DemoService(store)
ai_service = AiService(store, DeepSeekProvider(load_settings()), os.getenv("RAG_FORCE_MOCK") == "1", service.compare_preview)


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


def require_trusted_origin(request: Request):
    origin = request.headers.get("origin")
    if origin is not None and origin not in TRUSTED_ORIGINS:
        raise HTTPException(status_code=403, detail="Untrusted Origin")


@app.get("/api/overview")
def overview():
    return store.get("overview")


@app.get("/api/workspace")
def workspace():
    return store.get("workspace")


@app.get("/api/documents")
def documents():
    return store.get("documents")


@app.get("/api/dataset")
def dataset():
    return store.get("dataset")


@app.get("/api/evaluation")
def evaluation():
    return store.get("evaluation")


@app.get("/api/bad-cases")
def bad_cases():
    return store.get("bad_cases")


@app.get("/api/bad-cases/{case_id}")
def bad_case(case_id: str):
    for item in store.get("bad_cases"):
        if item["id"] == case_id:
            return item
    raise HTTPException(status_code=404, detail="Bad case not found")


@app.get("/api/optimization")
def optimization():
    return store.get("optimization")


@app.get("/api/versions")
def versions():
    return store.get("versions")


@app.get("/api/readiness")
def readiness():
    return ai_service.readiness()


@app.post("/api/ai-readiness/probe", dependencies=[Depends(require_trusted_origin)])
def probe_readiness():
    return ai_service.probe()


@app.post("/api/experiments/run", status_code=201)
def run_experiments():
    return service.start_experiment()


@app.get("/api/experiments/{run_id}")
def experiment(run_id: str):
    result = service.get_experiment(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result


@app.post("/api/versions/{version_id}/activate")
def activate_version(version_id: str):
    result = service.activate_version(version_id)
    if not result:
        raise HTTPException(status_code=404, detail="Version not found")
    return result


@app.post("/api/preview", dependencies=[Depends(require_trusted_origin)])
def preview(payload: PreviewRequest):
    return ai_service.preview(payload.question)


@app.post("/api/evaluations/live", dependencies=[Depends(require_trusted_origin)])
def live_evaluation(payload: EvaluationRequest):
    return ai_service.evaluate(payload.limit)
