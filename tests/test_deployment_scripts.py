# coding: utf-8

from pathlib import Path


def test_gpu_api_start_script_requires_key_and_uses_gpu_defaults():
    script = Path("scripts/start_gpu_api_server.sh").read_text(encoding="utf-8")

    assert "LIVEPORTRAIT_API_KEY must be set" in script
    assert "LIVEPORTRAIT_API_FORCE_CPU:=0" in script
    assert "LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER:=3" in script
    assert "LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB:=2" in script
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
    assert "cleanup-runs.jsonl" in doc
    assert "python scripts/download_humans_assets.py" in doc
    assert "docker compose -f deploy/docker-compose.gpu.yml up -d --build" in doc
    assert "deploy/Dockerfile.api" in doc
    assert "deploy/nginx-liveportrait-api.conf" in doc
    assert "deploy/Caddyfile.example" in doc
    assert "https://liveportrait.example.com/" in doc


def test_deployment_env_template_contains_safe_defaults():
    template = Path("deploy/liveportrait-api.env.example").read_text(encoding="utf-8")

    assert "LIVEPORTRAIT_API_KEY=replace-with-a-long-random-secret" in template
    assert "LIVEPORTRAIT_API_HOST=0.0.0.0" in template
    assert "LIVEPORTRAIT_API_FORCE_CPU=0" in template
    assert "LIVEPORTRAIT_API_DATA_DIR=tmp/api" in template
    assert "LIVEPORTRAIT_API_MAX_ACTIVE_JOBS=20" in template
    assert "LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER=3" in template
    assert "LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB=2" in template
    assert "LIVEPORTRAIT_API_MAX_UPLOAD_BYTES=209715200" in template


def test_systemd_template_points_to_start_script_and_env_file():
    service = Path("deploy/liveportrait-api.service").read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/liveportrait/liveportrait-api.env" in service
    assert "ExecStart=/opt/liveportrait/scripts/start_gpu_api_server.sh" in service
    assert "Restart=on-failure" in service
    assert "WorkingDirectory=/opt/liveportrait" in service


def test_docker_deployment_files_use_gpu_api_defaults_and_exclude_local_artifacts():
    dockerfile = Path("deploy/Dockerfile.api").read_text(encoding="utf-8")
    compose = Path("deploy/docker-compose.gpu.yml").read_text(encoding="utf-8")
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")

    assert "nvidia/cuda" in dockerfile
    assert "pip install torch torchvision torchaudio" in dockerfile
    assert "pip install -r requirements.txt" in dockerfile
    assert "LIVEPORTRAIT_API_FORCE_CPU=0" in dockerfile
    assert "LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER=3" in dockerfile
    assert "LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB=2" in dockerfile
    assert "scripts/start_gpu_api_server.sh" in dockerfile
    assert "LIVEPORTRAIT_API_KEY" in compose
    assert "LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER" in compose
    assert "LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB" in compose
    assert "deploy/Dockerfile.api" in compose
    assert "capabilities: [gpu]" in compose
    assert "8000:8000" in compose
    assert "../tmp/api:/app/tmp/api" in compose
    assert "../pretrained_weights:/app/pretrained_weights" in compose
    assert "pretrained_weights/" in dockerignore
    assert "tmp/" in dockerignore
    assert "output/" in dockerignore
    assert "LivePortrait_env/" in dockerignore


def test_reverse_proxy_templates_route_https_to_local_api_with_upload_limits():
    nginx = Path("deploy/nginx-liveportrait-api.conf").read_text(encoding="utf-8")
    caddy = Path("deploy/Caddyfile.example").read_text(encoding="utf-8")

    assert "liveportrait.example.com" in nginx
    assert "listen 80" in nginx
    assert "listen 443 ssl http2" in nginx
    assert "return 301 https://$host$request_uri" in nginx
    assert "proxy_pass http://127.0.0.1:8000" in nginx
    assert "client_max_body_size 220m" in nginx
    assert "proxy_read_timeout 3600s" in nginx
    assert "proxy_request_buffering off" in nginx
    assert "X-Forwarded-Proto https" in nginx

    assert "liveportrait.example.com" in caddy
    assert "reverse_proxy 127.0.0.1:8000" in caddy
    assert "max_size 220MB" in caddy
    assert "read_timeout 3600s" in caddy
    assert "X-Forwarded-Proto https" in caddy


def test_deployment_check_script_verifies_health_frontend_and_auth():
    script = Path("scripts/check_api_deployment.py").read_text(encoding="utf-8")

    assert "/api/health" in script
    assert "/api/whoami" in script
    assert "/api/jobs?limit=1" in script
    assert "/api/authorization-records/export" in script
    assert "/api/cleanup-runs?limit=1" in script
    assert "_post_json" in script
    assert "Cleanup create endpoint rejects requests without x-api-key" in script
    assert "/audit" in script
    assert "/export" in script
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


def test_cleanup_script_records_cleanup_runs():
    script = Path("scripts/cleanup_api_jobs.py").read_text(encoding="utf-8")

    assert "cleanup-runs.jsonl" in script
    assert "record=" in script


def test_production_operations_doc_covers_launch_and_support_workflows():
    doc = Path("docs/production-operations.md").read_text(encoding="utf-8")

    assert "Launch Checklist" in doc
    assert "Daily Operations" in doc
    assert "Support Export" in doc
    assert "cleanup-runs.jsonl" in doc
    assert "GET /api/jobs?status=failed" in doc
    assert "GET /api/jobs?authorization_reference=CRM-2026-0001" in doc
    assert "GET /api/authorization-records/export?authorization_reference=CRM-2026-0001" in doc
    assert "GET /api/cleanup-runs?limit=20" in doc
    assert "POST /api/cleanup-runs" in doc
    assert "GET /api/jobs/{job_id}/export" in doc
    assert "Incident Response" in doc
    assert "deploy/nginx-liveportrait-api.conf" in doc
    assert "deploy/Caddyfile.example" in doc
    assert "Reverse Proxy Or HTTPS Failure" in doc


def test_deployment_acceptance_checklist_covers_evidence_and_failures():
    doc = Path("docs/deployment-acceptance-checklist.md").read_text(encoding="utf-8")

    assert "Acceptance Stages" in doc
    assert "Evidence To Record" in doc
    assert "Pass/Fail Criteria" in doc
    assert "scripts/check_api_deployment.py" in doc
    assert "scripts/smoke_api_job.py" in doc
    assert "output_sha256" in doc
    assert "Rollback" in doc
    assert "Choose One Deployment Mode" in doc
    assert "docker-compose" in doc
    assert "systemd" in doc
    assert "deploy/docker-compose.gpu.yml" in doc
    assert "deploy/Dockerfile.api" in doc
    assert "docker compose -f deploy/docker-compose.gpu.yml ps" in doc
    assert "sudo systemctl stop liveportrait-api" in doc
    assert "HTTPS Reverse Proxy" in doc
    assert "deploy/nginx-liveportrait-api.conf" in doc
    assert "deploy/Caddyfile.example" in doc
    assert "https://liveportrait.example.com" in doc


def test_content_safety_authorization_workflow_covers_mvp_controls():
    doc = Path("docs/content-safety-authorization-workflow.md").read_text(encoding="utf-8")

    assert "Authorization Record" in doc
    assert "Content Review" in doc
    assert "Prohibited Uses" in doc
    assert "Manual Review" in doc
    assert "GET /api/jobs/{job_id}/export" in doc
    assert "GET /api/authorization-records/export?authorization_reference=<reference>" in doc
    assert "consent_confirmed" in doc
    assert "Retention" in doc
