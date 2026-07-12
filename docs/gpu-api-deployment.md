# GPU API Deployment

This guide starts the commercial-safe Humans mode API and the minimal frontend
on a Linux GPU cloud machine.

The frontend is served by the same FastAPI service. After the server starts,
open:

```text
http://<server-ip>:8000/
```

## 1. Prepare The Machine

Use an NVIDIA GPU machine with a working driver. Confirm the GPU is visible:

```bash
nvidia-smi
```

Clone this repository and enter the project directory:

```bash
git clone https://github.com/wzqgxlz/LivePortrait-commercial.git
cd LivePortrait-commercial
git checkout codex/commercial-mediapipe-cropper
```

Create and activate a Python environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install PyTorch for the CUDA version supported by the rented GPU image, then
install the project requirements. Example:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
pip install huggingface_hub
```

If the cloud image already includes PyTorch, check it first:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## 2. Download Commercial-Safe Assets

Download Humans mode weights and the MediaPipe detector model:

```bash
python scripts/download_humans_assets.py
```

Run the commercial safety scan:

```bash
python scripts/commercial_safety_scan.py
```

The deployment must not contain `pretrained_weights/insightface`.

## 3. Verify Before Serving

Run the focused API and deployment checks:

```bash
python scripts/check_deployment_preflight.py --skip-gpu --allow-missing-api-key
python -m pytest tests/test_api_service.py tests/test_api_cleanup.py tests/test_deployment_scripts.py -q
```

Before exposing the service on a GPU machine, run the strict preflight with the
real deployment environment variables set:

```bash
export LIVEPORTRAIT_API_KEY="replace-with-a-long-random-secret"
python scripts/check_deployment_preflight.py
```

The preflight checks Python version, required repository files, Humans mode
weights, the MediaPipe detector model, blocked commercial-risk paths, the
commercial safety scan, API environment values, Python package imports, and CUDA
availability through PyTorch. Use `--skip-gpu` only on non-GPU machines.

For a GPU regression pass, run:

```bash
python scripts/run_humans_regression.py --python python
```

## 4. Start API And Frontend

Set deployment environment variables:

```bash
export LIVEPORTRAIT_API_KEY="replace-with-a-long-random-secret"
export LIVEPORTRAIT_API_HOST="0.0.0.0"
export LIVEPORTRAIT_API_PORT="8000"
export LIVEPORTRAIT_API_DATA_DIR="tmp/api"
export LIVEPORTRAIT_API_PYTHON="python"
export LIVEPORTRAIT_API_FORCE_CPU="0"
export LIVEPORTRAIT_API_MAX_UPLOAD_BYTES="209715200"
export LIVEPORTRAIT_API_MAX_ACTIVE_JOBS="20"
export LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER="3"
export LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB="2"
```

You can also start from the template:

```bash
sudo mkdir -p /etc/liveportrait
sudo cp deploy/liveportrait-api.env.example /etc/liveportrait/liveportrait-api.env
sudo nano /etc/liveportrait/liveportrait-api.env
```

Start the service:

```bash
bash scripts/start_gpu_api_server.sh
```

The same service exposes:

- Frontend: `http://<server-ip>:8000/`
- Health check: `http://<server-ip>:8000/api/health`
- API job endpoint: `POST http://<server-ip>:8000/api/jobs`

`LIVEPORTRAIT_API_KEY` is the bootstrap administrator Key. Keep it in server
configuration and do not give it to end users. Use it to issue personal Keys
through `POST /api/admin/api-keys`; personal Keys can create and view only their
own jobs. The frontend keeps a personal Key only for the current browser session
and sends it as `x-api-key` for job creation, status polling, and result download.

Keep `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS` conservative until the GPU has passed
load testing. It counts jobs that are still `pending` or `running` and rejects
new uploads with `429` when the queue is full. The default upload limit is
200 MB per file. `LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER` separately limits
each personal Key owner; the default is three active jobs.

After a service restart, jobs that were still `pending` are safely requeued.
Jobs that had already reached `running` are marked `failed` with an interruption
audit event and require an explicit retry, preventing an unobserved duplicate
generation. The default `LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB=2` permits two
retries after the initial execution attempt.

## 5. Put HTTPS In Front

For any external tester or customer, keep the FastAPI service behind a reverse
proxy and expose the HTTPS domain, not the raw `:8000` service. The API can keep
listening on `127.0.0.1:8000` or an internal network address while Nginx/Caddy
handles TLS, upload size limits, request timeouts, and access logs.

Example public URL:

```text
https://liveportrait.example.com/
```

Nginx template:

```bash
sudo cp deploy/nginx-liveportrait-api.conf /etc/nginx/sites-available/liveportrait-api.conf
sudo ln -s /etc/nginx/sites-available/liveportrait-api.conf /etc/nginx/sites-enabled/liveportrait-api.conf
sudo nginx -t
sudo systemctl reload nginx
```

Before enabling it, replace `liveportrait.example.com` and the certificate paths
in `deploy/nginx-liveportrait-api.conf`. The template sets `client_max_body_size
220m`, which should stay above `LIVEPORTRAIT_API_MAX_UPLOAD_BYTES=209715200`.
It also sets long proxy timeouts because video generation can take longer than
typical web requests.

