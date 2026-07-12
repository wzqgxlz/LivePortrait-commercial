# coding: utf-8

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Queue

from fastapi.testclient import TestClient


def test_frontend_page_and_assets_are_served(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        page_response = client.get("/")
        script_response = client.get("/static/app.js")
        style_response = client.get("/static/styles.css")

        assert page_response.status_code == 200
        assert "LivePortrait" in page_response.text
        assert 'id="source"' in page_response.text
        assert 'id="driving"' in page_response.text
        assert 'id="consent_confirmed"' in page_response.text
        assert 'id="jobs-list"' in page_response.text
        assert 'id="download-audit"' in page_response.text
        assert 'id="upload-limits"' in page_response.text
        assert 'id="form-errors"' in page_response.text
        assert 'id="source-summary"' in page_response.text
        assert 'id="driving-summary"' in page_response.text
        assert 'id="job-summary"' in page_response.text
        assert 'id="job-summary-content"' in page_response.text
        assert 'id="retry-job"' in page_response.text
        assert 'id="clear-result"' in page_response.text
        assert 'id="auth-hint"' in page_response.text
        assert 'id="empty-state"' in page_response.text
        assert 'id="completion-panel"' in page_response.text
        assert 'id="job-status-filter"' in page_response.text
        assert 'id="authorization-reference-filter"' in page_response.text
        assert 'id="authorization-status-filter"' in page_response.text
        assert 'id="owner-filter-field"' in page_response.text
        assert 'id="owner-id-filter"' in page_response.text
        assert 'id="export-authorization-record"' in page_response.text
        assert 'id="access-panel"' in page_response.text
        assert 'id="access-identity"' in page_response.text
        assert 'id="api-key-form"' in page_response.text
        assert 'id="new-key-owner"' in page_response.text
        assert 'id="new-key-label"' in page_response.text
        assert 'id="new-key-role"' in page_response.text
        assert 'id="new-api-key-result"' in page_response.text
        assert 'id="api-keys-list"' in page_response.text
        assert 'id="refresh-api-keys"' in page_response.text
        assert 'id="cleanup-runs-list"' in page_response.text
        assert 'id="refresh-cleanup-runs"' in page_response.text
        assert 'id="cleanup-older-than-days"' in page_response.text
        assert 'id="cleanup-dry-run"' in page_response.text
        assert 'id="cleanup-delete"' in page_response.text
        assert 'id="cleanup-panel"' in page_response.text
        assert 'id="authorization-basis"' in page_response.text
        assert 'id="authorization-reference"' in page_response.text
        assert 'id="authorization-reviewer"' in page_response.text
        assert 'id="authorization-status"' in page_response.text
        assert script_response.status_code == 200
        assert "createJob" in script_response.text
        assert "validateJobForm" in script_response.text
        assert "validateSelectedFile" in script_response.text
        assert "renderFileSummary" in script_response.text
        assert "renderJobSummary" in script_response.text
        assert "authorization_basis" in script_response.text
        assert "authorization_reference" in script_response.text
        assert "clearCurrentJob" in script_response.text
        assert "renderEmptyState" in script_response.text
        assert "renderCompletion" in script_response.text
        assert "updateAuthHint" in script_response.text
        assert "shortHash" in script_response.text
        assert "loadJobs" in script_response.text
        assert "jobStatusFilter" in script_response.text
        assert "authorizationReferenceFilter" in script_response.text
        assert "ownerIdFilter" in script_response.text
        assert "exportAuthorizationRecord" in script_response.text
        assert "loadApiKeys" in script_response.text
        assert "createManagedApiKey" in script_response.text
        assert "renderNewApiKey" in script_response.text
        assert "renderApiKeys" in script_response.text
        assert "revokeApiKey" in script_response.text
        assert "copyText" in script_response.text
        assert "/api/admin/api-keys" in script_response.text
        assert "owner_id" in script_response.text
        assert "loadCleanupRuns" in script_response.text
        assert "renderCleanupRuns" in script_response.text
        assert "runCleanup" in script_response.text
        assert "loadAccessProfile" in script_response.text
        assert "sessionStorage" in script_response.text
        assert "createIdempotencyKey" in script_response.text
        assert "retryCurrentJob" in script_response.text
        assert "status=" in script_response.text
        assert "authorization_reference=" in script_response.text
        assert "loadAuditExport" in script_response.text
        assert "status-chip" in script_response.text
        assert "formatBytes" in script_response.text
        assert ".form-errors" in style_response.text
        assert ".file-summary" in style_response.text
        assert ".job-summary" in style_response.text
        assert ".summary-grid" in style_response.text
        assert ".auth-hint" in style_response.text
        assert ".empty-state" in style_response.text
        assert ".completion-panel" in style_response.text
        assert ".status-chip" in style_response.text
        assert ".cleanup-runs-list" in style_response.text
        assert ".access-form" in style_response.text
        assert ".api-keys-list" in style_response.text
        assert ".new-key-result" in style_response.text
        assert style_response.status_code == 200


def test_create_job_saves_uploads_and_returns_pending_status(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.jpg", b"source-bytes", "image/jpeg"),
                "driving": ("driving.jpg", b"driving-bytes", "image/jpeg"),
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["status"] == "pending"
        assert payload["consent_confirmed"] is True
        assert payload["usage_policy_version"]
        assert payload["job_id"]
        assert (tmp_path / "api-data" / "jobs" / payload["job_id"] / "uploads" / "source.jpg").exists()

        status_response = client.get(f"/api/jobs/{payload['job_id']}")
        assert status_response.status_code == 200
        assert status_response.json()["source_filename"] == "source.jpg"
        assert status_response.json()["consent_confirmed"] is True


def test_create_job_idempotency_key_returns_the_original_job_without_duplication(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )
    headers = {"x-idempotency-key": "client-request-001"}

    with TestClient(app) as client:
        first = client.post(
            "/api/jobs",
            headers=headers,
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.jpg", b"source", "image/jpeg"),
                "driving": ("driving.jpg", b"driving", "image/jpeg"),
            },
        )
        repeated = client.post(
            "/api/jobs",
            headers=headers,
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.jpg", b"source", "image/jpeg"),
                "driving": ("driving.jpg", b"driving", "image/jpeg"),
            },
        )

        assert first.status_code == 201
        assert repeated.status_code == 200
        assert repeated.json()["job_id"] == first.json()["job_id"]
        assert repeated.json()["idempotency_key"] == "client-request-001"
        assert len(client.get("/api/jobs").json()["jobs"]) == 1


