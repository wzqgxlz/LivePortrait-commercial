# coding: utf-8

import hashlib
import json
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
TERMINAL_STATUSES = (SUCCEEDED, FAILED)
DEFAULT_USAGE_POLICY_VERSION = "human-image-authorization-v1"
DEFAULT_AUTHORIZATION_STATUS = "self_confirmed"
API_KEY_STATUS_ACTIVE = "active"
API_KEY_STATUS_REVOKED = "revoked"


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
    output_sha256: Optional[str]
    consent_confirmed: bool
    usage_policy_version: str
    authorization_basis: Optional[str]
    authorization_reference: Optional[str]
    authorization_reviewer: Optional[str]
    authorization_status: str
    owner_id: Optional[str]
    created_by_key_id: Optional[str]
    idempotency_key: Optional[str]
    attempt_count: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AuditEvent:
    event_id: int
    job_id: str
    event_type: str
    metadata: dict
    created_at: str


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str
    owner_id: str
    role: str
    label: Optional[str]
    key_prefix: str
    status: str
    created_at: str
    revoked_at: Optional[str]


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
        consent_confirmed: bool = False,
        usage_policy_version: str = DEFAULT_USAGE_POLICY_VERSION,
        authorization_basis: str | None = None,
        authorization_reference: str | None = None,
        authorization_reviewer: str | None = None,
        authorization_status: str = DEFAULT_AUTHORIZATION_STATUS,
        owner_id: str | None = None,
        created_by_key_id: str | None = None,
        idempotency_key: str | None = None,
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
                    source_sha256, driving_sha256, output_sha256, consent_confirmed,
                    usage_policy_version, authorization_basis, authorization_reference,
                    authorization_reviewer, authorization_status, owner_id,
                    created_by_key_id, idempotency_key, attempt_count, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    None,
                    1 if consent_confirmed else 0,
                    usage_policy_version,
                    authorization_basis,
                    authorization_reference,
                    authorization_reviewer,
                    authorization_status,
                    owner_id,
                    created_by_key_id,
                    idempotency_key,
                    0,
                    now,
                    now,
                ),
            )
            self._insert_audit_event(
                conn,
                job_id,
                "created",
                {
                    "source_filename": source_filename,
                    "driving_filename": driving_filename,
                    "source_sha256": source_sha256,
                    "driving_sha256": driving_sha256,
                    "consent_confirmed": consent_confirmed,
                    "usage_policy_version": usage_policy_version,
                    "authorization_basis": authorization_basis,
                    "authorization_reference": authorization_reference,
                    "authorization_reviewer": authorization_reviewer,
                    "authorization_status": authorization_status,
                    "owner_id": owner_id,
                    "created_by_key_id": created_by_key_id,
                    "idempotency_key": idempotency_key,
                },
                now,
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def get_job_by_idempotency_key(self, owner_id: str, idempotency_key: str) -> Optional[JobRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE owner_id = ? AND idempotency_key = ?",
                (owner_id, idempotency_key),
            ).fetchone()
        return _row_to_job(row) if row else None

    def list_jobs(self) -> list[JobRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at ASC").fetchall()
        return [_row_to_job(row) for row in rows]

    def list_recent_jobs(
        self,
        limit: int = 20,
        status: str | None = None,
        authorization_reference: str | None = None,
        authorization_status: str | None = None,
        owner_id: str | None = None,
    ) -> list[JobRecord]:
        safe_limit = max(1, min(limit, 100))
        clauses = []
        values = []
        if status is not None:
            clauses.append("status = ?")
            values.append(status)
        if authorization_reference is not None:
            clauses.append("authorization_reference = ?")
            values.append(authorization_reference)
        if authorization_status is not None:
            clauses.append("authorization_status = ?")
            values.append(authorization_status)
        if owner_id is not None:
            clauses.append("owner_id = ?")
            values.append(owner_id)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs {where_clause} ORDER BY created_at DESC LIMIT ?",
                (*values, safe_limit),
            ).fetchall()
        return [_row_to_job(row) for row in rows]

    def count_active_jobs(self, owner_id: str | None = None) -> int:
        where_clause = "WHERE status IN (?, ?)"
        values: list[str] = [PENDING, RUNNING]
        if owner_id is not None:
            where_clause += " AND owner_id = ?"
            values.append(owner_id)
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS total FROM jobs {where_clause}",
                values,
            ).fetchone()
        return int(row["total"])

    def create_api_key(
        self,
        owner_id: str,
        role: str,
        secret: str,
        label: str | None = None,
        key_id: str | None = None,
    ) -> ApiKeyRecord:
        now = _now()
        key_id = key_id or uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_keys (
                    key_id, owner_id, role, label, key_digest, key_prefix, status,
                    created_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key_id,
                    owner_id,
                    role,
                    label,
                    hash_api_key(secret),
                    secret[:12],
                    API_KEY_STATUS_ACTIVE,
                    now,
                    None,
                ),
            )
        return self.get_api_key(key_id)  # type: ignore[return-value]

    def get_api_key(self, key_id: str) -> Optional[ApiKeyRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM api_keys WHERE key_id = ?", (key_id,)).fetchone()
        return _row_to_api_key(row) if row else None

    def get_active_api_key(self, secret: str) -> Optional[ApiKeyRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE key_digest = ? AND status = ?",
                (hash_api_key(secret), API_KEY_STATUS_ACTIVE),
            ).fetchone()
        return _row_to_api_key(row) if row else None

    def list_api_keys(self) -> list[ApiKeyRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
        return [_row_to_api_key(row) for row in rows]

    def has_api_keys(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM api_keys").fetchone()
        return bool(row["total"])

    def revoke_api_key(self, key_id: str) -> Optional[ApiKeyRecord]:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE api_keys
                SET status = ?, revoked_at = ?
                WHERE key_id = ? AND status = ?
                """,
                (API_KEY_STATUS_REVOKED, now, key_id, API_KEY_STATUS_ACTIVE),
            )
        if cursor.rowcount != 1:
            return None
        return self.get_api_key(key_id)

    def list_terminal_jobs_before(self, cutoff: str) -> list[JobRecord]:
        placeholders = ", ".join("?" for _ in TERMINAL_STATUSES)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM jobs
                WHERE status IN ({placeholders}) AND updated_at < ?
                ORDER BY updated_at ASC
                """,
                (*TERMINAL_STATUSES, cutoff),
            ).fetchall()
        return [_row_to_job(row) for row in rows]

    def delete_job(self, job_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM job_audit_events WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))

    def mark_running(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job is None or job.status != PENDING:
            return
        self._update(
            job_id,
            "running",
            status=RUNNING,
            error_message=None,
            attempt_count=job.attempt_count + 1,
        )

    def mark_succeeded(self, job_id: str, result_path: Path) -> None:
        output_sha256 = sha256_file(result_path)
        self._update(
            job_id,
            "succeeded",
            status=SUCCEEDED,
            result_path=str(result_path),
            output_sha256=output_sha256,
            error_message=None,
        )

    def mark_failed(self, job_id: str, error_message: str) -> None:
        self._update(job_id, "failed", status=FAILED, error_message=error_message)

    def retry_failed_job(self, job_id: str) -> Optional[JobRecord]:
        job = self.get_job(job_id)
        if job is None or job.status != FAILED:
            return None
        self._update(
            job_id,
            "retried",
            status=PENDING,
            error_message=None,
            result_path=None,
            output_sha256=None,
        )
        return self.get_job(job_id)

    def recover_incomplete_jobs(self) -> dict[str, list[str]]:
        pending_jobs = self.list_jobs_with_status(PENDING)
        running_jobs = self.list_jobs_with_status(RUNNING)
        for job in running_jobs:
            self._update(
                job.job_id,
                "interrupted",
                status=FAILED,
                error_message="service restarted before task completion; retry the job to run it again",
            )
        for job in pending_jobs:
            self._update(
                job.job_id,
                "requeued_after_restart",
                status=PENDING,
                error_message=None,
            )
        return {
            "requeued_job_ids": [job.job_id for job in pending_jobs],
            "interrupted_job_ids": [job.job_id for job in running_jobs],
        }

    def list_jobs_with_status(self, status: str) -> list[JobRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC",
                (status,),
            ).fetchall()
        return [_row_to_job(row) for row in rows]

    def list_audit_events(self, job_id: str) -> list[AuditEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM job_audit_events WHERE job_id = ? ORDER BY event_id ASC",
                (job_id,),
            ).fetchall()
        return [_row_to_audit_event(row) for row in rows]

    def _update(self, job_id: str, event_type: str, **fields) -> None:
        now = _now()
        fields["updated_at"] = now
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [job_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE job_id = ?", values)
            self._insert_audit_event(conn, job_id, event_type, _event_metadata(fields), now)

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
                    output_sha256 TEXT,
                    consent_confirmed INTEGER NOT NULL DEFAULT 0,
                    usage_policy_version TEXT NOT NULL DEFAULT 'legacy',
                    authorization_basis TEXT,
                    authorization_reference TEXT,
                    authorization_reviewer TEXT,
                    authorization_status TEXT NOT NULL DEFAULT 'self_confirmed',
                    owner_id TEXT,
                    created_by_key_id TEXT,
                    idempotency_key TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                )
                """
            )
            _ensure_column(conn, "jobs", "output_sha256", "TEXT")
            _ensure_column(conn, "jobs", "consent_confirmed", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(conn, "jobs", "usage_policy_version", "TEXT NOT NULL DEFAULT 'legacy'")
            _ensure_column(conn, "jobs", "authorization_basis", "TEXT")
            _ensure_column(conn, "jobs", "authorization_reference", "TEXT")
            _ensure_column(conn, "jobs", "authorization_reviewer", "TEXT")
            _ensure_column(
                conn,
                "jobs",
                "authorization_status",
                "TEXT NOT NULL DEFAULT 'self_confirmed'",
            )
            _ensure_column(conn, "jobs", "owner_id", "TEXT")
            _ensure_column(conn, "jobs", "created_by_key_id", "TEXT")
            _ensure_column(conn, "jobs", "idempotency_key", "TEXT")
            _ensure_column(conn, "jobs", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
            conn.execute("CREATE INDEX IF NOT EXISTS jobs_owner_id_idx ON jobs(owner_id)")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS jobs_owner_idempotency_key_idx
                ON jobs(owner_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    label TEXT,
                    key_digest TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS api_keys_owner_id_idx ON api_keys(owner_id)")

    def _insert_audit_event(
        self,
        conn: sqlite3.Connection,
        job_id: str,
        event_type: str,
        metadata: dict,
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO job_audit_events (job_id, event_type, metadata_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, event_type, json.dumps(metadata, sort_keys=True), created_at),
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
        output_sha256=row["output_sha256"],
        consent_confirmed=bool(row["consent_confirmed"]),
        usage_policy_version=row["usage_policy_version"],
        authorization_basis=row["authorization_basis"],
        authorization_reference=row["authorization_reference"],
        authorization_reviewer=row["authorization_reviewer"],
        authorization_status=row["authorization_status"],
        owner_id=row["owner_id"],
        created_by_key_id=row["created_by_key_id"],
        idempotency_key=row["idempotency_key"],
        attempt_count=row["attempt_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_audit_event(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        event_id=row["event_id"],
        job_id=row["job_id"],
        event_type=row["event_type"],
        metadata=json.loads(row["metadata_json"]),
        created_at=row["created_at"],
    )


def _row_to_api_key(row: sqlite3.Row) -> ApiKeyRecord:
    return ApiKeyRecord(
        key_id=row["key_id"],
        owner_id=row["owner_id"],
        role=row["role"],
        label=row["label"],
        key_prefix=row["key_prefix"],
        status=row["status"],
        created_at=row["created_at"],
        revoked_at=row["revoked_at"],
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_metadata(fields: dict) -> dict:
    metadata = dict(fields)
    metadata.pop("updated_at", None)
    return metadata


def hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