Caddy template:

```bash
sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy can issue and renew certificates automatically when the domain points to
the server and ports `80` and `443` are open.

## 6. Check Deployment

After startup, run a non-inference deployment check:

```bash
python scripts/check_api_deployment.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "$LIVEPORTRAIT_API_KEY"
```

This checks:

- `GET /api/health`
- the frontend HTML page
- that job endpoints reject requests without `x-api-key`
- that the recent job list rejects requests without `x-api-key`
- that the audit endpoint rejects requests without `x-api-key`
- that the audit export endpoint rejects requests without `x-api-key`
- that the operations audit export endpoint rejects requests without `x-api-key`
- that the configured API Key reaches the job endpoint

When HTTPS is configured, rerun the check against the public domain:

```bash
python scripts/check_api_deployment.py \
  --base-url https://liveportrait.example.com \
  --api-key "$LIVEPORTRAIT_API_KEY"
```

## 7. Run A Real Smoke Job

After the lightweight deployment check passes, submit one real Humans mode job:

```bash
python scripts/smoke_api_job.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "$LIVEPORTRAIT_API_KEY" \
  --source assets/examples/source/s9.jpg \
  --driving assets/examples/driving/d12.jpg \
  --output tmp/api-smoke-result.jpg
```

This uploads the source and driving files through the API, polls until the job
finishes, and downloads the generated result. The script submits
`consent_confirmed=true`, matching the frontend authorization checkbox.

Successful jobs record `output_sha256` and audit events for later traceability.
Use `GET /api/jobs/{job_id}/export` or the frontend `Download audit JSON`
action to download the complete traceability package.

For a formal handoff, complete `docs/deployment-acceptance-checklist.md`. Pick
either the systemd or Docker Compose path first, then record the deployment
mode, smoke job ID, result path, `output_sha256`, and the selected runtime's
status/log evidence. Do not run both service modes on port `8000`.

## 8. Run With systemd

Install the service template after you have copied the repository to
`/opt/liveportrait` and created `/etc/liveportrait/liveportrait-api.env`:

```bash
sudo cp deploy/liveportrait-api.service /etc/systemd/system/liveportrait-api.service
sudo systemctl daemon-reload
sudo systemctl enable liveportrait-api
sudo systemctl start liveportrait-api
sudo systemctl status liveportrait-api
```

View logs:

```bash
journalctl -u liveportrait-api -f
```

## 9. Run With Docker Compose

The repository also includes a minimal GPU container deployment:

- `deploy/Dockerfile.api`
- `deploy/docker-compose.gpu.yml`
- `.dockerignore`

The image does not copy local `pretrained_weights`, `tmp`, `output`, or local
virtual environments into the build context. Runtime data is mounted from the
host so model files and API job data survive container rebuilds.

Set an API Key:

```bash
export LIVEPORTRAIT_API_KEY="replace-with-a-long-random-secret"
```

Build the image:

```bash
docker compose -f deploy/docker-compose.gpu.yml build
```

Download Humans assets into the mounted `pretrained_weights` directory:

```bash
docker compose -f deploy/docker-compose.gpu.yml run --rm api \
  python3 scripts/download_humans_assets.py
```

Run the commercial safety scan inside the container:

```bash
docker compose -f deploy/docker-compose.gpu.yml run --rm api \
  python3 scripts/commercial_safety_scan.py
```

Start the API and frontend:

```bash
docker compose -f deploy/docker-compose.gpu.yml up -d --build
```

Follow logs:

```bash
docker compose -f deploy/docker-compose.gpu.yml logs -f api
```

Then run the same deployment check from the host:

```bash
python scripts/check_api_deployment.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "$LIVEPORTRAIT_API_KEY"
```

The Compose file requests one NVIDIA GPU and mounts:

- `../pretrained_weights` to `/app/pretrained_weights`
- `../tmp/api` to `/app/tmp/api`

Use the systemd flow or the Docker Compose flow, not both on the same port.

## 10. Clean Old Jobs

Preview cleanup:

```bash
python scripts/cleanup_api_jobs.py --older-than-days 7 --dry-run
```

Delete old finished jobs:

```bash
python scripts/cleanup_api_jobs.py --older-than-days 7
```

Only `succeeded` and `failed` jobs older than the retention window are removed.
`pending` and `running` jobs are kept.

Each cleanup run appends an operational record to:

```text
<LIVEPORTRAIT_API_DATA_DIR>/cleanup-runs.jsonl
```

Keep this file with the API data directory if you need retention and deletion
evidence for customer support or internal audits.

## 11. Production Notes

- Put the service behind HTTPS before public access.
- Keep `LIVEPORTRAIT_API_KEY` secret and rotate it when sharing access changes.
- Restrict firewall rules to the ports you need.
- Use a process manager such as systemd, supervisor, or the cloud platform's
  service runner for long-running deployment.
- Keep GPU concurrency low until real load testing confirms safe memory usage.
- Use `GET /api/jobs?status=failed` for failure triage and
  `GET /api/jobs/{job_id}/export` for per-job support exports.
