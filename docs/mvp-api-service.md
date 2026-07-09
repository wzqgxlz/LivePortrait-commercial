# MVP API Service

This service is the first product-facing wrapper around the commercial-safe
Humans mode pipeline. It is intentionally small: one local SQLite database, one
local upload/output directory, and one in-process worker that runs jobs in
sequence.

Animals mode is not supported by this API.

## Start

```powershell
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Open the minimal upload page at:

```text
http://127.0.0.1:8000/
```

Useful environment variables:

```powershell
$env:LIVEPORTRAIT_API_DATA_DIR = "tmp/api"
$env:LIVEPORTRAIT_API_PYTHON = ".\LivePortrait_env\Scripts\python.exe"
$env:LIVEPORTRAIT_API_FORCE_CPU = "0"
$env:LIVEPORTRAIT_API_KEY = "replace-with-a-long-random-secret"
$env:LIVEPORTRAIT_API_MAX_UPLOAD_BYTES = "209715200"
$env:LIVEPORTRAIT_API_MAX_ACTIVE_JOBS = "20"
```

Set `LIVEPORTRAIT_API_FORCE_CPU=1` only for local smoke tests without an NVIDIA
GPU.

Set `LIVEPORTRAIT_API_KEY` before exposing the service to any network. When it
is unset, the API stays open for local development and smoke tests. When it is
set, every job endpoint requires the same value in the `x-api-key` header.

`LIVEPORTRAIT_API_MAX_UPLOAD_BYTES` limits each uploaded file. The default is
209,715,200 bytes, about 200 MB. `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS` limits the
number of `pending` plus `running` jobs. The default is 20; when the queue is
full, `POST /api/jobs` returns `429`.

## Authentication

Protected endpoints:

- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/result`
- `GET /api/jobs/{job_id}/audit`
- `GET /api/jobs/{job_id}/export`

Public endpoint:

- `GET /api/health`

Example with API Key enabled:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/jobs" `
  -H "x-api-key: replace-with-a-long-random-secret" `
  -F "source=@assets/examples/source/s9.jpg" `
  -F "driving=@assets/examples/driving/d12.jpg" `
  -F "consent_confirmed=true"
```

The frontend page stores the API Key in the browser's local storage and sends it
as `x-api-key` when creating jobs, polling status, and downloading results.

## Endpoints

### Create Job

```http
POST /api/jobs
```

Multipart files:

- `source`: `.jpg`, `.jpeg`, `.png`
- `driving`: `.jpg`, `.jpeg`, `.png`, `.mp4`, `.pkl`

Uploads are checked by extension and content type. Source files must be JPEG or
PNG. Driving files can be JPEG, PNG, MP4, or PKL.

Required form field:

- `consent_confirmed=true`: confirms the user has permission to use the source
  image and accepts the usage restrictions.

Response:

```json
{
  "job_id": "<job_id>",
  "status": "pending",
  "source_filename": "source.jpg",
  "driving_filename": "driving.mp4"
}
```

### Get Job

```http
GET /api/jobs/{job_id}
```

Status values:

- `pending`
- `running`
- `succeeded`
- `failed`

### List Recent Jobs

```http
GET /api/jobs?limit=20
```

Returns recent jobs in newest-first order. The frontend uses this endpoint to
show the Recent jobs list.

### Download Result

```http
GET /api/jobs/{job_id}/result
```

Returns `409` until the job has succeeded.

### Get Audit Events

```http
GET /api/jobs/{job_id}/audit
```

Returns the job timeline used for support and traceability. Events currently
include `created`, `running`, `succeeded`, and `failed`. The `created` event
records input hashes and the authorization policy version. Terminal events
record the output hash or failure message.

### Download Audit Export

```http
GET /api/jobs/{job_id}/export
```

Returns a downloadable JSON package with the job record, input/output hashes,
authorization confirmation, policy version, and audit event timeline. The
frontend exposes this as `Download audit JSON` after a job succeeds.

## Before Serving Users

Run these checks on the deployment machine:

```powershell
python scripts\download_humans_assets.py
python scripts\commercial_safety_scan.py
python -m pytest tests/test_commercial_mediapipe_cropper.py tests/test_commercial_safety_guardrails.py tests/test_gpu_migration_scripts.py tests/test_api_service.py tests/test_api_cleanup.py -q
```

The service must not start with `pretrained_weights/insightface` present.

