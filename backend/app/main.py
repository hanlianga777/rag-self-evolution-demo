import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .seed import SeedStore
from .services import DemoService


app = FastAPI(title="RAG Evolution Demo API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"], allow_methods=["*"], allow_headers=["*"])
store = SeedStore()
service = DemoService(store)


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
    configured = bool(os.getenv("DEEPSEEK_API_KEY"))
    return {"mode": "configured" if configured else "mock", "provider": "DeepSeek", "status": "Configured" if configured else "Not Configured"}


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


@app.post("/api/preview")
def preview(payload: dict):
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question is required")
    return service.compare_preview(question)
