# coding: utf-8

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.cleanup import cleanup_finished_jobs
from src.api.config import ApiConfig
from src.api.storage import JobStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean old completed LivePortrait API jobs.")
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=7,
        help="Delete succeeded/failed jobs older than this many days. Default: 7.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without deleting files or database rows.",
    )
    args = parser.parse_args()

    config = ApiConfig.from_env()
    store = JobStore(config.db_path)
    result = cleanup_finished_jobs(
        store=store,
        jobs_dir=config.jobs_dir,
        older_than_days=args.older_than_days,
        dry_run=args.dry_run,
        cleanup_record_path=config.resolved_data_dir / "cleanup-runs.jsonl",
    )
    mode = "DRY RUN" if args.dry_run else "CLEANED"
    print(
        f"{mode}: matched={result.matched_jobs} "
        f"deleted={result.deleted_jobs} "
        f"skipped_active={result.skipped_active_jobs} "
        f"removed_bytes={result.removed_bytes} "
        f"operational_audit_matched={result.operational_audit_matched_events} "
        f"operational_audit_deleted={result.operational_audit_deleted_events} "
        f"record={result.cleanup_record_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