def test_failed_job_retry_preserves_job_identity_and_enforces_retry_limit(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(
            repo_root=tmp_path,
            data_dir=tmp_path / "api-data",
            max_active_jobs=10,
            max_active_jobs_per_owner=10,
            max_retries_per_job=1,
        ),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.jpg", b"source", "image/jpeg"),
                "driving": ("driving.jpg", b"driving", "image/jpeg"),
            },
        )
        job_id = created.json()["job_id"]
        store = app.state.job_store
        store.mark_running(job_id)
        store.mark_failed(job_id, "first attempt failed")

        retried = client.post(f"/api/jobs/{job_id}/retry")
        assert retried.status_code == 202
        assert retried.json()["job_id"] == job_id
        assert retried.json()["status"] == "pending"
        assert retried.json()["attempt_count"] == 1

        store.mark_running(job_id)
        store.mark_failed(job_id, "second attempt failed")
        retry_limit = client.post(f"/api/jobs/{job_id}/retry")
        audit = client.get(f"/api/jobs/{job_id}/audit")
        assert retry_limit.status_code == 409
        assert "retry limit" in retry_limit.json()["detail"]
        assert [event["event_type"] for event in audit.json()["events"]] == [
            "created",
            "running",
            "failed",
            "retried",
            "running",
            "failed",
        ]


