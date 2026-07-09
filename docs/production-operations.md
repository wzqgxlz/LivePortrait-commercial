# Production Operations

This checklist is for running the commercial-safe Humans mode MVP after the API
and frontend are deployed. It assumes the service is already using the
MediaPipe-based detection path and the commercial safety scan has passed.

Animals mode is not covered here.

## Launch Checklist

Complete these before giving the service to any external tester or customer.

### Code And License

- Confirm the branch is `codex/commercial-mediapipe-cropper`.
- Confirm `THIRD_PARTY_LICENSES.md` is present and current.
- Run the commercial safety scan:

```bash
python scripts/commercial_safety_scan.py
```

- Confirm `pretrained_weights/insightface` is not present.
- Confirm `src/utils/dependencies/insightface` is not present.
- Confirm the service is limited to Humans mode.

### Runtime

- Set a non-empty `LIVEPORTRAIT_API_KEY`.
- Keep `LIVEPORTRAIT_API_FORCE_CPU=0` on GPU servers.
- Set `LIVEPORTRAIT_API_DATA_DIR` to a persistent disk path.
- Set conservative limits before load testing:
  - `LIVEPORTRAIT_API_MAX_UPLOAD_BYTES=209715200`
  - `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS=20`
- Start the API behind HTTPS before any public network access.

### Verification

Run the focused checks:

```bash
python -m pytest tests/test_api_service.py tests/test_api_cleanup.py tests/test_api_storage.py tests/test_deployment_scripts.py -q
python scripts/check_api_deployment.py --base-url http://127.0.0.1:8000 --api-key "$LIVEPORTRAIT_API_KEY"
```

Run a real smoke job on the deployment machine:

```bash
python scripts/smoke_api_job.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "$LIVEPORTRAIT_API_KEY" \
  --source assets/examples/source/s9.jpg \
  --driving assets/examples/driving/d12.jpg \
  --output tmp/api-smoke-result.jpg
```

Record the job ID, status, output path, and `output_sha256` in the launch notes
for that deployment.

## Daily Operations

Use these checks while the MVP is serving testers.

### Health

- Open `GET /api/health` and confirm `status=ok`.
- Confirm the frontend loads at `/`.
- Confirm the API Key still protects job endpoints.
- Check available disk space for `LIVEPORTRAIT_API_DATA_DIR`.
- Check GPU memory before raising `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS`.

### Job Review

Use the recent jobs endpoint:

```http
GET /api/jobs?limit=20
```

Use status filters for triage:

```http
GET /api/jobs?status=failed
GET /api/jobs?status=succeeded
GET /api/jobs?status=running
GET /api/jobs?status=pending
```

The frontend exposes the same filter in the Recent jobs section.

### Cleanup

Preview cleanup before deleting:

```bash
python scripts/cleanup_api_jobs.py --older-than-days 7 --dry-run
```

Delete old terminal jobs:

```bash
python scripts/cleanup_api_jobs.py --older-than-days 7
```

Each run appends one JSON line to:

```text
<LIVEPORTRAIT_API_DATA_DIR>/cleanup-runs.jsonl
```

Keep `cleanup-runs.jsonl` with the API data directory. It is the lightweight
retention/deletion evidence for this MVP.

## Support Export

Use this workflow when a tester reports a failed or suspicious generation.

1. Find the job.

```http
GET /api/jobs?status=failed
```

2. Inspect the current job record.

```http
GET /api/jobs/{job_id}
```

3. Download the support package.

```http
GET /api/jobs/{job_id}/export
```

4. If needed, inspect the raw audit timeline.

```http
GET /api/jobs/{job_id}/audit
```

The export contains input hashes, output hash when available, authorization
confirmation, policy version, timestamps, status, failure message, and audit
events. Do not share source images, driving files, or generated output outside
the authorized support channel.

## Incident Response

Use this lightweight flow for MVP incidents.

### Unauthorized Or Suspicious Use

- Stop sharing the current API Key.
- Rotate `LIVEPORTRAIT_API_KEY`.
- Preserve the related job export from `GET /api/jobs/{job_id}/export`.
- Preserve `cleanup-runs.jsonl` and service logs.
- Review the source authorization confirmation and policy version in the export.

### Queue Or GPU Pressure

- Lower `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS`.
- Restart the service during a maintenance window.
- Review `GET /api/jobs?status=running` and `GET /api/jobs?status=pending`.
- Keep failed job exports for debugging before cleanup.

### Disk Pressure

- Run cleanup dry-run first.
- Confirm the matched jobs are terminal.
- Run cleanup.
- Preserve the appended `cleanup-runs.jsonl` record.

## Retention Notes

- Keep audit exports for support cases according to your customer agreement.
- Keep `cleanup-runs.jsonl` for internal audit history.
- Do not keep raw user uploads longer than necessary for the active support or
  retention window.
- Before public launch, have legal counsel review open-source license,
  portrait-right, privacy, and deepfake policy language.

## MVP Limitations

- This is not yet a multi-user admin console.
- SQLite and local disk are suitable for MVP/single-node operation, not
  multi-node production.
- API Key auth is coarse-grained. User accounts, roles, and per-customer
  authorization records are future work.
- Content moderation and formal consent-record workflows are future work.
