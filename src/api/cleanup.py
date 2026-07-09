# coding: utf-8

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .storage import PENDING, RUNNING, JobRecord, JobStore


@dataclass(frozen=True)
class CleanupResult:
    matched_jobs: int
    deleted_jobs: int
    skipped_active_jobs: int
    removed_bytes: int
    matched_job_ids: tuple[str, ...] = ()
    deleted_job_ids: tuple[str, ...] = ()
    cleanup_record_path: Path | None = None


def cleanup_finished_jobs(
    store: JobStore,
    jobs_dir: Path,
    older_than_days: int,
    now: datetime | None = None,
    dry_run: bool = False,
    cleanup_record_path: Path | None = None,
) -> CleanupResult:
    if older_than_days < 1:
        raise ValueError("older_than_days must be at least 1")

    current_time = now or datetime.now(timezone.utc)
    cutoff = (current_time - timedelta(days=older_than_days)).isoformat()
    matched_jobs = store.list_terminal_jobs_before(cutoff)
    active_jobs = [
        job
        for job in store.list_jobs()
        if job.status in {PENDING, RUNNING} and job.updated_at < cutoff
    ]

    deleted_jobs = 0
    removed_bytes = 0
    deleted_job_ids = []
    for job in matched_jobs:
        job_dir = _job_directory(job)
        if job_dir is not None and _is_relative_to(job_dir, jobs_dir):
            removed_bytes += _directory_size(job_dir)
            if not dry_run:
                shutil.rmtree(job_dir, ignore_errors=True)
        if not dry_run:
            store.delete_job(job.job_id)
            deleted_jobs += 1
            deleted_job_ids.append(job.job_id)

    result = CleanupResult(
        matched_jobs=len(matched_jobs),
        deleted_jobs=deleted_jobs,
        skipped_active_jobs=len(active_jobs),
        removed_bytes=removed_bytes,
        matched_job_ids=tuple(job.job_id for job in matched_jobs),
        deleted_job_ids=tuple(deleted_job_ids),
        cleanup_record_path=cleanup_record_path,
    )
    if cleanup_record_path is not None:
        _write_cleanup_record(
            cleanup_record_path,
            result,
            older_than_days=older_than_days,
            dry_run=dry_run,
            created_at=current_time.isoformat(),
        )
    return result


def _job_directory(job: JobRecord) -> Path | None:
    if job.output_dir.name == "outputs":
        return job.output_dir.parent
    if job.source_path.parent.name == "uploads":
        return job.source_path.parent.parent
    return None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _write_cleanup_record(
    record_path: Path,
    result: CleanupResult,
    older_than_days: int,
    dry_run: bool,
    created_at: str,
) -> None:
    record_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": created_at,
        "older_than_days": older_than_days,
        "dry_run": dry_run,
        "matched_jobs": result.matched_jobs,
        "deleted_jobs": result.deleted_jobs,
        "skipped_active_jobs": result.skipped_active_jobs,
        "removed_bytes": result.removed_bytes,
        "matched_job_ids": list(result.matched_job_ids),
        "deleted_job_ids": list(result.deleted_job_ids),
    }
    with record_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