def test_worker_exception_marks_the_job_failed_without_stopping_queue_processing(tmp_path):
    from src.api.app import _worker_loop
    from src.api.storage import FAILED, JobStore

    class ExplodingRunner:
        def run_job(self, store, job_id):
            raise RuntimeError("runner exploded")

    store = JobStore(tmp_path / "jobs.sqlite3")
    source_path = tmp_path / "source.jpg"
    driving_path = tmp_path / "driving.jpg"
    source_path.write_bytes(b"source")
    driving_path.write_bytes(b"driving")
    job = store.create_job(
        source_filename=source_path.name,
        driving_filename=driving_path.name,
        source_path=source_path,
        driving_path=driving_path,
        output_dir=tmp_path / "outputs",
        consent_confirmed=True,
    )
    queue: Queue[str] = Queue()
    worker = threading.Thread(target=_worker_loop, args=(queue, store, ExplodingRunner()), daemon=True)
    worker.start()
    queue.put(job.job_id)
    queue.join()

    failed_job = store.get_job(job.job_id)
    assert failed_job.status == FAILED
    assert "runner exploded" in failed_job.error_message


def test_create_job_records_authorization_metadata_in_payload_audit_and_export(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/jobs",
            data={
                "consent_confirmed": "true",
                "authorization_basis": "customer_contract",
                "authorization_reference": "CRM-2026-0001",
                "authorization_reviewer": "ops-reviewer",
                "authorization_status": "approved",
            },
            files={
                "source": ("source.jpg", b"source-bytes", "image/jpeg"),
                "driving": ("driving.jpg", b"driving-bytes", "image/jpeg"),
            },
        )

        assert create_response.status_code == 201
        job_id = create_response.json()["job_id"]
        assert create_response.json()["authorization_basis"] == "customer_contract"
        assert create_response.json()["authorization_reference"] == "CRM-2026-0001"
        assert create_response.json()["authorization_reviewer"] == "ops-reviewer"
        assert create_response.json()["authorization_status"] == "approved"

        audit_response = client.get(f"/api/jobs/{job_id}/audit")
        export_response = client.get(f"/api/jobs/{job_id}/export")

        assert audit_response.status_code == 200
        created_metadata = audit_response.json()["events"][0]["metadata"]
        assert created_metadata["authorization_basis"] == "customer_contract"
        assert created_metadata["authorization_reference"] == "CRM-2026-0001"
        assert created_metadata["authorization_reviewer"] == "ops-reviewer"
        assert created_metadata["authorization_status"] == "approved"
        assert export_response.status_code == 200
        assert export_response.json()["job"]["authorization_reference"] == "CRM-2026-0001"


def test_create_job_rejects_invalid_authorization_status(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            data={
                "consent_confirmed": "true",
                "authorization_status": "rejected",
            },
            files={
                "source": ("source.jpg", b"source-bytes", "image/jpeg"),
                "driving": ("driving.jpg", b"driving-bytes", "image/jpeg"),
            },
        )

        assert response.status_code == 400
        assert "authorization status" in response.json()["detail"]


def test_create_job_requires_usage_consent(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            files={
                "source": ("source.jpg", b"source-bytes", "image/jpeg"),
                "driving": ("driving.jpg", b"driving-bytes", "image/jpeg"),
            },
        )

        assert response.status_code == 400
        assert "authorization" in response.json()["detail"]


def test_list_jobs_returns_recent_jobs(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        first_response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("first-source.jpg", b"first-source", "image/jpeg"),
                "driving": ("first-driving.jpg", b"first-driving", "image/jpeg"),
            },
        )
        second_response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("second-source.jpg", b"second-source", "image/jpeg"),
                "driving": ("second-driving.jpg", b"second-driving", "image/jpeg"),
            },
        )

        response = client.get("/api/jobs?limit=1")

        assert response.status_code == 200
        assert response.json()["jobs"][0]["job_id"] == second_response.json()["job_id"]
        assert response.json()["jobs"][0]["source_filename"] == "second-source.jpg"
        assert first_response.json()["job_id"] != second_response.json()["job_id"]


