# GPU Machine Quickstart

This is the shortest command checklist for validating the commercial-safe
Humans mode API on a rented NVIDIA GPU machine. Use it before the full
deployment acceptance checklist.

Animals mode is out of scope.

## 1. Confirm GPU Runtime

```bash
nvidia-smi
```

The command must show the rented NVIDIA GPU and driver. If it does not, fix the
cloud image or driver before continuing.

## 2. Clone The Project

```bash
git clone https://github.com/wzqgxlz/LivePortrait-commercial.git
cd LivePortrait-commercial
git checkout codex/commercial-mediapipe-cropper
git log -1 --oneline
```

Record the commit hash shown by `git log -1 --oneline`.

## 3. Create Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

If the cloud image already has PyTorch installed, check it first:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Install PyTorch for the CUDA version supported by the machine image, then install
the project requirements. Example for CUDA 12.8 wheels:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
pip install huggingface_hub
```

Check CUDA again:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

`torch.cuda.is_available()` must print `True` on the GPU machine.

## 4. Download Humans Mode Assets

```bash
python scripts/download_humans_assets.py
```

This downloads the Humans mode weights and MediaPipe detector asset required by
the commercial-safe detection path.

## 5. Set API Environment

```bash
export LIVEPORTRAIT_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export LIVEPORTRAIT_API_HOST=0.0.0.0
export LIVEPORTRAIT_API_PORT=8000
export LIVEPORTRAIT_API_DATA_DIR=tmp/api
export LIVEPORTRAIT_API_PYTHON=python
export LIVEPORTRAIT_API_FORCE_CPU=0
export LIVEPORTRAIT_API_MAX_UPLOAD_BYTES=209715200
export LIVEPORTRAIT_API_MAX_ACTIVE_JOBS=20
export LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER=3
export LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB=2
```

Keep the generated `LIVEPORTRAIT_API_KEY` private. Do not paste it into shared
logs, screenshots, or support notes.

## 6. Run Strict Preflight

```bash
python scripts/check_deployment_preflight.py
```

The strict preflight must pass on the GPU machine. It checks repository files,
commercial-safety guardrails, Humans mode assets, MediaPipe assets, required
Python imports, API environment, and CUDA availability.

## 7. Start The API

```bash
bash scripts/start_gpu_api_server.sh
```

Keep this terminal open for the first validation run. The API and frontend will
listen on port `8000`.

## 8. Validate From Another Terminal

Open a second terminal on the same machine:

```bash
cd LivePortrait-commercial
source .venv/bin/activate

curl -s http://127.0.0.1:8000/api/health
python scripts/check_api_deployment.py --base-url http://127.0.0.1:8000 --api-key "$LIVEPORTRAIT_API_KEY"
python scripts/smoke_api_job.py --base-url http://127.0.0.1:8000 --api-key "$LIVEPORTRAIT_API_KEY" --source assets/examples/source/s9.jpg --driving assets/examples/driving/d12.jpg --output tmp/api-smoke-result.jpg
```

The smoke job must end as `succeeded` and download `tmp/api-smoke-result.jpg`.

## 9. Validate The Browser UI

Open:

```text
http://<server-ip>:8000/
```

Use the bootstrap admin key from `LIVEPORTRAIT_API_KEY`, issue a personal user
key from the Access management panel, then test one upload with the personal
key.

## 10. Move To Acceptance

After this quickstart passes, run the full acceptance flow:

```text
docs/deployment-acceptance-checklist.md
```

For a long-running service, switch from the direct shell command to either:

```text
deploy/liveportrait-api.service
deploy/docker-compose.gpu.yml
```

For public access, put HTTPS in front of the API using:

```text
deploy/nginx-liveportrait-api.conf
deploy/Caddyfile.example
```

## Common Failures

| Symptom | Likely Cause | Action |
| --- | --- | --- |
| `nvidia-smi` fails | GPU driver or cloud image is not ready. | Rebuild the GPU instance or choose a GPU image with NVIDIA driver support. |
| `torch.cuda.is_available()` is `False` | PyTorch wheel does not match the machine CUDA/driver setup. | Install a compatible PyTorch CUDA wheel, then rerun preflight. |
| Humans assets are missing | Model files were not downloaded. | Run `python scripts/download_humans_assets.py` again. |
| Preflight blocks InsightFace paths | Unsafe old assets or vendored code are present. | Remove blocked InsightFace directories before deployment. |
| API returns `401` | API Key is missing or incorrect. | Send the correct `x-api-key` header or paste the correct Key in the browser. |
| Upload returns `413` | Upload exceeds API or reverse proxy limit. | Check `LIVEPORTRAIT_API_MAX_UPLOAD_BYTES` and proxy upload limits. |
| Job fails with CUDA out-of-memory | Too many concurrent jobs for the GPU memory. | Lower `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS` and `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER`. |
