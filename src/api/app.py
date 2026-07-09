# coding: utf-8

import shutil
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Dict

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.utils.commercial_safety import assert_commercial_safe_environment

from .config import ApiConfig
from .runner import InferenceRunner
from .storage import DEFAULT_USAGE_POLICY_VERSION, JobRecord, JobStore, PENDING, SUCCEEDED


SOURCE_CONTENT_TYPES = {
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png": {"image/png"},
}
DRIVING_CONTENT_TYPES = {
    **SOURCE_CONTENT_TYPES,
    ".mp4": {"video/mp4"},
    ".pkl": {"application/octet-stream", "application/pickle", "application/x-pickle"},
}
STATIC_DIR = Path(__file__).with_name("static")


def create_app(
    config: ApiConfig | None = None,
    enqueue_jobs: bool = True,
    run_startup_checks: bool = True,
) -> FastAPI:
    cfg = config or ApiConfig.from_env()
    store = JobStore(cfg.db_path)
    runner = InferenceRunner(cfg)
    queue: Queue[str] = Queue()
    app = FastAPI(title="LivePortrait Commercial API", version="0.1.0")
    app.state.config = cfg
    app.state.job_store = store
    app.state.runner = runner
    app.state.job_queue = queue

    if run_startup_checks:
        assert_commercial_safe_environment(cfg.repo_root)

    def require_api_key(x_api_key: str | None = Header(default=None, alias="x-api-key")) -> None:
        if cfg.api_key is None:
            return
        if x_api_key is None or not secrets.compare_digest(x_api_key, cfg.api_key):
            raise HTTPException(status_code=401, detail="invalid API key")

    if enqueue_jobs:
        worker = threading.Thread(target=_worker_loop, args=(queue, store, runner), daemon=True)
        worker.start()
        app.state.worker = worker

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def frontend():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health() -> Dict[str, object]:
        return {
            "status": "ok",
            "max_upload_bytes": cfg.max_upload_bytes,
            "max_active_jobs": cfg.max_active_jobs,
        }

    @app.post("/api/jobs", status_code=201)
    def create_job(
        source: UploadFile = File(...),
        driving: UploadFile = File(...),
        consent_confirmed: bool = Form(False),
        _: None = Depends(require_api_key),
    ) -> Dict[str, object]:
        _validate_consent(consent_confirmed)
        _validate_upload(source, SOURCE_CONTENT_TYPES, "source")
        _validate_upload(driving, DRIVING_CONTENT_TYPES, "driving")
        _validate_capacity(store, cfg.max_active_jobs)

        job_id = _new_job_id_hint()
        job_dir = cfg.jobs_dir / job_id
        upload_dir = job_dir / "uploads"
        output_dir = job_dir / "outputs"
        upload_dir.mkdir(parents=True, exist_ok=True)
        source_path = upload_dir / _safe_filename(source.filename)
        driving_path = upload_dir / _safe_filename(driving.filename)
        _save_upload(source, source_path, cfg.max_upload_bytes)
        _save_upload(driving, driving_path, cfg.max_upload_bytes)

        job = store.create_job(
            source_filename=source.filename or source_path.name,
            driving_filename=driving.filename or driving_path.name,
            source_path=source_path,
            driving_path=driving_path,
            output_dir=output_dir,
            job_id=job_id,
            consent_confirmed=consent_confirmed,
            usage_policy_version=DEFAULT_USAGE_POLICY_VERSION,
        )
        if enqueue_jobs:
            queue.put(job.job_id)
        return _job_payload(job)

    @app.get("/api/jobs")
    def list_jobs(
        limit: int = Query(20, ge=1, le=100),
        _: None = Depends(require_api_key),
    ) -> Dict[str, object]:
        return {"jobs": [_job_payload(job) for job in store.list_recent_jobs(limit=limit)]}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, _: None = Depends(require_api_key)) -> Dict[str, object]:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_payload(job)

    @app.get("/api/jobs/{job_id}/result")
    def get_result(job_id: str, _: None = Depends(require_api_key)):
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job.status != SUCCEEDED or job.result_path is None:
            raise HTTPException(status_code=409, detail=f"job is {job.status}")
        if not job.result_path.exists():
            raise HTTPException(status_code=404, detail="result file not found")
        return FileResponse(job.result_path)

    @app.get("/api/jobs/{job_id}/audit")
    def get_job_audit(job_id: str, _: None = Depends(require_api_key)) -> Dict[str, object]:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        events = store.list_audit_events(job_id)
        return {
            "job_id": job_id,
            "events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "metadata": event.metadata,
                    "created_at": event.created_at,
                }
                for event in events
            ],
        }

    @app.get("/api/jobs/{job_id}/export")
    def export_job_audit(job_id: str, _: None = Depends(require_api_key)) -> JSONResponse:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        events = store.list_audit_events(job_id)
        payload = {
            "export_version": "liveportrait-audit-export-v1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "job": _job_payload(job),
            "audit_events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "metadata": event.metadata,
                    "created_at": event.created_at,
                }
                for event in events
            ],
        }
        return JSONResponse(
            payload,
            headers={
                "Content-Disposition": f'attachment; filename="liveportrait-audit-{job_id}.json"'
            },
        )

    return app


def _worker_loop(queue: Queue[str], store: JobStore, runner: InferenceRunner) -> None:
    while True:
        job_id = queue.get()
        try:
            runner.run_job(store, job_id)
        finally:
            queue.task_done()


def _validate_upload(
    upload: UploadFile,
    allowed_content_types: dict[str, set[str]],
    field_name: str,
) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} file type is not supported: {suffix or '(none)'}",
        )
    content_type = _normalized_content_type(upload.content_type)
    if content_type not in allowed_content_types[suffix]:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} content type is not supported: {content_type}",
        )


def _validate_capacity(store: JobStore, max_active_jobs: int) -> None:
    if max_active_jobs <= 0:
        return
    if store.count_active_jobs() >= max_active_jobs:
        raise HTTPException(
            status_code=429,
            detail="job queue is full; retry after existing jobs finish",
        )


def _validate_consent(consent_confirmed: bool) -> None:
    if not consent_confirmed:
        raise HTTPException(
            status_code=400,
            detail="source image authorization must be confirmed before creating a job",
        )


def _normalized_content_type(content_type: str | None) -> str:
    value = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    return value or "application/octet-stream"


def _save_upload(upload: UploadFile, destination: Path, max_upload_bytes: int) -> None:
    total = 0
    with destination.open("wb") as handle:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_upload_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="uploaded file is too large")
            handle.write(chunk)


def _job_payload(job: JobRecord) -> Dict[str, object]:
    payload = {
        "job_id": job.job_id,
        "status": job.status,
        "source_filename": job.source_filename,
        "driving_filename": job.driving_filename,
        "source_sha256": job.source_sha256,
        "driving_sha256": job.driving_sha256,
        "output_sha256": job.output_sha256,
        "consent_confirmed": job.consent_confirmed,
        "usage_policy_version": job.usage_policy_version,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if job.result_path is not None:
        payload["result_path"] = str(job.result_path)
    if job.error_message:
        payload["error_message"] = job.error_message
    return payload


def _safe_filename(filename: str | None) -> str:
    name = Path(filename or "upload").name
    if not name or name in {".", ".."}:
        return "upload"
    return name


def _new_job_id_hint() -> str:
    # The final job id is created by JobStore; this only keeps uploaded files isolated
    # before the row is inserted.
    import uuid

    return uuid.uuid4().hex


app = create_app()
