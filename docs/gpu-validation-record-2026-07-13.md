# GPU Validation Record - 2026-07-13

This record captures the first real GPU smoke validation for the
commercial-safe Humans mode API.

## Environment

- Host: rented AutoDL GPU container.
- Repository branch: `codex/commercial-mediapipe-cropper`.
- Commit validated: `20c938b docs: add gpu machine quickstart`.
- Python environment: project `.venv`.
- PyTorch check result: `2.11.0+cu128 True`.
- Product scope: Humans mode only. Animals mode remains out of scope.

## Validation Steps

1. Cloned `https://github.com/wzqgxlz/LivePortrait-commercial.git`.
2. Checked out `codex/commercial-mediapipe-cropper`.
3. Installed project dependencies in `.venv`.
4. Downloaded MediaPipe detector and LivePortrait Humans weights.
5. Set API runtime environment variables.
6. Ran deployment preflight.
7. Started the GPU API service.
8. Ran API health/auth checks.
9. Ran a real API smoke job with:
   - Source: `assets/examples/source/s9.jpg`
   - Driving: `assets/examples/driving/d12.jpg`
   - Output: `tmp/api-smoke-result.jpg`

## Issues Found And Fixes

| Issue | Symptom | Fix Added To Project |
| --- | --- | --- |
| Missing Humans weights | `models.humans_mode` failed in preflight while MediaPipe asset existed. | `scripts/download_humans_assets.py` now validates required Humans files after download and reports missing files. |
| Hugging Face access instability | Direct Humans weight download did not populate all LivePortrait model files. | GPU docs now document `HF_ENDPOINT=https://hf-mirror.com` retry flow. |
| Missing FFmpeg runtime | Smoke job failed with `FFmpeg is not installed`. | Preflight now checks `ffmpeg` and `ffprobe`; GPU docs install `ffmpeg`. |
| Missing MediaPipe shared library | Smoke job failed with `libGLESv2.so.2: cannot open shared object file`. | Preflight now checks Linux shared libraries; GPU docs and Dockerfile install `libgles2`, `libegl1`, `libgl1`, and `libglib2.0-0`. |

## Final Result

The final API smoke job succeeded and downloaded:

```text
tmp/api-smoke-result.jpg
```

Successful smoke output:

```text
Status: succeeded
Downloaded result: tmp/api-smoke-result.jpg
```

## Follow-Up

Use the hardened quickstart and preflight before the next GPU rental or
production deployment:

```bash
apt update
apt install -y ffmpeg libgles2 libegl1 libgl1 libglib2.0-0
python scripts/download_humans_assets.py
python scripts/check_deployment_preflight.py
python scripts/smoke_api_job.py --base-url http://127.0.0.1:8000 --api-key "$LIVEPORTRAIT_API_KEY" --source assets/examples/source/s9.jpg --driving assets/examples/driving/d12.jpg --output tmp/api-smoke-result.jpg
```
