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
