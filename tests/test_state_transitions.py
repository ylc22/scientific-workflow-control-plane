import pytest

from app.models import JobCreate
from app.store import JobStore


def test_terminal_job_cannot_return_to_running(tmp_path):
    store = JobStore(str(tmp_path / "db.sqlite"))
    job = store.create("job-terminal", JobCreate(workflow="rna", sample_id="s1"), None)

    store.set_status(job.id, "running", "started", "attempt=1")
    store.set_status(job.id, "succeeded", "completed", "workflow finished")

    with pytest.raises(ValueError, match="succeeded -> running"):
        store.set_status(job.id, "running", "started", "attempt=2")


def test_queued_job_cannot_skip_directly_to_succeeded(tmp_path):
    store = JobStore(str(tmp_path / "db.sqlite"))
    job = store.create("job-queued", JobCreate(workflow="rna", sample_id="s2"), None)

    with pytest.raises(ValueError, match="queued -> succeeded"):
        store.set_status(job.id, "succeeded", "completed", "invalid shortcut")


def test_running_to_running_is_allowed_for_step_events(tmp_path):
    store = JobStore(str(tmp_path / "db.sqlite"))
    job = store.create("job-running", JobCreate(workflow="rna", sample_id="s3"), None)

    store.set_status(job.id, "running", "started", "attempt=1")
    store.set_status(job.id, "running", "step_started", "ingest")

    assert store.get(job.id).status == "running"