def test_list_jobs_can_filter_by_status(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        pending_response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("pending-source.jpg", b"pending-source", "image/jpeg"),
                "driving": ("pending-driving.jpg", b"pending-driving", "image/jpeg"),
            },
        )
        failed_response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("failed-source.jpg", b"failed-source", "image/jpeg"),
                "driving": ("failed-driving.jpg", b"failed-driving", "image/jpeg"),
            },
        )
        app.state.job_store.mark_failed(failed_response.json()["job_id"], "operator test failure")

        failed_jobs = client.get("/api/jobs?status=failed")
        pending_jobs = client.get("/api/jobs?status=pending")
        invalid_status = client.get("/api/jobs?status=missing")

        assert failed_jobs.status_code == 200
        assert [job["job_id"] for job in failed_jobs.json()["jobs"]] == [failed_response.json()["job_id"]]
        assert pending_jobs.status_code == 200
        assert [job["job_id"] for job in pending_jobs.json()["jobs"]] == [pending_response.json()["job_id"]]
        assert invalid_status.status_code == 400


def test_list_jobs_can_filter_by_authorization_metadata(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        first_response = client.post(
            "/api/jobs",
            data={
                "consent_confirmed": "true",
                "authorization_reference": "CRM-2026-0001",
                "authorization_status": "approved",
            },
            files={
                "source": ("first-source.jpg", b"first-source", "image/jpeg"),
                "driving": ("first-driving.jpg", b"first-driving", "image/jpeg"),
            },
        )
        second_response = client.post(
            "/api/jobs",
            data={
                "consent_confirmed": "true",
                "authorization_reference": "CRM-2026-0002",
                "authorization_status": "needs_review",
            },
            files={
                "source": ("second-source.jpg", b"second-source", "image/jpeg"),
                "driving": ("second-driving.jpg", b"second-driving", "image/jpeg"),
            },
        )

        by_reference = client.get("/api/jobs?authorization_reference=CRM-2026-0001")
        by_status = client.get("/api/jobs?authorization_status=needs_review")
        invalid_status = client.get("/api/jobs?authorization_status=rejected")

        assert by_reference.status_code == 200
        assert [job["job_id"] for job in by_reference.json()["jobs"]] == [first_response.json()["job_id"]]
        assert by_status.status_code == 200
        assert [job["job_id"] for job in by_status.json()["jobs"]] == [second_response.json()["job_id"]]
        assert invalid_status.status_code == 400


def test_export_authorization_record_returns_matching_jobs_and_audits(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        matching_response = client.post(
            "/api/jobs",
            data={
                "consent_confirmed": "true",
                "authorization_reference": "CRM-2026-0001",
                "authorization_status": "approved",
            },
            files={
                "source": ("matching-source.jpg", b"matching-source", "image/jpeg"),
                "driving": ("matching-driving.jpg", b"matching-driving", "image/jpeg"),
            },
        )
        other_response = client.post(
            "/api/jobs",
            data={
                "consent_confirmed": "true",
                "authorization_reference": "CRM-2026-0002",
                "authorization_status": "approved",
            },
            files={
                "source": ("other-source.jpg", b"other-source", "image/jpeg"),
                "driving": ("other-driving.jpg", b"other-driving", "image/jpeg"),
            },
        )

        export_response = client.get(
            "/api/authorization-records/export?authorization_reference=CRM-2026-0001"
        )
        missing_response = client.get(
            "/api/authorization-records/export?authorization_reference=missing"
        )

        assert export_response.status_code == 200
        payload = export_response.json()
        assert payload["export_version"] == "liveportrait-authorization-export-v1"
        assert payload["authorization_reference"] == "CRM-2026-0001"
        assert [item["job"]["job_id"] for item in payload["jobs"]] == [matching_response.json()["job_id"]]
        assert payload["jobs"][0]["audit_events"][0]["event_type"] == "created"
        assert other_response.json()["job_id"] not in str(payload)
        assert "attachment" in export_response.headers["content-disposition"]
        assert missing_response.status_code == 404


def test_cleanup_runs_endpoint_returns_recent_records(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    data_dir = tmp_path / "api-data"
    record_path = data_dir / "cleanup-runs.jsonl"
    record_path.parent.mkdir(parents=True)
    record_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
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
                ),
                json.dumps(
                    {
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
                ),
            ]
        ),
        encoding="utf-8",
    )
    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=data_dir),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.get("/api/cleanup-runs?limit=1")

    assert response.status_code == 200
    assert response.json()["cleanup_record_path"] == str(record_path)
    assert len(response.json()["records"]) == 1
    assert response.json()["records"][0]["deleted_job_ids"] == ["third"]


