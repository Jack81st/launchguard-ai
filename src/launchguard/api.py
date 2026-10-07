"""FastAPI surface for starting, reviewing, resuming, and inspecting launches."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from launchguard.config import Settings
from launchguard.models import ApprovalDecision, SkuEvidence
from launchguard.workflow import LaunchWorkflow


class StartRunRequest(BaseModel):
    sku: SkuEvidence


class RunResponse(BaseModel):
    run: Dict[str, Any]
    interrupt: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]]


def create_app(
    settings: Optional[Settings] = None,
    workflow: Optional[LaunchWorkflow] = None,
) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    runtime_workflow = workflow or LaunchWorkflow(runtime_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if workflow is None:
            runtime_workflow.close()

    app = FastAPI(
        title="LaunchGuard API",
        version="0.1.0",
        description="Durable evidence-to-Shopify launch reviews.",
        lifespan=lifespan,
    )
    app.state.workflow = runtime_workflow

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> HTMLResponse:
        page = Path(__file__).parent / "web" / "static" / "index.html"
        return HTMLResponse(page.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok", "service": "launchguard", "version": "0.1.0"}

    @app.post("/api/runs", response_model=RunResponse, status_code=201)
    def start_run(request: StartRunRequest) -> Dict[str, Any]:
        try:
            return runtime_workflow.start(request.sku)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/runs")
    def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
        return runtime_workflow.list(max(1, min(limit, 100)))

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> Dict[str, Any]:
        try:
            return runtime_workflow.get(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/decision", response_model=RunResponse)
    def decide(run_id: str, decision: ApprovalDecision) -> Dict[str, Any]:
        try:
            return runtime_workflow.resume(run_id, decision)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app
