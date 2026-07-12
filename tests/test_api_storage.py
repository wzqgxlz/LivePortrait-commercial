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
    assert "idempotency_key" in columns
    assert "attempt_count" in columns

    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    assert "operational_audit_events" in tables


def test_job_store_records_operational_audit_events(tmp_path):
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "jobs.sqlite3")

    created = store.record_operational_audit_event(
        actor_owner_id="bootstrap-admin",
        actor_key_id=None,
        actor_role="admin",
        action="api_key.created",
        target_type="api_key",
        target_id="key-001",
        metadata={"owner_id": "customer-001", "key_prefix": "lp_abc"},
    )
    store.record_operational_audit_event(
        actor_owner_id="customer-001",
        actor_key_id="key-001",
        actor_role="user",
        action="job.retried",
        target_type="job",
        target_id="job-001",
        metadata={"attempt_count": 1},
    )

    all_events = store.list_operational_audit_events()
    key_events = store.list_operational_audit_events(action="api_key.created")
    actor_events = store.list_operational_audit_events(actor_owner_id="customer-001")

    assert created.event_id > 0
    assert [event.action for event in all_events] == ["job.retried", "api_key.created"]
    assert key_events[0].target_id == "key-001"
    assert key_events[0].metadata["owner_id"] == "customer-001"
    assert actor_events[0].action == "job.retried"


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


def test_job_store_filters_recent_jobs_by_authorization_metadata(tmp_path):
    from src.api.storage import JobStore

    store = JobStore(tmp_path / "jobs.sqlite3")
    matching_ids = []
    cases = [
        ("CRM-2026-0001", "approved"),
        ("CRM-2026-0002", "approved"),
        ("CRM-2026-0001", "needs_review"),
    ]
    for index, (reference, auth_status) in enumerate(cases):
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
            authorization_reference=reference,
            authorization_status=auth_status,
        )
        if reference == "CRM-2026-0001":
            matching_ids.append(job.job_id)

    by_reference = store.list_recent_jobs(
        limit=10,
        authorization_reference="CRM-2026-0001",
    )
    by_reference_and_status = store.list_recent_jobs(
        limit=10,
        authorization_reference="CRM-2026-0001",
        authorization_status="approved",
    )

    assert [job.job_id for job in by_reference] == list(reversed(matching_ids))
    assert [job.authorization_status for job in by_reference_and_status] == ["approved"]


def test_job_store_recovers_pending_jobs_and_marks_interrupted_jobs_failed(tmp_path):
    from src.api.storage import FAILED, PENDING, JobStore

    store = JobStore(tmp_path / "jobs.sqlite3")
    pending_source = tmp_path / "pending-source.jpg"
    pending_driving = tmp_path / "pending-driving.jpg"
    running_source = tmp_path / "running-source.jpg"
    running_driving = tmp_path / "running-driving.jpg"
    for path in (pending_source, pending_driving, running_source, running_driving):
        path.write_bytes(path.name.encode("utf-8"))

    pending_job = store.create_job(
        source_filename=pending_source.name,
        driving_filename=pending_driving.name,
        source_path=pending_source,
        driving_path=pending_driving,
        output_dir=tmp_path / "pending-output",
        consent_confirmed=True,
    )
    running_job = store.create_job(
        source_filename=running_source.name,
        driving_filename=running_driving.name,
        source_path=running_source,
        driving_path=running_driving,
        output_dir=tmp_path / "running-output",
        consent_confirmed=True,
    )
    store.mark_running(running_job.job_id)

    recovery = store.recover_incomplete_jobs()

    assert recovery == {
        "requeued_job_ids": [pending_job.job_id],
        "interrupted_job_ids": [running_job.job_id],
    }
    assert store.get_job(pending_job.job_id).status == PENDING
    interrupted = store.get_job(running_job.job_id)
    assert interrupted.status == FAILED
    assert "service restarted" in interrupted.error_message
    assert [event.event_type for event in store.list_audit_events(pending_job.job_id)] == [
        "created",
        "requeued_after_restart",
    ]
    assert [event.event_type for event in store.list_audit_events(running_job.job_id)] == [
        "created",
        "running",
        "interrupted",
    ]
