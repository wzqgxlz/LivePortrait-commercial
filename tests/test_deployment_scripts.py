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
    assert "scripts/cleanup_api_jobs.py --older-than-days 7" in doc
    assert "python scripts/download_humans_assets.py" in doc
