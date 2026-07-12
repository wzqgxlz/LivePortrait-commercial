# coding: utf-8

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def test_cleanup_finished_jobs_removes_only_old_terminal_jobs(tmp_path):
    from src.api.cleanup import cleanup_finished_jobs
    from src.api.storage import FAILED, RUNNING, SUCCEEDED, JobStore

    store = JobStore(tmp_path / "api-data" / "jobs.sqlite3")
    jobs_dir = tmp_path / "api-data" / "jobs"
    now = datetime(2026, 7, 8, tzinfo=timezone.utc)

    old_succeeded = _create_job(store, jobs_dir, "old-succeeded")
    old_failed = _create_job(store, jobs_dir, "old-failed")
    old_running = _create_job(store, jobs_dir, "old-running")
    fresh_succeeded = _create_job(store, jobs_dir, "fresh-succeeded")

    store.mark_succeeded(old_succeeded, jobs_dir / old_succeeded / "outputs" / "result.jpg")
    store.mark_failed(old_failed, "failed")
    store.mark_running(old_running)
    store.mark_succeeded(fresh_succeeded, jobs_dir / fresh_succeeded / "outputs" / "result.jpg")
    _set_updated_at(store.db_path, old_succeeded, now - timedelta(days=10))
    _set_updated_at(store.db_path, old_failed, now - timedelta(days=10))
    _set_updated_at(store.db_path, old_running, now - timedelta(days=10))
    _set_updated_at(store.db_path, fresh_succeeded, now - timedelta(days=1))

    result = cleanup_finished_jobs(store, jobs_dir, older_than_days=7, now=now)

    assert result.deleted_jobs == 2
    assert result.skipped_active_jobs == 1
    assert store.get_job(old_succeeded) is None
    assert store.get_job(old_failed) is None
    assert store.get_job(old_running).status == RUNNING
    assert store.get_job(fresh_succeeded).status == SUCCEEDED
    assert not (jobs_dir / old_succeeded).exists()
    assert not (jobs_dir / old_failed).exists()
    assert (jobs_dir / old_running).exists()
    assert (jobs_dir / fresh_succeeded).exists()


def test_cleanup_finished_jobs_dry_run_keeps_files_and_rows(tmp_path):
    from src.api.cleanup import cleanup_finished_jobs
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "api-data" / "jobs.sqlite3")
    jobs_dir = tmp_path / "api-data" / "jobs"
    now = datetime(2026, 7, 8, tzinfo=timezone.utc)
    job_id = _create_job(store, jobs_dir, "old-succeeded")
    store.mark_succeeded(job_id, jobs_dir / job_id / "outputs" / "result.jpg")
    audit_event = store.record_operational_audit_event(
        actor_owner_id="admin",
        actor_role="admin",
        action="api_key.created",
        target_type="api_key",
        target_id="key-001",
    )
    _set_updated_at(store.db_path, job_id, now - timedelta(days=10))
    _set_operational_audit_created_at(store.db_path, audit_event.event_id, now - timedelta(days=10))

    result = cleanup_finished_jobs(store, jobs_dir, older_than_days=7, now=now, dry_run=True)

    assert result.deleted_jobs == 0
    assert result.matched_jobs == 1
    assert result.operational_audit_matched_events == 1
    assert result.operational_audit_deleted_events == 0
    assert store.get_job(job_id) is not None
    assert store.list_operational_audit_events()[0].event_id == audit_event.event_id
    assert (jobs_dir / job_id).exists()


def test_cleanup_finished_jobs_deletes_old_operational_audit_events(tmp_path):
    from src.api.cleanup import cleanup_finished_jobs
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "api-data" / "jobs.sqlite3")
    jobs_dir = tmp_path / "api-data" / "jobs"
    now = datetime(2026, 7, 8, tzinfo=timezone.utc)
    old_event = store.record_operational_audit_event(
        actor_owner_id="admin",
        actor_role="admin",
        action="api_key.created",
        target_type="api_key",
        target_id="old-key",
    )
    fresh_event = store.record_operational_audit_event(
        actor_owner_id="admin",
        actor_role="admin",
        action="api_key.revoked",
        target_type="api_key",
        target_id="fresh-key",
    )
    _set_operational_audit_created_at(store.db_path, old_event.event_id, now - timedelta(days=10))
    _set_operational_audit_created_at(store.db_path, fresh_event.event_id, now - timedelta(days=1))

    result = cleanup_finished_jobs(store, jobs_dir, older_than_days=7, now=now)

    assert result.matched_jobs == 0
    assert result.operational_audit_matched_events == 1
    assert result.operational_audit_deleted_events == 1
    assert [event.target_id for event in store.list_operational_audit_events()] == ["fresh-key"]


