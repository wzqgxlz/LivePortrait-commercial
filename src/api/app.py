# coding: utf-8

import shutil
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Dict

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.utils.commercial_safety import assert_commercial_safe_environment

from .cleanup import CleanupResult, cleanup_finished_jobs, list_cleanup_records
from .config import ApiConfig
from .runner import InferenceRunner
from .storage import (
    DEFAULT_AUTHORIZATION_STATUS,
    DEFAULT_USAGE_POLICY_VERSION,
    FAILED,
    PENDING,
    RUNNING,
    SUCCEEDED,
    ApiKeyRecord,
    JobRecord,
    JobStore,
)


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
VALID_JOB_STATUSES = {PENDING, RUNNING, SUCCEEDED, FAILED}
VALID_AUTHORIZATION_STATUSES = {"self_confirmed", "approved", "needs_review"}
VALID_API_KEY_ROLES = {"user", "admin"}
RESERVED_OWNER_IDS = {"bootstrap-admin", "local-development"}


@dataclass(frozen=True)
class Principal:
    owner_id: str
    role: str
    key_id: str | None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


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

    def require_principal(
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
    ) -> Principal:
        if x_api_key and cfg.api_key and secrets.compare_digest(x_api_key, cfg.api_key):
            return Principal(owner_id="bootstrap-admin", role="admin", key_id=None)
        if x_api_key:
            record = store.get_active_api_key(x_api_key)
            if record is not None:
                return Principal(owner_id=record.owner_id, role=record.role, key_id=record.key_id)
        if cfg.api_key is None and not store.has_api_keys():
            # Preserve the intentionally open local-development mode until the
            # first managed key is issued.
            return Principal(owner_id="local-development", role="admin", key_id=None)
        raise HTTPException(status_code=401, detail="invalid API key")

    def require_admin(principal: Principal = Depends(require_principal)) -> Principal:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="administrator API key is required")
        return principal

    startup_recovery = {"requeued_job_ids": [], "interrupted_job_ids": []}
    if enqueue_jobs:
        startup_recovery = store.recover_incomplete_jobs()
        worker = threading.Thread(target=_worker_loop, args=(queue, store, runner), daemon=True)
        worker.start()
        app.state.worker = worker
        for job_id in startup_recovery["requeued_job_ids"]:
            queue.put(job_id)
    app.state.startup_recovery = startup_recovery

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
            "max_active_jobs_per_owner": cfg.max_active_jobs_per_owner,
            "max_retries_per_job": cfg.max_retries_per_job,
            "authentication_required": cfg.api_key is not None or store.has_api_keys(),
            "startup_recovery": {
                "requeued_jobs": len(startup_recovery["requeued_job_ids"]),
                "interrupted_jobs": len(startup_recovery["interrupted_job_ids"]),
            },
        }

    @app.get("/api/admin/api-keys")
    def list_api_keys(_: Principal = Depends(require_admin)) -> Dict[str, object]:
        return {"api_keys": [_api_key_payload(record) for record in store.list_api_keys()]}

    @app.get("/api/whoami")
    def whoami(principal: Principal = Depends(require_principal)) -> Dict[str, object]:
        return {
            "owner_id": principal.owner_id,
            "role": principal.role,
            "is_admin": principal.is_admin,
        }

    @app.post("/api/admin/api-keys", status_code=201)
    def create_api_key(
        payload: dict = Body(default_factory=dict),
        _: Principal = Depends(require_admin),
    ) -> Dict[str, object]:
        owner_id = _required_owner_id(payload.get("owner_id"))
        role = _validate_api_key_role(payload.get("role", "user"))
        label = _clean_optional_form_value(payload.get("label"))
        secret = "lp_" + secrets.token_urlsafe(32)
        record = store.create_api_key(owner_id=owner_id, role=role, label=label, secret=secret)
        response = _api_key_payload(record)
        response["api_key"] = secret
        response["secret_notice"] = "Copy this API key now. It cannot be shown again."
        return response

    @app.post("/api/admin/api-keys/{key_id}/revoke")
    def revoke_api_key(key_id: str, _: Principal = Depends(require_admin)) -> Dict[str, object]:
        record = store.revoke_api_key(key_id)
        if record is None:
            raise HTTPException(status_code=404, detail="API key not found or already revoked")
        return _api_key_payload(record)

    @app.get("/api/cleanup-runs")
    def get_cleanup_runs(
        limit: int = Query(20, ge=1, le=100),
        _: Principal = Depends(require_admin),
    ) -> Dict[str, object]:
        record_path = cfg.resolved_data_dir / "cleanup-runs.jsonl"
        return {
            "cleanup_record_path": str(record_path),
            "records": list_cleanup_records(record_path, limit=limit),
        }

    @app.post("/api/cleanup-runs", status_code=201)
    def create_cleanup_run(
        payload: dict = Body(default_factory=dict),
        _: Principal = Depends(require_admin),
    ) -> Dict[str, object]:
        older_than_days = _int_payload_value(payload, "older_than_days", default=7)
        dry_run = _bool_payload_value(payload, "dry_run", default=True)
        confirm_delete = _bool_payload_value(payload, "confirm_delete", default=False)
        if not dry_run and not confirm_delete:
            raise HTTPException(status_code=400, detail="confirm_delete=true is required before deleting jobs")
        try:
            result = cleanup_finished_jobs(
                store=store,
                jobs_dir=cfg.jobs_dir,
                older_than_days=older_than_days,
                dry_run=dry_run,
                cleanup_record_path=cfg.resolved_data_dir / "cleanup-runs.jsonl",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _cleanup_result_payload(result, older_than_days=older_than_days, dry_run=dry_run)

    @app.post("/api/jobs", status_code=201)
    def create_job(
        response: Response,
        source: UploadFile = File(...),
        driving: UploadFile = File(...),
        consent_confirmed: bool = Form(False),
        authorization_basis: str | None = Form(None),
        authorization_reference: str | None = Form(None),
        authorization_reviewer: str | None = Form(None),
        authorization_status: str = Form(DEFAULT_AUTHORIZATION_STATUS),
        x_idempotency_key: str | None = Header(default=None, alias="x-idempotency-key"),
        principal: Principal = Depends(require_principal),
    ) -> Dict[str, object]:
        idempotency_key = _validate_idempotency_key(x_idempotency_key)
        if idempotency_key is not None:
            existing_job = store.get_job_by_idempotency_key(principal.owner_id, idempotency_key)
            if existing_job is not None:
                response.status_code = 200
                return _job_payload(existing_job)
        _validate_consent(consent_confirmed)
        authorization_status = _validate_authorization_status(authorization_status)
        authorization_basis = _clean_optional_form_value(authorization_basis)
        authorization_reference = _clean_optional_form_value(authorization_reference)
        authorization_reviewer = _clean_optional_form_value(authorization_reviewer)
        _validate_upload(source, SOURCE_CONTENT_TYPES, "source")
        _validate_upload(driving, DRIVING_CONTENT_TYPES, "driving")
        _validate_capacity(
            store,
            max_active_jobs=cfg.max_active_jobs,
            max_active_jobs_per_owner=cfg.max_active_jobs_per_owner,
            owner_id=principal.owner_id,
        )

        job_id = _new_job_id_hint()
        job_dir = cfg.jobs_dir / job_id
        upload_dir = job_dir / "uploads"
        output_dir = job_dir / "outputs"
        upload_dir.mkdir(parents=True, exist_ok=True)
        source_path = upload_dir / _safe_filename(source.filename)
        driving_path = upload_dir / _safe_filename(driving.filename)
        _save_upload(source, source_path, cfg.max_upload_bytes)
        _save_upload(driving, driving_path, cfg.max_upload_bytes)

        try:
            job = store.create_job(
                source_filename=source.filename or source_path.name,
                driving_filename=driving.filename or driving_path.name,
                source_path=source_path,
                driving_path=driving_path,
                output_dir=output_dir,
                job_id=job_id,
                consent_confirmed=consent_confirmed,
                usage_policy_version=DEFAULT_USAGE_POLICY_VERSION,
                authorization_basis=authorization_basis,
                authorization_reference=authorization_reference,
                authorization_reviewer=authorization_reviewer,
                authorization_status=authorization_status,
                owner_id=principal.owner_id,
                created_by_key_id=principal.key_id,
                idempotency_key=idempotency_key,
            )
        except sqlite3.IntegrityError:
            shutil.rmtree(job_dir, ignore_errors=True)
            if idempotency_key is not None:
                existing_job = store.get_job_by_idempotency_key(principal.owner_id, idempotency_key)
                if existing_job is not None:
                    response.status_code = 200
                    return _job_payload(existing_job)
            raise
        if enqueue_jobs:
            queue.put(job.job_id)
        return _job_payload(job)

    @app.post("/api/jobs/{job_id}/retry", status_code=202)
    def retry_job(job_id: str, principal: Principal = Depends(require_principal)) -> Dict[str, object]:
        job = _get_visible_job(store, job_id, principal)
        if job.status != FAILED:
            raise HTTPException(status_code=409, detail=f"job is {job.status}; only failed jobs can be retried")
        if job.attempt_count > cfg.max_retries_per_job:
            raise HTTPException(status_code=409, detail="job retry limit is reached")
        _validate_capacity(
            store,
            max_active_jobs=cfg.max_active_jobs,
            max_active_jobs_per_owner=cfg.max_active_jobs_per_owner,
            owner_id=principal.owner_id,
        )
        retried_job = store.retry_failed_job(job_id)
        if retried_job is None:
            raise HTTPException(status_code=409, detail="job can no longer be retried")
        if enqueue_jobs:
            queue.put(retried_job.job_id)
        return _job_payload(retried_job)

    @app.get("/api/jobs")
    def list_jobs(
        limit: int = Query(20, ge=1, le=100),
        status: str | None = Query(default=None),
        authorization_reference: str | None = Query(default=None),
        authorization_status: str | None = Query(default=None),
        owner_id: str | None = Query(default=None),
        principal: Principal = Depends(require_principal),
    ) -> Dict[str, object]:
        _validate_job_status(status)
        authorization_reference = _clean_optional_form_value(authorization_reference)
        authorization_status = _validate_optional_authorization_status(authorization_status)
        requested_owner_id = _clean_optional_form_value(owner_id)
        if requested_owner_id is not None and not principal.is_admin:
            raise HTTPException(status_code=403, detail="administrator API key is required to filter by owner")
        return {
            "jobs": [
                _job_payload(job)
                for job in store.list_recent_jobs(
                    limit=limit,
                    status=status,
                    authorization_reference=authorization_reference,
                    authorization_status=authorization_status,
                    owner_id=requested_owner_id if principal.is_admin else principal.owner_id,
                )
            ]
        }

    @app.get("/api/authorization-records/export")
    def export_authorization_record(
        authorization_reference: str = Query(...),
        principal: Principal = Depends(require_principal),
    ) -> JSONResponse:
        authorization_reference = _clean_optional_form_value(authorization_reference)
        if authorization_reference is None:
            raise HTTPException(status_code=400, detail="authorization_reference is required")
        jobs = store.list_recent_jobs(
            limit=100,
            authorization_reference=authorization_reference,
            owner_id=None if principal.is_admin else principal.owner_id,
        )
        if not jobs:
            raise HTTPException(status_code=404, detail="authorization record not found")
        payload = {
            "export_version": "liveportrait-authorization-export-v1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "authorization_reference": authorization_reference,
            "jobs": [
                {
                    "job": _job_payload(job),
                    "audit_events": [
                        _audit_event_payload(event)
                        for event in store.list_audit_events(job.job_id)
                    ],
                }
                for job in jobs
            ],
        }
        filename = _safe_filename(authorization_reference).replace(" ", "_")
        return JSONResponse(
            payload,
            headers={
                "Content-Disposition": f'attachment; filename="liveportrait-authorization-{filename}.json"'
            },
        )

    @app.get("/api/jobs/{job_id}")
    def get_job(
        job_id: str,
        principal: Principal = Depends(require_principal),
    ) -> Dict[str, object]:
        job = _get_visible_job(store, job_id, principal)
        return _job_payload(job)

    @app.get("/api/jobs/{job_id}/result")
    def get_result(job_id: str, principal: Principal = Depends(require_principal)):
        job = _get_visible_job(store, job_id, principal)
        if job.status != SUCCEEDED or job.result_path is None:
            raise HTTPException(status_code=409, detail=f"job is {job.status}")
        if not job.result_path.exists():
            raise HTTPException(status_code=404, detail="result file not found")
        return FileResponse(job.result_path)

    @app.get("/api/jobs/{job_id}/audit")
    def get_job_audit(
        job_id: str,
        principal: Principal = Depends(require_principal),
    ) -> Dict[str, object]:
        job = _get_visible_job(store, job_id, principal)
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
    def export_job_audit(
        job_id: str,
        principal: Principal = Depends(require_principal),
    ) -> JSONResponse:
        job = _get_visible_job(store, job_id, principal)
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
        except Exception as exc:
            store.mark_failed(job_id, f"worker error: {type(exc).__name__}: {exc}"[:4000])
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


def _validate_capacity(
    store: JobStore,
    max_active_jobs: int,
    max_active_jobs_per_owner: int,
    owner_id: str,
) -> None:
    if max_active_jobs <= 0:
        pass
    elif store.count_active_jobs() >= max_active_jobs:
        raise HTTPException(
            status_code=429,
            detail="job queue is full; retry after existing jobs finish",
        )
    if max_active_jobs_per_owner > 0 and store.count_active_jobs(owner_id=owner_id) >= max_active_jobs_per_owner:
        raise HTTPException(
            status_code=429,
            detail="your active job limit is reached; retry after an existing job finishes",
        )


def _validate_job_status(status: str | None) -> None:
    if status is None:
        return
    if status not in VALID_JOB_STATUSES:
        raise HTTPException(status_code=400, detail=f"unsupported job status filter: {status}")


def _validate_consent(consent_confirmed: bool) -> None:
    if not consent_confirmed:
        raise HTTPException(
            status_code=400,
            detail="source image authorization must be confirmed before creating a job",
        )


def _validate_authorization_status(status: str) -> str:
    value = (status or DEFAULT_AUTHORIZATION_STATUS).strip().lower()
    if value not in VALID_AUTHORIZATION_STATUSES:
        raise HTTPException(status_code=400, detail=f"unsupported authorization status: {status}")
    return value


def _validate_optional_authorization_status(status: str | None) -> str | None:
    if status is None:
        return None
    cleaned = status.strip()
    if not cleaned:
        return None
    return _validate_authorization_status(cleaned)


def _clean_optional_form_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip()
    if not key or len(key) > 128:
        raise HTTPException(status_code=400, detail="x-idempotency-key must be 1 to 128 characters")
    return key


def _required_owner_id(value: object) -> str:
    owner_id = _clean_optional_form_value(value if isinstance(value, str) else None)
    if owner_id is None or len(owner_id) > 120:
        raise HTTPException(status_code=400, detail="owner_id is required and must be at most 120 characters")
    if owner_id in RESERVED_OWNER_IDS:
        raise HTTPException(status_code=400, detail="owner_id is reserved for system use")
    return owner_id


def _validate_api_key_role(value: object) -> str:
    role = str(value or "user").strip().lower()
    if role not in VALID_API_KEY_ROLES:
        raise HTTPException(status_code=400, detail=f"unsupported API key role: {value}")
    return role


def _int_payload_value(payload: dict, key: str, default: int) -> int:
    try:
        return int(payload.get(key, default))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{key} must be an integer") from exc


def _bool_payload_value(payload: dict, key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes"}:
            return True
        if normalized in {"0", "false", "no"}:
            return False
    return bool(value)


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
        "authorization_basis": job.authorization_basis,
        "authorization_reference": job.authorization_reference,
        "authorization_reviewer": job.authorization_reviewer,
        "authorization_status": job.authorization_status,
        "owner_id": job.owner_id,
        "idempotency_key": job.idempotency_key,
        "attempt_count": job.attempt_count,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if job.result_path is not None:
        payload["result_path"] = str(job.result_path)
    if job.error_message:
        payload["error_message"] = job.error_message
    return payload


def _api_key_payload(record: ApiKeyRecord) -> Dict[str, object]:
    return {
        "key_id": record.key_id,
        "owner_id": record.owner_id,
        "role": record.role,
        "label": record.label,
        "key_prefix": record.key_prefix,
        "status": record.status,
        "created_at": record.created_at,
        "revoked_at": record.revoked_at,
    }


def _get_visible_job(store: JobStore, job_id: str, principal: Principal) -> JobRecord:
    job = store.get_job(job_id)
    if job is None or (not principal.is_admin and job.owner_id != principal.owner_id):
        raise HTTPException(status_code=404, detail="job not found")
    return job


def _audit_event_payload(event) -> Dict[str, object]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "metadata": event.metadata,
        "created_at": event.created_at,
    }


def _cleanup_result_payload(
    result: CleanupResult,
    older_than_days: int,
    dry_run: bool,
) -> Dict[str, object]:
    return {
        "older_than_days": older_than_days,
        "dry_run": dry_run,
        "matched_jobs": result.matched_jobs,
        "deleted_jobs": result.deleted_jobs,
        "skipped_active_jobs": result.skipped_active_jobs,
        "removed_bytes": result.removed_bytes,
        "matched_job_ids": list(result.matched_job_ids),
        "deleted_job_ids": list(result.deleted_job_ids),
        "cleanup_record_path": str(result.cleanup_record_path) if result.cleanup_record_path else None,
    }


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
