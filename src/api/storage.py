# coding: utf-8

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    status: str
    source_filename: str
    driving_filename: str
    source_path: Path
    driving_path: Path
    output_dir: Path
    result_path: Optional[Path]
    error_message: Optional[str]
    source_sha256: str
    driving_sha256: str
    created_at: str
    updated_at: str


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create_job(
        self,
        source_filename: str,
        driving_filename: str,
        source_path: Path,
        driving_path: Path,
        output_dir: Path,
        job_id: str | None = None,
    ) -> JobRecord:
        now = _now()
        job_id = job_id or uuid.uuid4().hex
        source_sha256 = sha256_file(source_path)
        driving_sha256 = sha256_file(driving_path)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, status, source_filename, driving_filename, source_path,
                    driving_path, output_dir, result_path, error_message,
                    source_sha256, driving_sha256, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    PENDING,
                    source_filename,
                    driving_filename,
                    str(source_path),
                    str(driving_path),
                    str(output_dir),
                    None,
                    None,
                    source_sha256,
                    driving_sha256,
                    now,
                    now,
                ),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def mark_running(self, job_id: str) -> None:
        self._update(job_id, status=RUNNING, error_message=None)

    def mark_succeeded(self, job_id: str, result_path: Path) -> None:
        self._update(job_id, status=SUCCEEDED, result_path=str(result_path), error_message=None)

    def mark_failed(self, job_id: str, error_message: str) -> None:
        self._update(job_id, status=FAILED, error_message=error_message)

    def _update(self, job_id: str, **fields) -> None:
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [job_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE job_id = ?", values)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    source_filename TEXT NOT NULL,
                    driving_filename TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    driving_path TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    result_path TEXT,
                    error_message TEXT,
                    source_sha256 TEXT NOT NULL,
                    driving_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_to_job(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        job_id=row["job_id"],
        status=row["status"],
        source_filename=row["source_filename"],
        driving_filename=row["driving_filename"],
        source_path=Path(row["source_path"]),
        driving_path=Path(row["driving_path"]),
        output_dir=Path(row["output_dir"]),
        result_path=Path(row["result_path"]) if row["result_path"] else None,
        error_message=row["error_message"],
        source_sha256=row["source_sha256"],
        driving_sha256=row["driving_sha256"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
