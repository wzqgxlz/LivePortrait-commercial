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


def _check_authenticated_request(base_url: str, api_key: str) -> tuple[bool, str]:
    result = _get(f"{base_url}/api/jobs/not-found", headers={"x-api-key": api_key})
    if result.status == 404:
        return True, "Authenticated request reached the jobs endpoint."
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


if __name__ == "__main__":
    raise SystemExit(main())