def test_cleanup_finished_jobs_writes_cleanup_record(tmp_path):
    from src.api.cleanup import cleanup_finished_jobs
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "api-data" / "jobs.sqlite3")
    jobs_dir = tmp_path / "api-data" / "jobs"
    record_path = tmp_path / "api-data" / "cleanup-runs.jsonl"
    now = datetime(2026, 7, 8, tzinfo=timezone.utc)
    job_id = _create_job(store, jobs_dir, "old-succeeded")
    store.mark_succeeded(job_id, jobs_dir / job_id / "outputs" / "result.jpg")
    _set_updated_at(store.db_path, job_id, now - timedelta(days=10))

    result = cleanup_finished_jobs(
        store,
        jobs_dir,
        older_than_days=7,
        now=now,
        cleanup_record_path=record_path,
    )

    payload = json.loads(record_path.read_text(encoding="utf-8").strip())
    assert result.cleanup_record_path == record_path
    assert payload["older_than_days"] == 7
    assert payload["dry_run"] is False
    assert payload["matched_job_ids"] == [job_id]
    assert payload["deleted_job_ids"] == [job_id]
    assert payload["deleted_jobs"] == 1
    assert payload["operational_audit_matched_events"] == 0
    assert payload["operational_audit_deleted_events"] == 0
    assert payload["removed_bytes"] > 0


def test_list_cleanup_records_returns_recent_valid_records(tmp_path):
    from src.api.cleanup import list_cleanup_records

    record_path = tmp_path / "api-data" / "cleanup-runs.jsonl"
    record_path.parent.mkdir(parents=True)
    first = {
        "created_at": "2026-07-08T01:00:00+00:00",
        "older_than_days": 7,
        "dry_run": True,
        "matched_jobs": 2,
        "deleted_jobs": 0,
        "skipped_active_jobs": 1,
        "removed_bytes": 512,
        "matched_job_ids": ["first", "second"],
        "deleted_job_ids": [],
    }
    second = {
        "created_at": "2026-07-09T01:00:00+00:00",
        "older_than_days": 14,
        "dry_run": False,
        "matched_jobs": 1,
        "deleted_jobs": 1,
        "skipped_active_jobs": 0,
        "removed_bytes": 1024,
        "matched_job_ids": ["third"],
        "deleted_job_ids": ["third"],
    }
    record_path.write_text(
        json.dumps(first) + "\nnot-json\n" + json.dumps(second) + "\n",
        encoding="utf-8",
    )

    records = list_cleanup_records(record_path, limit=1)

    assert records == [second]


def _create_job(store, jobs_dir: Path, job_id: str) -> str:
    job_dir = jobs_dir / job_id
    upload_dir = job_dir / "uploads"
    output_dir = job_dir / "outputs"
    upload_dir.mkdir(parents=True)
    output_dir.mkdir()
    source_path = upload_dir / "source.jpg"
    driving_path = upload_dir / "driving.jpg"
    source_path.write_bytes(f"{job_id}-source".encode("utf-8"))
    driving_path.write_bytes(f"{job_id}-driving".encode("utf-8"))
    (output_dir / "result.jpg").write_bytes(b"result")
    return store.create_job(
        source_filename="source.jpg",
        driving_filename="driving.jpg",
        source_path=source_path,
        driving_path=driving_path,
        output_dir=output_dir,
        job_id=job_id,
    ).job_id


def _set_updated_at(db_path: Path, job_id: str, value: datetime) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE jobs SET updated_at = ? WHERE job_id = ?", (value.isoformat(), job_id))


def _set_operational_audit_created_at(db_path: Path, event_id: int, value: datetime) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE operational_audit_events SET created_at = ? WHERE event_id = ?",
            (value.isoformat(), event_id),
        )
