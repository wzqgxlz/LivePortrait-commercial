# coding: utf-8

import shutil
import secrets
import threading
from pathlib import Path
from queue import Queue
from typing import Dict

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.utils.commercial_safety import assert_commercial_safe_environment

from .config import ApiConfig
from .runner import InferenceRunner
from .storage import JobRecord, JobStore, PENDING, SUCCEEDED


SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DRIVING_EXTENSIONS = {".jpg", ".jpeg", ".png", ".mp4", ".pkl"}


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

    @app.get("/api/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/jobs", status_code=201)
    def create_job(
        source: UploadFile = File(...),
        driving: UploadFile = File(...),
        _: None = Depends(require_api_key),
    ) -> Dict[str, str]:
        _validate_upload(source, SOURCE_EXTENSIONS, "source", cfg.max_upload_bytes)
        _validate_upload(driving, DRIVING_EXTENSIONS, "driving", cfg.max_upload_bytes)

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
        )
        if enqueue_jobs:
            queue.put(job.job_id)
        return _job_payload(job)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, _: None = Depends(require_api_key)) -> Dict[str, str]:
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

    return app


def _worker_loop(queue: Queue[str], store: JobStore, runner: InferenceRunner) -> None:
    while True:
        job_id = queue.get()
        try:
            runner.run_job(store, job_id)
        finally:
            queue.task_done()


def _validate_upload(upload: UploadFile, allowed_extensions: set[str], field_name: str, max_upload_bytes: int) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} file type is not supported: {suffix or '(none)'}",
        )


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


def _job_payload(job: JobRecord) -> Dict[str, str]:
    payload = {
        "job_id": job.job_id,
        "status": job.status,
        "source_filename": job.source_filename,
        "driving_filename": job.driving_filename,
        "source_sha256": job.source_sha256,
        "driving_sha256": job.driving_sha256,
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
