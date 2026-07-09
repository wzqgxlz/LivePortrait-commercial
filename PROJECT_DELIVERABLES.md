# Project Deliverables

This file is the running deliverables index for the commercial-safe
LivePortrait project. Keep it updated whenever a new product, API, frontend,
deployment, compliance, test, or documentation artifact is added.

## Update Rule

- Add every new deliverable to this file before or with the same checkpoint
  commit that creates it.
- Prefer stable repo-relative paths, so the file remains useful after cloning
  the repository onto a GPU machine.
- Record only project artifacts. Do not record local caches such as
  `__pycache__`, `.pytest_cache`, temporary smoke-test outputs, or downloaded
  browser runtimes.

## Current Working Branch

- Branch: `codex/commercial-mediapipe-cropper`
- Remote repository: `https://github.com/wzqgxlz/LivePortrait-commercial.git`
- Current product scope: commercial-safe Humans mode first. Animals mode remains
  out of scope until X-Pose and animal model licensing are separately reviewed.

## Product Status

The project has moved from commercial-safety migration into an MVP product
wrapper:

- Commercial-safe MediaPipe-based human face detection path.
- Minimal FastAPI job service.
- Minimal browser upload frontend.
- API Key protection.
- Source image authorization confirmation.
- Job queue/status tracking.
- Result download.
- Audit timeline and audit JSON export.
- Upload type/size limits and active queue limit.
- Recent job status filtering for lightweight operations triage.
- Cleanup run records for retention/deletion evidence.
- GPU deployment and smoke-test scripts.

## Core Commercial-Safety Deliverables

| Artifact | Path | Purpose |
| --- | --- | --- |
| Third-party license inventory | `THIRD_PARTY_LICENSES.md` | Tracks LivePortrait, MediaPipe, PyTorch, ONNX, OpenCV, Gradio, and related dependency license notes. |
| Commercial safety checks | `src/utils/commercial_safety.py` | Runtime guardrails that prevent commercial builds from using removed InsightFace assets or imports. |
| Commercial safety scan script | `scripts/commercial_safety_scan.py` | CI/local scan for blocked InsightFace references and unsafe assets. |
| MediaPipe face adapter | `src/utils/mediapipe_face_analysis.py` | Replaces the InsightFace face-analysis dependency for Humans mode detection. |
| Cropper integration | `src/utils/cropper.py` | Integrates the commercial-safe detection path with the existing LivePortrait crop pipeline. |
| Commercial cropper tests | `tests/test_commercial_mediapipe_cropper.py` | Regression coverage for the MediaPipe cropper behavior. |
| Commercial guardrail tests | `tests/test_commercial_safety_guardrails.py` | Regression coverage for blocked InsightFace paths/references. |

## API Service Deliverables

| Artifact | Path | Purpose |
| --- | --- | --- |
| FastAPI application | `src/api/app.py` | Serves the frontend and API endpoints for job creation, status, result, audit, export, and health checks. |
| API configuration | `src/api/config.py` | Centralizes environment-driven settings: data directory, Python executable, CPU/GPU mode, API Key, upload limit, and active job limit. |
| Inference runner | `src/api/runner.py` | Builds and runs Humans mode inference commands from API jobs. |
| SQLite job store | `src/api/storage.py` | Stores jobs, statuses, hashes, authorization confirmation, audit events, and output metadata. |
| Cleanup helper | `src/api/cleanup.py` | Deletes old terminal jobs and their files, and can append cleanup run records. |
| API package marker | `src/api/__init__.py` | Makes the API folder importable for `uvicorn src.api.app:app`. |

## Frontend Deliverables

| Artifact | Path | Purpose |
| --- | --- | --- |
| Minimal upload page | `src/api/static/index.html` | Browser UI for API Key entry, source/driving upload, consent confirmation, job status, result preview, recent jobs, and job details. |
| Frontend behavior | `src/api/static/app.js` | Handles API Key storage, client-side upload validation, job submission, polling, result download, audit export, recent jobs, and job detail rendering. |
| Frontend styles | `src/api/static/styles.css` | Provides responsive layout, upload boxes, inline errors, job status chips, result preview, and job detail styling. |

## Frontend Features Delivered

- Source image upload: `.jpg`, `.jpeg`, `.png`.
- Driving upload: `.jpg`, `.jpeg`, `.png`, `.mp4`, `.pkl`.
- API Key stored in browser local storage.
- Source authorization checkbox before submission.
- Client-side file type and file size validation.
- Inline form errors for missing files, unsupported types, oversized files, and missing consent.
- Job submission and status polling.
- Result preview and result download.
- Audit JSON download after success.
- Recent jobs list.
- Job detail panel with status, Job ID, filenames, timestamps, input hashes, output hash, and failure reason.
- Clear button for the current selected job.
- API Key guidance that tells users whether a key is saved locally.
- First-use empty state in the result preview area.
- Completion panel after a successful generation with download guidance.
- Recent jobs status filter for `pending`, `running`, `succeeded`, and `failed`.

## Deployment And GPU Migration Deliverables

