import time

from .store import JobStore
from .metrics import Metrics

STEPS = ("ingest", "validate", "analyze", "publish")


def run_job(job_id: str, store: JobStore, metrics: Metrics, step_delay: float = 0.03) -> None:
    job = store.get(job_id)
    store.set_status(job_id, "running", "started", f"attempt={job.attempt}")

    for step in STEPS:
        store.set_status(job_id, "running", "step_started", step)
        time.sleep(step_delay)
        job = store.get(job_id)
        if job.fail_step == step:
            store.set_status(job_id, "failed", "step_failed", step)
            metrics.inc("jobs_failed")
            return
        store.set_status(job_id, "running", "step_completed", step)

    store.set_status(job_id, "succeeded", "completed", "workflow finished")
    metrics.inc("jobs_succeeded")
