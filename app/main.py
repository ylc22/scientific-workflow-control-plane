import os
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query

from .engine import run_job
from .metrics import Metrics
from .models import JobCreate, JobRecord
from .store import JobStore


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Scientific Workflow Control Plane",
        version="0.1.0",
        description="Demo control plane for reliable scientific workflow execution.",
    )
    store = JobStore(db_path or os.getenv("CONTROL_PLANE_DB", "control_plane.db"))
    metrics = Metrics()
    app.state.store = store
    app.state.metrics = metrics

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/jobs", response_model=JobRecord, status_code=202)
    def submit_job(
        payload: JobCreate,
        background_tasks: BackgroundTasks,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JobRecord:
        if idempotency_key:
            existing = store.get_by_idempotency_key(idempotency_key)
            if existing:
                return existing

        job = store.create(str(uuid4()), payload, idempotency_key)
        metrics.inc("jobs_submitted")
        background_tasks.add_task(run_job, job.id, store, metrics)
        return job

    @app.get("/jobs", response_model=list[JobRecord])
    def list_jobs(limit: int = Query(default=50, ge=1, le=200)) -> list[JobRecord]:
        return store.list(limit)

    @app.get("/jobs/{job_id}", response_model=JobRecord)
    def get_job(job_id: str) -> JobRecord:
        try:
            return store.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.post("/jobs/{job_id}/retry", response_model=JobRecord, status_code=202)
    def retry_job(job_id: str, background_tasks: BackgroundTasks) -> JobRecord:
        try:
            job = store.prepare_retry(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        metrics.inc("job_retries")
        background_tasks.add_task(run_job, job.id, store, metrics)
        return job

    @app.get("/metrics")
    def get_metrics() -> dict:
        jobs = store.list(200)
        by_status: dict[str, int] = {}
        for job in jobs:
            by_status[job.status] = by_status.get(job.status, 0) + 1
        return {"counters": metrics.snapshot(), "jobs_by_status": by_status}

    return app


app = create_app()
