# coding: utf-8

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit a real LivePortrait API job and download the result.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument("--api-key", required=True, help="API Key sent as x-api-key.")
    parser.add_argument("--source", type=Path, default=Path("assets/examples/source/s9.jpg"), help="Source image.")
    parser.add_argument("--driving", type=Path, default=Path("assets/examples/driving/d12.jpg"), help="Driving image/video.")
    parser.add_argument("--output", type=Path, default=Path("tmp/api-smoke-result"), help="Downloaded result path.")
    parser.add_argument("--timeout-seconds", type=int, default=300, help="Maximum wait time for the job.")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help="Seconds between status checks.")
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    try:
        job_id = _create_job(base_url, args.api_key, args.source, args.driving)
        print(f"Created job: {job_id}")
        job = _wait_for_job(base_url, args.api_key, job_id, args.timeout_seconds, args.poll_seconds)
        if job.get("status") != "succeeded":
            print(f"Job did not succeed: {job}", file=sys.stderr)
            return 1
        output_path = _download_result(base_url, args.api_key, job_id, args.output)
    except Exception as exc:
        print(f"API smoke job failed: {exc}", file=sys.stderr)
        return 1

    print(f"Status: succeeded")
    print(f"Downloaded result: {output_path}")
    return 0


def _create_job(base_url: str, api_key: str, source: Path, driving: Path) -> str:
    if not source.exists():
        raise FileNotFoundError(source)
    if not driving.exists():
        raise FileNotFoundError(driving)

    boundary = f"----LivePortraitBoundary{uuid.uuid4().hex}"
    body = b"".join(
        [
            _file_part(boundary, "source", source),
            _file_part(boundary, "driving", driving),
            _text_part(boundary, "consent_confirmed", "true"),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    request = urllib.request.Request(
        f"{base_url}/api/jobs",
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "x-api-key": api_key,
        },
    )
    payload = _request_json(request)
    job_id = payload.get("job_id")
    if not job_id:
        raise RuntimeError(f"Create job response did not include job_id: {payload}")
    return job_id


def _wait_for_job(base_url: str, api_key: str, job_id: str, timeout_seconds: int, poll_seconds: float) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        request = urllib.request.Request(
            f"{base_url}/api/jobs/{job_id}",
            headers={"x-api-key": api_key},
        )
        payload = _request_json(request)
        status = payload.get("status")
        print(f"Status: {status}")
        if status in {"succeeded", "failed"}:
            return payload
        time.sleep(poll_seconds)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout_seconds} seconds.")


def _download_result(base_url: str, api_key: str, job_id: str, output: Path) -> Path:
    suffix = output.suffix
    if not suffix:
        output = output.with_suffix(".bin")
    output.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        f"{base_url}/api/jobs/{job_id}/result",
        headers={"x-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            output.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc
    return output


def _file_part(boundary: str, field_name: str, path: Path) -> bytes:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    )
    return header.encode("utf-8") + path.read_bytes() + b"\r\n"


def _text_part(boundary: str, field_name: str, value: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")


def _request_json(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {message}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
