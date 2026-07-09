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
    assert "authorization_basis" in columns
    assert "authorization_reference" in columns
    assert "authorization_reviewer" in columns
    assert "authorization_status" in columns


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


def test_job_store_records_authorization_metadata(tmp_path):
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "jobs.sqlite3")
    source_path = tmp_path / "source.jpg"
    driving_path = tmp_path / "driving.jpg"
    output_dir = tmp_path / "outputs"
    source_path.write_bytes(b"source")
    driving_path.write_bytes(b"driving")
    output_dir.mkdir()

    job = store.create_job(
        source_filename="source.jpg",
        driving_filename="driving.jpg",
        source_path=source_path,
        driving_path=driving_path,
        output_dir=output_dir,
        consent_confirmed=True,
        authorization_basis="customer_contract",
        authorization_reference="CRM-2026-0001",
        authorization_reviewer="ops-reviewer",
        authorization_status="approved",
    )
    events = store.list_audit_events(job.job_id)

    assert job.authorization_basis == "customer_contract"
    assert job.authorization_reference == "CRM-2026-0001"
    assert job.authorization_reviewer == "ops-reviewer"
    assert job.authorization_status == "approved"
    assert events[0].metadata["authorization_reference"] == "CRM-2026-0001"


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


def test_job_store_lists_recent_jobs_newest_first(tmp_path):
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "jobs.sqlite3")
    created_ids = []
    for index in range(3):
        source_path = tmp_path / f"source-{index}.jpg"
        driving_path = tmp_path / f"driving-{index}.jpg"
        source_path.write_bytes(f"source-{index}".encode("utf-8"))
        driving_path.write_bytes(f"driving-{index}".encode("utf-8"))
        job = store.create_job(
            source_filename=source_path.name,
            driving_filename=driving_path.name,
            source_path=source_path,
            driving_path=driving_path,
            output_dir=tmp_path / f"outputs-{index}",
            consent_confirmed=True,
        )
        created_ids.append(job.job_id)

    recent = store.list_recent_jobs(limit=2)

    assert [job.job_id for job in recent] == [created_ids[2], created_ids[1]]