def test_create_cleanup_run_dry_run_records_preview_without_deleting(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    data_dir = tmp_path / "api-data"
    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=data_dir),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.jpg", b"source", "image/jpeg"),
                "driving": ("driving.jpg", b"driving", "image/jpeg"),
            },
        )
        job_id = create_response.json()["job_id"]
        result_path = data_dir / "jobs" / job_id / "outputs" / "result.jpg"
        result_path.parent.mkdir(parents=True)
        result_path.write_bytes(b"result")
        app.state.job_store.mark_succeeded(job_id, result_path)
        _set_job_updated_at(app.state.job_store.db_path, job_id, datetime.now(timezone.utc) - timedelta(days=10))

        cleanup_response = client.post(
            "/api/cleanup-runs",
            json={"older_than_days": 7, "dry_run": True},
        )

        assert cleanup_response.status_code == 201
        payload = cleanup_response.json()
        assert payload["matched_jobs"] == 1
        assert payload["deleted_jobs"] == 0
        assert payload["dry_run"] is True
        assert app.state.job_store.get_job(job_id) is not None
        assert (data_dir / "jobs" / job_id).exists()
        records_response = client.get("/api/cleanup-runs?limit=1")
        assert records_response.json()["records"][0]["matched_job_ids"] == [job_id]


def test_create_cleanup_run_rejects_delete_without_confirmation(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/cleanup-runs",
            json={"older_than_days": 7, "dry_run": False},
        )

    assert response.status_code == 400
    assert "confirm" in response.json()["detail"]


def test_create_job_rejects_unsupported_source_type(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.gif", b"bad", "image/gif"),
                "driving": ("driving.jpg", b"ok", "image/jpeg"),
            },
        )

        assert response.status_code == 400
        assert "source" in response.json()["detail"]


def test_create_job_rejects_mismatched_source_content_type(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.jpg", b"not-an-image", "text/plain"),
                "driving": ("driving.jpg", b"ok", "image/jpeg"),
            },
        )

        assert response.status_code == 400
        assert "source" in response.json()["detail"]
        assert "content type" in response.json()["detail"]


def test_create_job_rejects_when_active_queue_is_full(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data", max_active_jobs=1),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        first_response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("first-source.jpg", b"first-source", "image/jpeg"),
                "driving": ("first-driving.jpg", b"first-driving", "image/jpeg"),
            },
        )
        second_response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("second-source.jpg", b"second-source", "image/jpeg"),
                "driving": ("second-driving.jpg", b"second-driving", "image/jpeg"),
            },
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 429
        assert "queue" in second_response.json()["detail"]


def test_api_key_protects_job_endpoints_when_configured(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data", api_key="secret-key"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/jobs",
            files={
                "source": ("source.jpg", b"source", "image/jpeg"),
                "driving": ("driving.jpg", b"driving", "image/jpeg"),
            },
        )
        assert create_response.status_code == 401

        wrong_key_response = client.get("/api/jobs/missing", headers={"x-api-key": "wrong"})
        assert wrong_key_response.status_code == 401

        authed_create_response = client.post(
            "/api/jobs",
            headers={"x-api-key": "secret-key"},
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.jpg", b"source", "image/jpeg"),
                "driving": ("driving.jpg", b"driving", "image/jpeg"),
            },
        )
        assert authed_create_response.status_code == 201
        job_id = authed_create_response.json()["job_id"]

        authed_status_response = client.get(f"/api/jobs/{job_id}", headers={"x-api-key": "secret-key"})
        assert authed_status_response.status_code == 200

        result_response = client.get(f"/api/jobs/{job_id}/result")
        list_response = client.get("/api/jobs")
        export_response = client.get(f"/api/jobs/{job_id}/export")
        authorization_export_response = client.get(
            "/api/authorization-records/export?authorization_reference=CRM-2026-0001"
        )
        cleanup_runs_response = client.get("/api/cleanup-runs")
        cleanup_create_response = client.post(
            "/api/cleanup-runs",
            json={"older_than_days": 7, "dry_run": True},
        )
        assert result_response.status_code == 401
        assert list_response.status_code == 401
        assert export_response.status_code == 401
        assert authorization_export_response.status_code == 401
        assert cleanup_runs_response.status_code == 401
        assert cleanup_create_response.status_code == 401


