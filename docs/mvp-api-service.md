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
```

Set `LIVEPORTRAIT_API_FORCE_CPU=1` only for local smoke tests without an NVIDIA
GPU.

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
  "job_id": "…",
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
