import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .models import JobCreate, JobEvent, JobRecord


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, db_path: str = "control_plane.db") -> None:
        self.db_path = str(Path(db_path))
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    workflow TEXT NOT NULL,
                    sample_id TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    fail_step TEXT,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    event TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
                """
            )

    def create(self, job_id: str, payload: JobCreate, idempotency_key: Optional[str]) -> JobRecord:
        now = utcnow()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO jobs
                (id, workflow, sample_id, parameters, fail_step, status, attempt, created_at, updated_at, idempotency_key)
                VALUES (?, ?, ?, ?, ?, 'queued', 1, ?, ?, ?)
                """,
                (
                    job_id,
                    payload.workflow,
                    payload.sample_id,
                    json.dumps(payload.parameters, sort_keys=True),
                    payload.fail_step,
                    now,
                    now,
                    idempotency_key,
                ),
            )
            conn.execute(
                "INSERT INTO events (job_id, ts, event, detail) VALUES (?, ?, ?, ?)",
                (job_id, now, "submitted", f"workflow={payload.workflow}"),
            )
        return self.get(job_id)

    def get_by_idempotency_key(self, key: str) -> Optional[JobRecord]:
        with self._conn() as conn:
            row = conn.execute("SELECT id FROM jobs WHERE idempotency_key = ?", (key,)).fetchone()
        return self.get(row["id"]) if row else None

    def get(self, job_id: str) -> JobRecord:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            event_rows = conn.execute(
                "SELECT ts, event, detail FROM events WHERE job_id = ? ORDER BY id", (job_id,)
            ).fetchall()
        return JobRecord(
            id=row["id"],
            workflow=row["workflow"],
            sample_id=row["sample_id"],
            parameters=json.loads(row["parameters"]),
            fail_step=row["fail_step"],
            status=row["status"],
            attempt=row["attempt"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            events=[JobEvent(**dict(e)) for e in event_rows],
        )

    def list(self, limit: int = 50) -> list[JobRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.get(r["id"]) for r in rows]

    def set_status(self, job_id: str, status: str, event: str, detail: str) -> None:
        now = utcnow()
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, job_id),
            )
            conn.execute(
                "INSERT INTO events (job_id, ts, event, detail) VALUES (?, ?, ?, ?)",
                (job_id, now, event, detail),
            )

    def prepare_retry(self, job_id: str) -> JobRecord:
        current = self.get(job_id)
        if current.status != "failed":
            raise ValueError("only failed jobs can be retried")
        now = utcnow()
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status='queued', attempt=attempt+1, fail_step=NULL, updated_at=? WHERE id=?",
                (now, job_id),
            )
            conn.execute(
                "INSERT INTO events (job_id, ts, event, detail) VALUES (?, ?, 'retry_requested', ?)",
                (job_id, now, f"attempt={current.attempt + 1}"),
            )
        return self.get(job_id)