def test_managed_api_keys_isolate_jobs_limit_active_work_and_support_revocation(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(
            repo_root=tmp_path,
            data_dir=tmp_path / "api-data",
            api_key="bootstrap-secret",
            max_active_jobs=5,
            max_active_jobs_per_owner=1,
        ),
        enqueue_jobs=False,
        run_startup_checks=False,
    )
    admin_headers = {"x-api-key": "bootstrap-secret"}

    with TestClient(app) as client:
        reserved_owner_response = client.post(
            "/api/admin/api-keys",
            headers=admin_headers,
            json={"owner_id": "bootstrap-admin"},
        )
        assert reserved_owner_response.status_code == 400

        alice_key_response = client.post(
            "/api/admin/api-keys",
            headers=admin_headers,
            json={"owner_id": "alice", "label": "Alice pilot"},
        )
        bob_key_response = client.post(
            "/api/admin/api-keys",
            headers=admin_headers,
            json={"owner_id": "bob", "label": "Bob pilot"},
        )
        assert alice_key_response.status_code == 201
        assert bob_key_response.status_code == 201
        alice_key = alice_key_response.json()["api_key"]
        bob_key = bob_key_response.json()["api_key"]
        assert alice_key.startswith("lp_")
        assert alice_key_response.json()["key_prefix"] == alice_key[:12]

        alice_identity = client.get("/api/whoami", headers={"x-api-key": alice_key})
        admin_identity = client.get("/api/whoami", headers=admin_headers)
        assert alice_identity.json() == {"owner_id": "alice", "role": "user", "is_admin": False}
        assert admin_identity.json() == {
            "owner_id": "bootstrap-admin",
            "role": "admin",
            "is_admin": True,
        }

        listed_keys = client.get("/api/admin/api-keys", headers=admin_headers)
        assert listed_keys.status_code == 200
        assert alice_key not in listed_keys.text
        assert {item["owner_id"] for item in listed_keys.json()["api_keys"]} == {"alice", "bob"}
        with sqlite3.connect(app.state.job_store.db_path) as conn:
            digest = conn.execute(
                "SELECT key_digest FROM api_keys WHERE key_id = ?",
                (alice_key_response.json()["key_id"],),
            ).fetchone()[0]
        assert digest != alice_key

        alice_job = client.post(
            "/api/jobs",
            headers={"x-api-key": alice_key},
            data={"consent_confirmed": "true", "authorization_reference": "SHARED-REF"},
            files={
                "source": ("alice-source.jpg", b"alice-source", "image/jpeg"),
                "driving": ("alice-driving.jpg", b"alice-driving", "image/jpeg"),
            },
        )
        bob_job = client.post(
            "/api/jobs",
            headers={"x-api-key": bob_key},
            data={"consent_confirmed": "true", "authorization_reference": "SHARED-REF"},
            files={
                "source": ("bob-source.jpg", b"bob-source", "image/jpeg"),
                "driving": ("bob-driving.jpg", b"bob-driving", "image/jpeg"),
            },
        )
        assert alice_job.status_code == 201
        assert bob_job.status_code == 201
        assert alice_job.json()["owner_id"] == "alice"

        alice_second_job = client.post(
            "/api/jobs",
            headers={"x-api-key": alice_key},
            data={"consent_confirmed": "true"},
            files={
                "source": ("alice-source-2.jpg", b"alice-source-2", "image/jpeg"),
                "driving": ("alice-driving-2.jpg", b"alice-driving-2", "image/jpeg"),
            },
        )
        assert alice_second_job.status_code == 429
        assert "active job limit" in alice_second_job.json()["detail"]

        alice_jobs = client.get("/api/jobs", headers={"x-api-key": alice_key})
        alice_export = client.get(
            "/api/authorization-records/export?authorization_reference=SHARED-REF",
            headers={"x-api-key": alice_key},
        )
        alice_cannot_read_bob = client.get(
            f"/api/jobs/{bob_job.json()['job_id']}",
            headers={"x-api-key": alice_key},
        )
        alice_cannot_cleanup = client.get("/api/cleanup-runs", headers={"x-api-key": alice_key})
        alice_cannot_list_keys = client.get("/api/admin/api-keys", headers={"x-api-key": alice_key})
        assert [job["job_id"] for job in alice_jobs.json()["jobs"]] == [alice_job.json()["job_id"]]
        assert [item["job"]["job_id"] for item in alice_export.json()["jobs"]] == [alice_job.json()["job_id"]]
        assert alice_cannot_read_bob.status_code == 404
        assert alice_cannot_cleanup.status_code == 403
        assert alice_cannot_list_keys.status_code == 403

        admin_jobs = client.get("/api/jobs?owner_id=bob", headers=admin_headers)
        assert [job["job_id"] for job in admin_jobs.json()["jobs"]] == [bob_job.json()["job_id"]]

        revoke_response = client.post(
            f"/api/admin/api-keys/{alice_key_response.json()['key_id']}/revoke",
            headers=admin_headers,
        )
        assert revoke_response.status_code == 200
        assert revoke_response.json()["status"] == "revoked"
        assert client.get("/api/jobs", headers={"x-api-key": alice_key}).status_code == 401
        assert client.post(
            f"/api/admin/api-keys/{alice_key_response.json()['key_id']}/revoke",
            headers=admin_headers,
        ).status_code == 404


