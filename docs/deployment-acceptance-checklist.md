# Deployment Acceptance Checklist

Use this checklist when moving the commercial-safe Humans mode MVP onto a new
GPU machine or when refreshing an existing deployment. It is designed to produce
clear acceptance evidence before a tester or customer uses the service.

Animals mode is out of scope for this checklist.

## Acceptance Stages

### 1. Repository And Branch

- [ ] Repository cloned from `https://github.com/wzqgxlz/LivePortrait-commercial.git`.
- [ ] Branch is `codex/commercial-mediapipe-cropper`.
- [ ] Latest expected commit is recorded.
- [ ] `PROJECT_DELIVERABLES.md` is present.
- [ ] `THIRD_PARTY_LICENSES.md` is present.

Evidence to record:

```bash
git branch --show-current
git log -1 --oneline
```

### 2. Commercial Safety

- [ ] `pretrained_weights/insightface` is absent.
- [ ] `src/utils/dependencies/insightface` is absent.
- [ ] Humans mode assets are present.
- [ ] MediaPipe detector asset is present.
- [ ] Commercial safety scan passes.

Command:

```bash
python scripts/commercial_safety_scan.py
```

Pass/Fail Criteria:

- Pass: scan exits successfully and prints `Commercial safety scan passed.`
- Fail: any blocked InsightFace path or reference is detected.

### 3. GPU Runtime

- [ ] `nvidia-smi` shows the expected GPU.
- [ ] PyTorch imports successfully.
- [ ] `torch.cuda.is_available()` is `True`.
- [ ] `LIVEPORTRAIT_API_FORCE_CPU=0`.
- [ ] `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS` is conservative for the GPU memory.

Commands:

```bash
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Pass/Fail Criteria:

- Pass: GPU is visible and CUDA is available to PyTorch.
- Fail: CUDA is unavailable, the GPU is missing, or the service is still forced
  into CPU mode.

### 4. API Configuration

- [ ] `LIVEPORTRAIT_API_KEY` is non-empty and not the template value.
- [ ] `LIVEPORTRAIT_API_DATA_DIR` points to persistent storage.
- [ ] `LIVEPORTRAIT_API_MAX_UPLOAD_BYTES` is set.
- [ ] `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS` is set.
- [ ] Service starts with `scripts/start_gpu_api_server.sh` or systemd.

Evidence to record:

```bash
env | grep LIVEPORTRAIT_API
```

Do not paste the raw API Key into shared acceptance notes.

### 5. Lightweight Deployment Check

Run:

```bash
python scripts/check_api_deployment.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "$LIVEPORTRAIT_API_KEY"
```

Pass/Fail Criteria:

- Pass: health, frontend, auth guard, recent jobs, audit, and audit export
  checks all report `OK`.
- Fail: any endpoint is unavailable or protected endpoints do not require
  `x-api-key`.

### 6. Real Smoke Job

Run one real Humans mode job:

```bash
python scripts/smoke_api_job.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "$LIVEPORTRAIT_API_KEY" \
  --source assets/examples/source/s9.jpg \
  --driving assets/examples/driving/d12.jpg \
  --output tmp/api-smoke-result.jpg
```

Pass/Fail Criteria:

- Pass: job reaches `succeeded`, result downloads, and the job has
  `output_sha256`.
- Fail: upload is rejected, job stays pending/running past the timeout, job
  fails, result download fails, or `output_sha256` is missing.

### 7. Audit And Support Export

After the smoke job succeeds:

- [ ] `GET /api/jobs/{job_id}` returns `succeeded`.
- [ ] `GET /api/jobs/{job_id}/audit` returns `created`, `running`, and
  `succeeded` events.
- [ ] `GET /api/jobs/{job_id}/export` downloads a JSON support package.
- [ ] Export includes source hash, driving hash, output hash, consent flag, and
  policy version.

Pass/Fail Criteria:

- Pass: the export can support a future customer-support investigation.
- Fail: audit events or hashes are missing.

### 8. Cleanup Evidence

Run cleanup dry-run:

```bash
python scripts/cleanup_api_jobs.py --older-than-days 7 --dry-run
```

Confirm:

- [ ] Script prints `record=<...cleanup-runs.jsonl>`.
- [ ] `<LIVEPORTRAIT_API_DATA_DIR>/cleanup-runs.jsonl` exists.
- [ ] The newest JSON line records `dry_run=true`.

Pass/Fail Criteria:

- Pass: cleanup evidence is written without deleting active jobs.
- Fail: no cleanup record is produced.

## Evidence To Record

Fill this table for each deployment acceptance run.

| Item | Value |
| --- | --- |
| Date/time | |
| Operator | |
| Machine/provider | |
| GPU model | |
| Branch | |
| Commit | |
| Python version | |
| Torch version | |
| CUDA available | |
| API base URL | |
| Data directory | |
| Max upload bytes | |
| Max active jobs | |
| Deployment check result | |
| Smoke job ID | |
| Smoke job status | |
| Result path | |
| output_sha256 | |
| Audit export saved | |
| Cleanup record path | |
| Final decision | Accepted / Rejected |

## Rollback

Use rollback when any acceptance stage fails after the service has already been
shared.

1. Stop the service or remove public access.
2. Rotate `LIVEPORTRAIT_API_KEY` if it was exposed.
3. Preserve service logs, job exports, and `cleanup-runs.jsonl`.
4. Record the failing stage and exact command output.
5. Return to the previous accepted commit or keep the service offline until the
   failure is fixed and this checklist passes again.

## Acceptance Decision

Accept the deployment only when:

- Commercial safety scan passes.
- GPU runtime is confirmed.
- API Key protection is confirmed.
- Frontend loads.
- Real smoke job succeeds.
- Result download succeeds.
- Audit export includes hashes and authorization metadata.
- Cleanup dry-run writes a cleanup record.

Reject the deployment if any item above fails.
