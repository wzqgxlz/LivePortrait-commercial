# coding: utf-8

from pathlib import Path

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
        assert script_response.status_code == 200
        assert "createJob" in script_response.text
        assert "loadJobs" in script_response.text
        assert "loadAuditExport" in script_response.text
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
        assert result_response.status_code == 401
        assert list_response.status_code == 401
        assert export_response.status_code == 401


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
