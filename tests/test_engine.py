from app.engine import run_job
from app.metrics import Metrics
from app.models import JobCreate
from app.store import JobStore


def test_engine_success(tmp_path):
    store = JobStore(str(tmp_path / "db.sqlite"))
    job = store.create("job-1", JobCreate(workflow="rna", sample_id="s1"), None)
    metrics = Metrics()
    run_job(job.id, store, metrics, step_delay=0)
    result = store.get(job.id)
    assert result.status == "succeeded"
    assert any(e.event == "completed" for e in result.events)
    assert metrics.snapshot()["jobs_succeeded"] == 1


def test_engine_failure_then_retry(tmp_path):
    store = JobStore(str(tmp_path / "db.sqlite"))
    job = store.create(
        "job-2",
        JobCreate(workflow="rna", sample_id="s2", fail_step="analyze"),
        None,
    )
    metrics = Metrics()
    run_job(job.id, store, metrics, step_delay=0)
    assert store.get(job.id).status == "failed"

    retry = store.prepare_retry(job.id)
    assert retry.attempt == 2
    run_job(job.id, store, metrics, step_delay=0)
    assert store.get(job.id).status == "succeeded"
