# Local Product Workflow Acceptance - 2026-07-12

This record covers the non-GPU product shell workflow for the commercial-safe
Humans mode MVP. It intentionally does not run LivePortrait inference. The goal
is to verify authentication, user isolation, job submission, idempotency, audit
exports, retry, cleanup dry-run, and operational audit export before GPU
validation.

Animals mode is out of scope.

## Command

```powershell
python scripts\check_local_product_workflow.py
```

## Scope

The script runs the FastAPI app in-process with:

- `enqueue_jobs=False`
- `run_startup_checks=False`
- `LIVEPORTRAIT_API_FORCE_CPU` equivalent behavior through `ApiConfig(force_cpu=True)`
- a temporary API data directory
- a bootstrap administrator API Key used only inside the test

## Workflow Verified

- API health endpoint returned `status=ok`.
- Frontend HTML loaded and contained the LivePortrait upload page.
- Protected endpoints rejected unauthenticated requests.
- Administrator issued a personal `role=user` API Key.
- User identity returned `owner_id=local-acceptance-user`.
- User submitted a job with source authorization metadata.
- Repeating the same `x-idempotency-key` returned the original job.
- User listed only their own recent job.
- User downloaded a per-job audit export.
- A failed-job retry was simulated without running inference.
- Administrator ran cleanup dry-run.
- Administrator revoked the user Key.
- Revoked user Key was rejected.
- Administrator downloaded the operational audit export.
- Operational audit export contained the expected management actions.
- Raw user API Key did not appear in the operational audit export.

## Observed Result

```json
{
  "cleanup_dry_run": true,
  "cleanup_matched_jobs": 0,
  "cleanup_operational_audit_matched_events": 0,
  "created_job_id": "d6e6f00ee8fc4f89b4f030c216fbbe2e",
  "frontend_loaded": true,
  "health_status": "ok",
  "idempotent_job_id": "d6e6f00ee8fc4f89b4f030c216fbbe2e",
  "job_export_version": "liveportrait-audit-export-v1",
  "operations_export_actions": [
    "api_key.revoked",
    "cleanup.dry_run",
    "job.retried",
    "api_key.created"
  ],
  "operations_export_version": "liveportrait-operational-audit-export-v1",
  "raw_user_key_leaked": false,
  "recent_jobs": 1,
  "retry_status": "pending",
  "revoked_key_status": "revoked",
  "status": "passed",
  "user_owner_id": "local-acceptance-user"
}
```

## Result

Pass.

This verifies the product shell without GPU inference. GPU validation remains a
separate acceptance stage and must still run real Humans mode image/video
generation on an NVIDIA GPU machine.
