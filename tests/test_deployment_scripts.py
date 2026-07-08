# coding: utf-8

from pathlib import Path


def test_gpu_api_start_script_requires_key_and_uses_gpu_defaults():
    script = Path("scripts/start_gpu_api_server.sh").read_text(encoding="utf-8")

    assert "LIVEPORTRAIT_API_KEY must be set" in script
    assert "LIVEPORTRAIT_API_FORCE_CPU:=0" in script
    assert '"${LIVEPORTRAIT_API_PYTHON}" scripts/commercial_safety_scan.py' in script
    assert "uvicorn src.api.app:app" in script
    assert "--host \"${LIVEPORTRAIT_API_HOST}\"" in script
    assert "--port \"${LIVEPORTRAIT_API_PORT}\"" in script


def test_gpu_api_deployment_doc_mentions_frontend_and_cleanup():
    doc = Path("docs/gpu-api-deployment.md").read_text(encoding="utf-8")

    assert "http://<server-ip>:8000/" in doc
    assert "LIVEPORTRAIT_API_KEY" in doc
    assert "scripts/start_gpu_api_server.sh" in doc
    assert "scripts/check_api_deployment.py" in doc
    assert "scripts/cleanup_api_jobs.py --older-than-days 7" in doc
    assert "python scripts/download_humans_assets.py" in doc


def test_deployment_env_template_contains_safe_defaults():
    template = Path("deploy/liveportrait-api.env.example").read_text(encoding="utf-8")

    assert "LIVEPORTRAIT_API_KEY=replace-with-a-long-random-secret" in template
    assert "LIVEPORTRAIT_API_HOST=0.0.0.0" in template
    assert "LIVEPORTRAIT_API_FORCE_CPU=0" in template
    assert "LIVEPORTRAIT_API_DATA_DIR=tmp/api" in template


def test_systemd_template_points_to_start_script_and_env_file():
    service = Path("deploy/liveportrait-api.service").read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/liveportrait/liveportrait-api.env" in service
    assert "ExecStart=/opt/liveportrait/scripts/start_gpu_api_server.sh" in service
    assert "Restart=on-failure" in service
    assert "WorkingDirectory=/opt/liveportrait" in service


def test_deployment_check_script_verifies_health_frontend_and_auth():
    script = Path("scripts/check_api_deployment.py").read_text(encoding="utf-8")

    assert "/api/health" in script
    assert "/audit" in script
    assert "x-api-key" in script
    assert "Expected unauthorized response" in script
    assert "LivePortrait" in script


def test_api_job_smoke_script_submits_polls_and_downloads_result():
    script = Path("scripts/smoke_api_job.py").read_text(encoding="utf-8")

    assert "/api/jobs" in script
    assert "source" in script
    assert "driving" in script
    assert "consent_confirmed" in script
    assert "succeeded" in script
    assert "--output" in script
    assert "x-api-key" in script
