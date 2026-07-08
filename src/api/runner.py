# coding: utf-8

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from .config import ApiConfig
from .storage import JobRecord, JobStore


class InferenceRunner:
    def __init__(self, config: ApiConfig):
        self.config = config

    def build_command(self, source_path: Path, driving_path: Path, output_dir: Path) -> List[str]:
        command = [
            self.config.python_executable,
            "inference.py",
            "-s",
            str(source_path),
            "-d",
            str(driving_path),
            "-o",
            str(output_dir),
        ]
        if self.config.force_cpu:
            command.extend(["--flag-force-cpu", "--no-flag-use-half-precision"])
        return command

    def run_job(self, store: JobStore, job_id: str) -> None:
        job = store.get_job(job_id)
        if job is None:
            return

        store.mark_running(job_id)
        job.output_dir.mkdir(parents=True, exist_ok=True)
        command = self.build_command(job.source_path, job.driving_path, job.output_dir)
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        completed = subprocess.run(
            command,
            cwd=str(self.config.repo_root),
            env=env,
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            store.mark_failed(job_id, (completed.stderr or completed.stdout or "inference failed")[-4000:])
            return

        result_path = find_result_file(job.output_dir)
        if result_path is None:
            store.mark_failed(job_id, "inference completed but no result file was found")
            return

        store.mark_succeeded(job_id, result_path)


def find_result_file(output_dir: Path) -> Optional[Path]:
    candidates = []
    for pattern in ("*.mp4", "*.jpg", "*.png"):
        candidates.extend(path for path in output_dir.glob(pattern) if "_concat" not in path.stem)
    if not candidates:
        candidates = list(output_dir.glob("*.mp4")) + list(output_dir.glob("*.jpg")) + list(output_dir.glob("*.png"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)

