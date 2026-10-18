
from __future__ import annotations

from fastapi import FastAPI
import threading
from contextlib import asynccontextmanager

from app.api.routes.health import router as health_router
from app.api.routes.runs import router as runs_router
from app.db.session import get_session_factory
from app.models.run import Run
from app.services.workflow_runner import run_graph_background

from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: recover stalled runs
    session_factory = get_session_factory()
    with session_factory() as db:
        stalled_runs = db.query(Run).filter(Run.status == "running").all()
        for run in stalled_runs:
            print(f"[RECOVERY] Resuming orphaned run {run.id}...")
            # Fire and forget a thread to resume the run
            threading.Thread(target=run_graph_background, args=(str(run.id), {}), daemon=True).start()
    
    yield
    # Shutdown logic (none required)

def create_app() -> FastAPI:
    """Application factory used by Uvicorn and tests."""
    app = FastAPI(
        title="FlowDocs",
        version="0.1.0",
        description="FlowDocs Backend.",
        lifespan=lifespan,
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(health_router)
    app.include_router(runs_router, prefix="/api/v1")
    return app


app = create_app()
