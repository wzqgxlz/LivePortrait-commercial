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

Useful environment variables:

```powershell
$env:LIVEPORTRAIT_API_DATA_DIR = "tmp/api"
$env:LIVEPORTRAIT_API_PYTHON = ".\LivePortrait_env\Scripts\python.exe"
$env:LIVEPORTRAIT_API_FORCE_CPU = "0"
$env:LIVEPORTRAIT_API_KEY = "replace-with-a-long-random-secret"
```

Set `LIVEPORTRAIT_API_FORCE_CPU=1` only for local smoke tests without an NVIDIA
GPU.

Set `LIVEPORTRAIT_API_KEY` before exposing the service to any network. When it
is unset, the API stays open for local development and smoke tests. When it is
set, every job endpoint requires the same value in the `x-api-key` header.

## Authentication

Protected endpoints:

- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/result`

Public endpoint:

- `GET /api/health`

Example with API Key enabled:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/jobs" `
  -H "x-api-key: replace-with-a-long-random-secret" `
  -F "source=@assets/examples/source/s9.jpg" `
  -F "driving=@assets/examples/driving/d12.jpg"
```

## Endpoints

### Create Job

```http
POST /api/jobs
```

Multipart files:

- `source`: `.jpg`, `.jpeg`, `.png`
- `driving`: `.jpg`, `.jpeg`, `.png`, `.mp4`, `.pkl`

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

### Download Result

```http
GET /api/jobs/{job_id}/result
```

Returns `409` until the job has succeeded.

## Before Serving Users

Run these checks on the deployment machine:

```powershell
python scripts\download_humans_assets.py
python scripts\commercial_safety_scan.py
python -m pytest tests/test_commercial_mediapipe_cropper.py tests/test_commercial_safety_guardrails.py tests/test_gpu_migration_scripts.py tests/test_api_service.py -q
```

The service must not start with `pretrained_weights/insightface` present.

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
  -F "driving=@assets/examples/driving/d12.jpg"
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
- The in-process worker completed the LivePortrait Humans mode job.
- `GET /api/jobs/{job_id}` returned `succeeded`.
- `GET /api/jobs/{job_id}/result` downloaded a 275,418-byte image.
- The smoke test passed end to end.
