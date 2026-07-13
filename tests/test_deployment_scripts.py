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

    assert "docs/gpu-machine-quickstart.md" in doc
    assert "http://<server-ip>:8000/" in doc
    assert "LIVEPORTRAIT_API_KEY" in doc
    assert "scripts/start_gpu_api_server.sh" in doc
    assert "scripts/check_api_deployment.py" in doc
    assert "scripts/check_deployment_preflight.py" in doc
    assert "scripts/cleanup_api_jobs.py --older-than-days 7" in doc
    assert "cleanup-runs.jsonl" in doc
    assert "python scripts/download_humans_assets.py" in doc
    assert "docker compose -f deploy/docker-compose.gpu.yml up -d --build" in doc
    assert "deploy/Dockerfile.api" in doc
    assert "deploy/nginx-liveportrait-api.conf" in doc
    assert "deploy/Caddyfile.example" in doc
    assert "https://liveportrait.example.com/" in doc
    assert "operations audit export endpoint" in doc
    assert "CUDA" in doc
    assert "PyTorch" in doc


def test_gpu_machine_quickstart_covers_clone_to_browser_validation():
    doc = Path("docs/gpu-machine-quickstart.md").read_text(encoding="utf-8")
    acceptance = Path("docs/deployment-acceptance-checklist.md").read_text(encoding="utf-8")
    deliverables = Path("PROJECT_DELIVERABLES.md").read_text(encoding="utf-8")

    assert "nvidia-smi" in doc
    assert "git clone https://github.com/wzqgxlz/LivePortrait-commercial.git" in doc
    assert "git checkout codex/commercial-mediapipe-cropper" in doc
    assert "python3 -m venv .venv" in doc
    assert "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128" in doc
    assert "torch.cuda.is_available()" in doc
    assert "apt install -y ffmpeg libgles2 libegl1 libgl1 libglib2.0-0" in doc
    assert "python scripts/download_humans_assets.py" in doc
    assert "HF_ENDPOINT=https://hf-mirror.com" in doc
    assert "LIVEPORTRAIT_API_KEY" in doc
    assert "LIVEPORTRAIT_API_FORCE_CPU=0" in doc
    assert "python scripts/check_deployment_preflight.py" in doc
    assert "bash scripts/start_gpu_api_server.sh" in doc
    assert "python scripts/check_api_deployment.py" in doc
    assert "python scripts/smoke_api_job.py" in doc
    assert "http://<server-ip>:8000/" in doc
    assert "docs/deployment-acceptance-checklist.md" in doc
    assert "deploy/liveportrait-api.service" in doc
    assert "deploy/docker-compose.gpu.yml" in doc
    assert "deploy/nginx-liveportrait-api.conf" in doc
    assert "deploy/Caddyfile.example" in doc
    assert "CUDA out-of-memory" in doc
    assert "libGLESv2.so.2" in doc
    assert "ffprobe" in doc
    assert "docs/gpu-machine-quickstart.md" in acceptance
    assert "docs/gpu-machine-quickstart.md" in deliverables


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
    assert "ffmpeg" in dockerfile
    assert "libgles2" in dockerfile
    assert "libegl1" in dockerfile
    assert "libgl1" in dockerfile
    assert "libglib2.0-0" in dockerfile
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
    assert "/api/admin/audit-events/export" in script
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


def test_local_product_workflow_script_checks_non_gpu_product_shell():
    script = Path("scripts/check_local_product_workflow.py").read_text(encoding="utf-8")

    assert "create_app" in script
    assert "enqueue_jobs=False" in script
    assert "run_startup_checks=False" in script
    assert "/api/admin/api-keys" in script
    assert "x-idempotency-key" in script
    assert "/api/jobs/{created_job['job_id']}/export" in script
    assert "/api/admin/audit-events/export" in script
    assert "api_key.created" in script
    assert "job.retried" in script
    assert "cleanup.dry_run" in script
    assert "raw_user_key_leaked" in script


def test_deployment_preflight_script_checks_environment_assets_and_safety():
    script = Path("scripts/check_deployment_preflight.py").read_text(encoding="utf-8")

    assert "REQUIRED_MODEL_FILES" in script
    assert "pretrained_weights" in script
    assert "blaze_face_short_range.tflite" in script
    assert "commercial.safety_scan" in script
    assert "commercial.blocked_paths" in script
    assert "LIVEPORTRAIT_API_KEY" in script
    assert "LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER" in script
    assert "REQUIRED_SYSTEM_COMMANDS" in script
    assert "ffmpeg" in script
    assert "ffprobe" in script
    assert "REQUIRED_SHARED_LIBRARIES" in script
    assert "libGLESv2.so.2" in script
    assert "libEGL.so.1" in script
    assert "libGL.so.1" in script
    assert "libglib-2.0.so.0" in script
    assert "system.commands" in script
    assert "system.shared_libraries" in script
    assert "REQUIRED_IMPORTS" in script
    assert "torch.cuda.is_available" in script
    assert "--skip-gpu" in script
    assert "--skip-imports" in script
    assert "--skip-system-deps" in script
    assert "--allow-missing-api-key" in script