def test_result_endpoint_returns_completed_output(tmp_path):
    from src.api.app import create_app
    from src.api.config import ApiConfig

    app = create_app(
        ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data"),
        enqueue_jobs=False,
        run_startup_checks=False,
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/jobs",
            data={"consent_confirmed": "true"},
            files={
                "source": ("source.jpg", b"source", "image/jpeg"),
                "driving": ("driving.jpg", b"driving", "image/jpeg"),
            },
        )
        job_id = create_response.json()["job_id"]
        store = app.state.job_store
        result_path = tmp_path / "api-data" / "jobs" / job_id / "outputs" / "result.jpg"
        result_path.parent.mkdir(parents=True)
        result_path.write_bytes(b"result")
        store.mark_succeeded(job_id, result_path)

        response = client.get(f"/api/jobs/{job_id}/result")
        status_response = client.get(f"/api/jobs/{job_id}")
        audit_response = client.get(f"/api/jobs/{job_id}/audit")
        export_response = client.get(f"/api/jobs/{job_id}/export")

        assert response.status_code == 200
        assert response.content == b"result"
        assert status_response.status_code == 200
        assert status_response.json()["output_sha256"]
        assert audit_response.status_code == 200
        assert [event["event_type"] for event in audit_response.json()["events"]] == ["created", "succeeded"]
        assert export_response.status_code == 200
        assert "attachment" in export_response.headers["content-disposition"]
        export_payload = export_response.json()
        assert export_payload["export_version"] == "liveportrait-audit-export-v1"
        assert export_payload["job"]["job_id"] == job_id
        assert export_payload["job"]["output_sha256"]
        assert [event["event_type"] for event in export_payload["audit_events"]] == ["created", "succeeded"]


def test_inference_runner_builds_humans_only_command(tmp_path):
    from src.api.config import ApiConfig
    from src.api.runner import InferenceRunner

    cfg = ApiConfig(repo_root=tmp_path, data_dir=tmp_path / "api-data", force_cpu=True)
    runner = InferenceRunner(cfg)
    command = runner.build_command(
        source_path=Path("source.jpg"),
        driving_path=Path("driving.mp4"),
        output_dir=Path("outputs"),
    )

    assert command[:2] == [cfg.python_executable, "inference.py"]
    assert "inference_animals.py" not in command
    assert "--flag-force-cpu" in command
    assert "--no-flag-use-half-precision" in command


def _set_job_updated_at(db_path: Path, job_id: str, value: datetime) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE jobs SET updated_at = ? WHERE job_id = ?", (value.isoformat(), job_id))
