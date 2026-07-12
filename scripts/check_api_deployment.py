# coding: utf-8

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: str


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a deployed LivePortrait API/frontend service.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument("--api-key", default=None, help="API Key to verify authenticated requests.")
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    checks = [
        _check_health(base_url),
        _check_frontend(base_url),
        _check_auth_guard(base_url),
        _check_job_list_auth_guard(base_url),
        _check_audit_auth_guard(base_url),
        _check_export_auth_guard(base_url),
        _check_authorization_export_auth_guard(base_url),
        _check_operations_audit_export_auth_guard(base_url),
        _check_cleanup_runs_auth_guard(base_url),
        _check_cleanup_create_auth_guard(base_url),
    ]
    if args.api_key:
        checks.append(_check_authenticated_request(base_url, args.api_key))

    failed = [message for ok, message in checks if not ok]
    for ok, message in checks:
        prefix = "OK" if ok else "FAIL"
        print(f"{prefix}: {message}")

    return 1 if failed else 0


def _check_health(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/health")
    if result.status != 200:
        return False, f"Health check returned HTTP {result.status}."
    try:
        payload = json.loads(result.body)
    except json.JSONDecodeError:
        return False, "Health check did not return JSON."
    if payload.get("status") != "ok":
        return False, "Health check JSON did not contain status=ok."
    return True, "Health endpoint returned status=ok."


def _check_frontend(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/")
    if result.status != 200:
        return False, f"Frontend returned HTTP {result.status}."
    if "LivePortrait" not in result.body or 'id="source"' not in result.body:
        return False, "Frontend page did not contain expected LivePortrait upload controls."
    return True, "Frontend page loaded."


def _check_auth_guard(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/jobs/not-found")
    if result.status == 401:
        return True, "Expected unauthorized response without x-api-key."
    return False, f"Expected unauthorized response without x-api-key, got HTTP {result.status}."


def _check_job_list_auth_guard(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/jobs?limit=1")
    if result.status == 401:
        return True, "Job list endpoint rejects requests without x-api-key."
    return False, f"Job list endpoint should reject requests without x-api-key, got HTTP {result.status}."


def _check_audit_auth_guard(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/jobs/not-found/audit")
    if result.status == 401:
        return True, "Audit endpoint rejects requests without x-api-key."
    return False, f"Audit endpoint should reject requests without x-api-key, got HTTP {result.status}."


def _check_export_auth_guard(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/jobs/not-found/export")
    if result.status == 401:
        return True, "Audit export endpoint rejects requests without x-api-key."
    return False, f"Audit export endpoint should reject requests without x-api-key, got HTTP {result.status}."


def _check_authorization_export_auth_guard(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/authorization-records/export?authorization_reference=not-found")
    if result.status == 401:
        return True, "Authorization export endpoint rejects requests without x-api-key."
    return False, f"Authorization export endpoint should reject requests without x-api-key, got HTTP {result.status}."


def _check_operations_audit_export_auth_guard(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/admin/audit-events/export")
    if result.status == 401:
        return True, "Operations audit export endpoint rejects requests without x-api-key."
    return False, f"Operations audit export endpoint should reject requests without x-api-key, got HTTP {result.status}."


def _check_cleanup_runs_auth_guard(base_url: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/cleanup-runs?limit=1")
    if result.status == 401:
        return True, "Cleanup runs endpoint rejects requests without x-api-key."
    return False, f"Cleanup runs endpoint should reject requests without x-api-key, got HTTP {result.status}."


def _check_cleanup_create_auth_guard(base_url: str) -> tuple[bool, str]:
    result = _post_json(f"{base_url}/api/cleanup-runs", {"older_than_days": 7, "dry_run": True})
    if result.status == 401:
        return True, "Cleanup create endpoint rejects requests without x-api-key."
    return False, f"Cleanup create endpoint should reject requests without x-api-key, got HTTP {result.status}."


def _check_authenticated_request(base_url: str, api_key: str) -> tuple[bool, str]:
    headers = {"x-api-key": api_key}
    identity_result = _get(f"{base_url}/api/whoami", headers=headers)
    if identity_result.status != 200:
        return False, f"Authenticated identity endpoint check returned HTTP {identity_result.status}."
    result = _get(f"{base_url}/api/jobs/not-found", headers=headers)
    if result.status == 404:
        return True, "Authenticated request reached the identity and jobs endpoints."
    return False, f"Authenticated jobs endpoint check returned HTTP {result.status}."


def _get(url: str, headers: dict[str, str] | None = None) -> HttpResult:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return HttpResult(status=response.status, body=response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return HttpResult(status=exc.code, body=exc.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return HttpResult(status=0, body="")


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> HttpResult:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return HttpResult(status=response.status, body=response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return HttpResult(status=exc.code, body=exc.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return HttpResult(status=0, body="")


if __name__ == "__main__":
    raise SystemExit(main())