## Job Cleanup

API uploads and outputs are stored under `LIVEPORTRAIT_API_DATA_DIR`. Use the
cleanup script to remove old finished jobs so this directory does not grow
forever.

Dry run first:

```powershell
python scripts\cleanup_api_jobs.py --older-than-days 7 --dry-run
```

Delete matched jobs:

```powershell
python scripts\cleanup_api_jobs.py --older-than-days 7
```

The cleanup only removes jobs whose status is `succeeded` or `failed` and whose
`updated_at` timestamp is older than the retention window. Jobs that are still
`pending` or `running` are skipped.

## Local Smoke Test - 2026-07-08

Environment:

- Machine: local Windows workstation
- Mode: CPU smoke test
- API Python: `.\LivePortrait_env\Scripts\python.exe`
- Source: `assets/examples/source/s9.jpg`
- Driving: `assets/examples/driving/d12.jpg`

Startup:

```powershell
cd D:\codex_work\LivePortrait
$env:LIVEPORTRAIT_API_FORCE_CPU = "1"
$env:LIVEPORTRAIT_API_PYTHON = ".\LivePortrait_env\Scripts\python.exe"
.\LivePortrait_env\Scripts\python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Create job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/jobs" `
  -F "source=@assets/examples/source/s9.jpg" `
  -F "driving=@assets/examples/driving/d12.jpg" `
  -F "consent_confirmed=true"
```

Observed job:

```text
ad27741556c142348232f5c13ce4ef3a
```

Status check:

```powershell
curl.exe "http://127.0.0.1:8000/api/jobs/ad27741556c142348232f5c13ce4ef3a"
```

Observed status:

```text
succeeded
```

Server-side result:

```text
tmp/api/jobs/ad27741556c142348232f5c13ce4ef3a/outputs/s9--d12.jpg
```

Download result:

```powershell
curl.exe -L "http://127.0.0.1:8000/api/jobs/ad27741556c142348232f5c13ce4ef3a/result" -o api_result.jpg
```

Result:

- `POST /api/jobs` accepted real uploads.
- The request confirmed source image authorization with `consent_confirmed=true`.
- The in-process worker completed the LivePortrait Humans mode job.
- `GET /api/jobs/{job_id}` returned `succeeded`.
- `GET /api/jobs/{job_id}/result` downloaded a 275,418-byte image.
- The job record includes `output_sha256` after success.
- The smoke test passed end to end.

## Frontend Smoke Test - 2026-07-08

Environment:

- Machine: local Windows workstation
- Mode: CPU smoke test
- API Python: `.\LivePortrait_env\Scripts\python.exe`
- API URL: `http://127.0.0.1:8771/`
- API Key: configured with `LIVEPORTRAIT_API_KEY`
- Source: `assets/examples/source/s9.jpg`
- Driving: `assets/examples/driving/d12.jpg`

Startup:

```powershell
cd D:\codex_work\LivePortrait
$env:LIVEPORTRAIT_API_FORCE_CPU = "1"
$env:LIVEPORTRAIT_API_PYTHON = ".\LivePortrait_env\Scripts\python.exe"
$env:LIVEPORTRAIT_API_DATA_DIR = "tmp/api-frontend-smoke"
$env:LIVEPORTRAIT_API_KEY = "frontend-smoke-key"
.\LivePortrait_env\Scripts\python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8771
```

Browser flow:

- Opened the frontend page.
- Entered the API Key.
- Confirmed source image authorization and usage restrictions.
- Selected the source image and driving image.
- Submitted the job from the page.
- Waited for the page to poll the job status.
- Confirmed the job appeared in Recent jobs.
- Confirmed the generated result preview appeared.
- Downloaded the result from the page.
- Downloaded the audit JSON export from the page.

Observed job:

```text
811a3426c9d041f996d65639aad8bf2c
```

Observed status:

```text
succeeded
```

Result:

- The frontend submitted real uploads through `POST /api/jobs`.
- The frontend sent `x-api-key` for job creation, polling, and result download.
- The frontend submitted `consent_confirmed=true` with the job.
- The page showed service health as `Online`.
- The page reached `succeeded` without manual command-line polling.
- The page displayed a generated image preview.
- The downloaded result was a 275,418-byte image.
- The preview image measured 720 x 1280.
- The page had no horizontal overflow at 1280 px desktop width.
