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
  - `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER=3`
  - `LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB=2`
- Keep `LIVEPORTRAIT_API_KEY` as the bootstrap administrator Key; issue each
  tester/customer a separate personal Key instead of sharing it.
- Start the API behind HTTPS before any public network access. Use
  `deploy/nginx-liveportrait-api.conf` or `deploy/Caddyfile.example` as the
  baseline reverse proxy template.

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
- Confirm the public HTTPS domain redirects from HTTP and serves a valid
  certificate.
- Confirm the API Key still protects job endpoints.
- Check available disk space for `LIVEPORTRAIT_API_DATA_DIR`.
- Check GPU memory before raising `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS`.
- Check reverse proxy access/error logs for upload errors, `413`, `499`, `502`,
  or timeout spikes.

### Access Management

- Use the frontend Access management panel or `GET /api/admin/api-keys` with
  the bootstrap administrator Key to review issued personal Keys without
  exposing their secret values.
- Issue a separate `role=user` Key for each customer, tester, or integration.
- Revoke a Key from the frontend or with
  `POST /api/admin/api-keys/{key_id}/revoke` as soon as it is no longer needed
  or may have been exposed.
- Confirm a user Key can access only its own jobs through `GET /api/whoami` and
  `GET /api/jobs`.
- Keep cleanup and cross-customer support work on an administrator Key.

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

Use authorization filters to review customer or pilot records:

```http
GET /api/jobs?authorization_status=approved
GET /api/jobs?authorization_status=needs_review
GET /api/jobs?authorization_reference=CRM-2026-0001
```

The frontend exposes the same job-status, authorization-status, and
authorization-reference filters in the Recent jobs section. Administrators also
get an owner filter for cross-customer support checks.

### Restart And Retry Handling

- After a planned or unplanned API restart, `pending` jobs are requeued.
- Jobs that were `running` during the restart become `failed` with an
  `interrupted` audit event. Review the job, then use
  `POST /api/jobs/{job_id}/retry` if a new execution is appropriate.
- The retry keeps the same job ID and audit history. Do not create a duplicate
  upload for a simple retry.
- API clients should send a distinct `x-idempotency-key` for every new logical
  submission. Repeat requests with the same Key return the original job.

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

Review recent cleanup records through the API or frontend:

```http
GET /api/cleanup-runs?limit=20
```

The frontend Cleanup runs panel can also start a cleanup. Use `Dry run` first.
Actual deletion requires the confirmed delete action, which sends:

```http
POST /api/cleanup-runs
```

with `dry_run=false` and `confirm_delete=true`.

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

5. If a report covers all work under one authorization record, export the
   reference package.

```http
GET /api/authorization-records/export?authorization_reference=CRM-2026-0001
```

The export contains input hashes, output hash when available, authorization
confirmation, policy version, timestamps, status, failure message, and audit
events. The authorization-reference export contains the same job and audit data
for up to 100 recent jobs tied to that reference. Do not share source images,
driving files, or generated output outside the authorized support channel.

## Incident Response

Use this lightweight flow for MVP incidents.

### Unauthorized Or Suspicious Use

- Stop sharing the current API Key.
- Revoke the exposed personal Key through `POST /api/admin/api-keys/{key_id}/revoke`.
- Rotate `LIVEPORTRAIT_API_KEY` only when the bootstrap administrator Key is
  exposed, then restart the service.
- Preserve the related job export from `GET /api/jobs/{job_id}/export`.
- Preserve `cleanup-runs.jsonl` and service logs.
- Review the source authorization confirmation and policy version in the export.

### Queue Or GPU Pressure

- Lower `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS`.
- Restart the service during a maintenance window.
- Review `GET /api/jobs?status=running` and `GET /api/jobs?status=pending`.
- Keep failed job exports for debugging before cleanup.
- Lower `LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB` if repeated failures are creating
  avoidable pressure.

### Reverse Proxy Or HTTPS Failure

- Keep the API service running on the internal port while fixing the proxy.
- Validate Nginx with `sudo nginx -t` or Caddy with
  `sudo caddy validate --config /etc/caddy/Caddyfile`.
- Confirm the reverse proxy upload limit is above
  `LIVEPORTRAIT_API_MAX_UPLOAD_BYTES`.
- Check certificate renewal status before rotating DNS or firewall rules.
- Run `scripts/check_api_deployment.py` against both `http://127.0.0.1:8000`
  and the public HTTPS URL to isolate proxy issues from API issues.

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
- Follow `docs/content-safety-authorization-workflow.md` for MVP authorization
  records, content review, prohibited uses, and manual review.

## MVP Limitations

- API Key issuance/revocation is available through administrator endpoints and
  the browser Access management panel, but there is not yet a full account login
  system.
- SQLite and local disk are suitable for MVP/single-node operation, not
  multi-node production.
- The included Nginx/Caddy files are deployment templates; production domains,
  certificate paths, firewall rules, rate limiting, and WAF/CDN policy still
  need environment-specific review.
- Personal API Keys provide `user` and `admin` roles plus task isolation, but
  full user accounts, billing, and per-customer authorization records are
  future work.
- Content moderation and formal consent-record workflows are future work.
