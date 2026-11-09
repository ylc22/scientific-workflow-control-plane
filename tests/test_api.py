from fastapi.testclient import TestClient

from app.main import create_app


def test_health(tmp_path):
    client = TestClient(create_app(str(tmp_path / "db.sqlite")))
    assert client.get("/health").json() == {"status": "ok"}


def test_submission_is_idempotent(tmp_path):
    client = TestClient(create_app(str(tmp_path / "db.sqlite")))
    payload = {"workflow": "rna-seq-qc", "sample_id": "S1", "parameters": {}}
    headers = {"Idempotency-Key": "same-request"}

    first = client.post("/jobs", json=payload, headers=headers)
    second = client.post("/jobs", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


def test_unknown_job_is_404(tmp_path):
    client = TestClient(create_app(str(tmp_path / "db.sqlite")))
    assert client.get("/jobs/missing").status_code == 404


def test_cancel_queued_job(tmp_path):
    app = create_app(str(tmp_path / "db.sqlite"))
    client = TestClient(app)
    payload = {"workflow": "rna-seq-qc", "sample_id": "S2", "parameters": {}}
    job = app.state.store.create("job-cancel", __import__("app.models", fromlist=["JobCreate"]).JobCreate(**payload), None)

    response = client.post(f"/jobs/{job.id}/cancel")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert any(event["event"] == "cancel_requested" for event in body["events"])


def test_cannot_cancel_completed_job(tmp_path):
    app = create_app(str(tmp_path / "db.sqlite"))
    client = TestClient(app)
    JobCreate = __import__("app.models", fromlist=["JobCreate"]).JobCreate
    job = app.state.store.create("job-done", JobCreate(workflow="rna", sample_id="S3"), None)
    app.state.store.set_status(job.id, "succeeded", "completed", "done")

    response = client.post(f"/jobs/{job.id}/cancel")

    assert response.status_code == 409
    assert response.json()["detail"] == "only queued or running jobs can be cancelled"
