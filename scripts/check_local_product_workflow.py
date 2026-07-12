# coding: utf-8

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.app import create_app
from src.api.config import ApiConfig


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a non-GPU local product workflow check for the LivePortrait API/frontend shell."
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Optional API data directory. Defaults to a temporary directory.",
    )
    parser.add_argument(
        "--admin-key",
        default="local-product-acceptance-admin-key",
        help="Bootstrap administrator API Key used inside the in-process check.",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep the temporary data directory after the check.",
    )
    args = parser.parse_args(argv)

    temp_dir = None
    if args.data_dir:
        data_dir = Path(args.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.mkdtemp(prefix="liveportrait-product-workflow-")
        data_dir = Path(temp_dir)

    try:
        summary = run_workflow(data_dir=data_dir, admin_key=args.admin_key)
        print(json.dumps(summary, indent=2, sort_keys=True))
    finally:
        if temp_dir and not args.keep_data:
            shutil.rmtree(temp_dir, ignore_errors=True)
    return 0


def run_workflow(data_dir: Path, admin_key: str) -> dict:
    app = create_app(
        ApiConfig(
            repo_root=REPO_ROOT,
            data_dir=data_dir,
            api_key=admin_key,
            force_cpu=True,
            max_active_jobs=10,
            max_active_jobs_per_owner=10,
        ),
        enqueue_jobs=False,
        run_startup_checks=False,
    )
    admin_headers = {"x-api-key": admin_key}

    with TestClient(app) as client:
        health = _expect(client.get("/api/health"), 200)
        page = client.get("/")
        if page.status_code != 200 or "LivePortrait" not in page.text:
            raise RuntimeError("frontend page did not load")
        _expect(client.get("/api/jobs?limit=1"), 401)

        key_payload = _expect(
            client.post(
                "/api/admin/api-keys",
                headers=admin_headers,
                json={
                    "owner_id": "local-acceptance-user",
                    "label": "Local product workflow",
                    "role": "user",
                },
            ),
            201,
        )
        user_key = key_payload["api_key"]
        user_headers = {"x-api-key": user_key}
        identity = _expect(client.get("/api/whoami", headers=user_headers), 200)

        created_job = _expect(
            client.post(
                "/api/jobs",
                headers={
                    **user_headers,
                    "x-idempotency-key": "local-product-workflow-001",
                },
                data={
                    "consent_confirmed": "true",
                    "authorization_basis": "internal_test",
                    "authorization_reference": "LOCAL-PRODUCT-WORKFLOW",
                    "authorization_status": "approved",
                },
                files={
                    "source": ("source.jpg", b"source-image-bytes", "image/jpeg"),
                    "driving": ("driving.jpg", b"driving-image-bytes", "image/jpeg"),
                },
            ),
            201,
        )
        repeated_job = _expect(
            client.post(
                "/api/jobs",
                headers={
                    **user_headers,
                    "x-idempotency-key": "local-product-workflow-001",
                },
                data={"consent_confirmed": "true"},
                files={
                    "source": ("source.jpg", b"source-image-bytes", "image/jpeg"),
                    "driving": ("driving.jpg", b"driving-image-bytes", "image/jpeg"),
                },
            ),
            200,
        )
        if repeated_job["job_id"] != created_job["job_id"]:
            raise RuntimeError("idempotent submit did not return the original job")

        user_jobs = _expect(client.get("/api/jobs?limit=5", headers=user_headers), 200)
        job_export = _expect(client.get(f"/api/jobs/{created_job['job_id']}/export", headers=user_headers), 200)

        store = app.state.job_store
        store.mark_failed(created_job["job_id"], "local non-GPU workflow retry simulation")
        retry = _expect(client.post(f"/api/jobs/{created_job['job_id']}/retry", headers=user_headers), 202)
        cleanup = _expect(
            client.post(
                "/api/cleanup-runs",
                headers=admin_headers,
                json={"older_than_days": 7, "dry_run": True},
            ),
            201,
        )
        revoked = _expect(
            client.post(f"/api/admin/api-keys/{key_payload['key_id']}/revoke", headers=admin_headers),
            200,
        )
        _expect(client.get("/api/jobs?limit=1", headers=user_headers), 401)

        operations_export = _expect(
            client.get("/api/admin/audit-events/export?limit=20", headers=admin_headers),
            200,
        )
        actions = [event["action"] for event in operations_export["events"]]
        expected_actions = {"api_key.created", "job.retried", "cleanup.dry_run", "api_key.revoked"}
        if not expected_actions.issubset(set(actions)):
            raise RuntimeError(f"operations audit export is missing actions: {sorted(expected_actions - set(actions))}")
        if user_key in json.dumps(operations_export):
            raise RuntimeError("operations audit export leaked the raw user API Key")

        return {
            "status": "passed",
            "data_dir": str(data_dir),
            "health_status": health["status"],
            "frontend_loaded": True,
            "user_owner_id": identity["owner_id"],
            "created_job_id": created_job["job_id"],
            "idempotent_job_id": repeated_job["job_id"],
            "recent_jobs": len(user_jobs["jobs"]),
            "job_export_version": job_export["export_version"],
            "retry_status": retry["status"],
            "cleanup_dry_run": cleanup["dry_run"],
            "cleanup_matched_jobs": cleanup["matched_jobs"],
            "cleanup_operational_audit_matched_events": cleanup["operational_audit_matched_events"],
            "revoked_key_status": revoked["status"],
            "operations_export_version": operations_export["export_version"],
            "operations_export_actions": actions,
            "raw_user_key_leaked": False,
        }


def _expect(response, expected_status: int) -> dict:
    if response.status_code != expected_status:
        raise RuntimeError(
            f"expected HTTP {expected_status}, got {response.status_code}: {response.text[:500]}"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("response did not contain JSON") from exc


if __name__ == "__main__":
    raise SystemExit(main())