def test_humans_asset_downloader_validates_files_and_mentions_hf_mirror():
    script = Path("scripts/download_humans_assets.py").read_text(encoding="utf-8")

    assert "REQUIRED_HUMANS_FILES" in script
    assert "landmark.onnx" in script
    assert "appearance_feature_extractor.pth" in script
    assert "stitching_retargeting_module.pth" in script
    assert "_assert_required_assets(repo_root)" in script
    assert "Required Humans mode assets are still missing after download" in script
    assert "HF_ENDPOINT=https://hf-mirror.com" in script


def test_local_product_workflow_acceptance_record_documents_result():
    doc = Path("docs/local-product-workflow-acceptance-2026-07-12.md").read_text(encoding="utf-8")
    mvp_doc = Path("docs/mvp-api-service.md").read_text(encoding="utf-8")
    deliverables = Path("PROJECT_DELIVERABLES.md").read_text(encoding="utf-8")

    assert "python scripts\\check_local_product_workflow.py" in doc
    assert "status" in doc
    assert "passed" in doc
    assert "raw_user_key_leaked" in doc
    assert "false" in doc
    assert "liveportrait-operational-audit-export-v1" in doc
    assert "GPU validation remains" in doc
    assert "separate acceptance stage" in doc
    assert "scripts\\check_local_product_workflow.py" in mvp_doc
    assert "scripts\\check_deployment_preflight.py" in mvp_doc
    assert "docs/local-product-workflow-acceptance-2026-07-12.md" in mvp_doc
    assert "scripts/check_local_product_workflow.py" in deliverables
    assert "docs/local-product-workflow-acceptance-2026-07-12.md" in deliverables


def test_cleanup_script_records_cleanup_runs():
    script = Path("scripts/cleanup_api_jobs.py").read_text(encoding="utf-8")
    cleanup = Path("src/api/cleanup.py").read_text(encoding="utf-8")

    assert "cleanup-runs.jsonl" in script
    assert "record=" in script
    assert "operational_audit_matched" in script
    assert "operational_audit_deleted" in script
    assert "count_operational_audit_events_before" in cleanup
    assert "delete_operational_audit_events_before" in cleanup


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
    assert "GET /api/admin/audit-events" in doc
    assert "Operations Audit" in doc
    assert "GET /api/admin/audit-events/export" in doc
    assert "operational audit event counts" in doc
    assert "python scripts/check_deployment_preflight.py" in doc


def test_deployment_acceptance_checklist_covers_evidence_and_failures():
    doc = Path("docs/deployment-acceptance-checklist.md").read_text(encoding="utf-8")

    assert "Acceptance Stages" in doc
    assert "Evidence To Record" in doc
    assert "Pass/Fail Criteria" in doc
    assert "scripts/check_api_deployment.py" in doc
    assert "scripts/check_deployment_preflight.py" in doc
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
    assert "Operations Audit" in doc
    assert "GET /api/admin/audit-events/export" in doc
    assert "api_key.created" in doc
    assert "job.retried" in doc
    assert "operational_audit_matched_events" in doc
    assert "Deployment preflight passes" in doc
    assert "ffmpeg -version" in doc
    assert "ffprobe -version" in doc
    assert "libGLESv2.so.2" in doc
    assert "libEGL.so.1" in doc
    assert "libGL.so.1" in doc
    assert "libglib-2.0.so.0" in doc


def test_gpu_validation_record_documents_real_gpu_smoke_issues():
    doc = Path("docs/gpu-validation-record-2026-07-13.md").read_text(encoding="utf-8")
    deliverables = Path("PROJECT_DELIVERABLES.md").read_text(encoding="utf-8")

    assert "20c938b docs: add gpu machine quickstart" in doc
    assert "2.11.0+cu128 True" in doc
    assert "FFmpeg is not installed" in doc
    assert "libGLESv2.so.2" in doc
    assert "HF_ENDPOINT=https://hf-mirror.com" in doc
    assert "Status: succeeded" in doc
    assert "tmp/api-smoke-result.jpg" in doc
    assert "docs/gpu-validation-record-2026-07-13.md" in deliverables


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
