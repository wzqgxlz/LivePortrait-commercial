# coding: utf-8

import sqlite3


def test_job_store_migrates_existing_database_with_consent_columns(tmp_path):
    from src.api.storage import JobStore

    db_path = tmp_path / "jobs.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE jobs (
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

    JobStore(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}

    assert "consent_confirmed" in columns
    assert "usage_policy_version" in columns


def test_job_store_records_audit_events_and_output_hash(tmp_path):
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "jobs.sqlite3")
    source_path = tmp_path / "source.jpg"
    driving_path = tmp_path / "driving.jpg"
    output_dir = tmp_path / "outputs"
    result_path = output_dir / "result.jpg"
    source_path.write_bytes(b"source")
    driving_path.write_bytes(b"driving")
    output_dir.mkdir()
    result_path.write_bytes(b"result")

    job = store.create_job(
        source_filename="source.jpg",
        driving_filename="driving.jpg",
        source_path=source_path,
        driving_path=driving_path,
        output_dir=output_dir,
        consent_confirmed=True,
    )
    store.mark_running(job.job_id)
    store.mark_succeeded(job.job_id, result_path)

    updated_job = store.get_job(job.job_id)
    events = store.list_audit_events(job.job_id)

    assert updated_job.output_sha256
    assert [event.event_type for event in events] == ["created", "running", "succeeded"]
    assert events[0].metadata["source_sha256"] == job.source_sha256
    assert events[0].metadata["consent_confirmed"] is True
    assert events[-1].metadata["output_sha256"] == updated_job.output_sha256


def test_job_store_records_failed_audit_event(tmp_path):
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "jobs.sqlite3")
    source_path = tmp_path / "source.jpg"
    driving_path = tmp_path / "driving.jpg"
    output_dir = tmp_path / "outputs"
    source_path.write_bytes(b"source")
    driving_path.write_bytes(b"driving")

    job = store.create_job(
        source_filename="source.jpg",
        driving_filename="driving.jpg",
        source_path=source_path,
        driving_path=driving_path,
        output_dir=output_dir,
        consent_confirmed=True,
    )
    store.mark_failed(job.job_id, "boom")

    events = store.list_audit_events(job.job_id)

    assert [event.event_type for event in events] == ["created", "failed"]
    assert events[-1].metadata["error_message"] == "boom"