| Artifact | Path | Purpose |
| --- | --- | --- |
| GPU deployment guide | `docs/gpu-api-deployment.md` | Step-by-step cloud GPU setup, dependency installation, API startup, smoke test, systemd setup, and cleanup notes. |
| API service guide | `docs/mvp-api-service.md` | Local/API usage guide, endpoint descriptions, auth behavior, frontend notes, smoke test records, and cleanup flow. |
| systemd environment template | `deploy/liveportrait-api.env.example` | Production-style environment variables for API deployment. |
| systemd service template | `deploy/liveportrait-api.service` | Example Linux service unit for long-running API deployment. |
| GPU API startup script | `scripts/start_gpu_api_server.sh` | Starts the API on a GPU machine after checking required environment and commercial-safety guardrails. |
| Deployment check script | `scripts/check_api_deployment.py` | Non-inference HTTP checks for health, frontend, and API Key protection. |
| Real API smoke job script | `scripts/smoke_api_job.py` | Uploads real source/driving assets, polls job status, and downloads the result. |
| Humans assets downloader | `scripts/download_humans_assets.py` | Downloads Humans mode assets and the MediaPipe detector model for migration/deployment. |
| Humans regression script | `scripts/run_humans_regression.py` | Runs focused Humans mode regression cases. |
| API cleanup script | `scripts/cleanup_api_jobs.py` | Removes old succeeded/failed jobs from API storage and records each run in `cleanup-runs.jsonl`. |

## Documentation Deliverables

| Artifact | Path | Purpose |
| --- | --- | --- |
| Deliverables index | `PROJECT_DELIVERABLES.md` | This running inventory of project outputs. |
| API service guide | `docs/mvp-api-service.md` | Main operator/developer reference for the MVP API and frontend. |
| GPU deployment guide | `docs/gpu-api-deployment.md` | GPU machine setup and deployment reference. |
| Humans regression record | `docs/humans-mediapipe-regression-2026-07-08.md` | Recorded Humans mode MediaPipe regression notes. |
| Commercial migration plan | `docs/superpowers/plans/2026-07-08-commercial-mediapipe-cropper.md` | Implementation plan used for the commercial-safe MediaPipe migration. |

## Test Deliverables

| Artifact | Path | Purpose |
| --- | --- | --- |
| API service tests | `tests/test_api_service.py` | Covers frontend static assets, job creation, consent, API Key auth, result endpoint, audit export, upload validation, and queue limit behavior. |
| API storage tests | `tests/test_api_storage.py` | Covers SQLite job persistence, hashes, status transitions, and audit records. |
| API cleanup tests | `tests/test_api_cleanup.py` | Covers deletion behavior for old terminal jobs. |
| Deployment script tests | `tests/test_deployment_scripts.py` | Covers deployment scripts, env templates, docs, auth checks, and smoke-job script expectations. |
| GPU migration script tests | `tests/test_gpu_migration_scripts.py` | Covers GPU migration helper script expectations. |
| Commercial cropper tests | `tests/test_commercial_mediapipe_cropper.py` | Covers the MediaPipe cropper path. |
| Commercial guardrail tests | `tests/test_commercial_safety_guardrails.py` | Covers InsightFace removal and commercial-safety guardrails. |

## Verified Commands

Recent checkpoints have been verified with:

```powershell
python -m pytest -q
python scripts\commercial_safety_scan.py
node --check src\api\static\app.js
python scripts\check_api_deployment.py --base-url http://127.0.0.1:<port> --api-key test-key
```

Latest known full test result:

```text
38 passed
Commercial safety scan passed.
```

## Recent Checkpoint Commits

| Commit | Summary |
| --- | --- |
| `00b64f8` | `feat: refine frontend trial experience` |
| `6b82ff8` | `docs: add project deliverables index` |
| `69c8926` | `feat: add frontend job detail panel` |
| `28ae147` | `feat: improve frontend upload feedback` |
| `9157652` | `feat: add upload and queue safety limits` |
| `6fa2fed` | `feat: add audit export download` |
| `22a91df` | `feat: add recent job history` |
| `6744a7c` | `feat: add api job audit trail` |
| `e6a869b` | `feat: require source authorization consent` |
| `3fa9b64` | `chore: add api smoke job script` |
| `8715197` | `chore: add deployment runtime templates` |
| `4dd329e` | `chore: add gpu api deployment guide` |
| `c623440` | `feat: add minimal api frontend` |
| `3ed5214` | `feat: add mvp api job service` |

## Runtime Outputs Not Tracked As Deliverables

These folders may contain local generated data, but they are not product
deliverables and should not be used as the source of truth:

- `tmp/`
- `output/`
- `.pytest_cache/`
- `__pycache__/`
- local downloaded model/browser caches

API-generated uploads, job database files, and result files usually live under
`tmp/api` or the configured `LIVEPORTRAIT_API_DATA_DIR`.
Cleanup run records live in `cleanup-runs.jsonl` under the same API data
directory.

## Next Deliverables To Add Here

When implemented, add new entries for:

- Deployment acceptance checklist.
- Production operations notes.
- Content moderation and authorization-record workflow.
- Billing/admin/backend artifacts, if built.
- Any GPU regression report from a rented GPU machine.
