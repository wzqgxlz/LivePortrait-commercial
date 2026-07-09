# coding: utf-8

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApiConfig:
    repo_root: Path = Path.cwd()
    data_dir: Path = Path("tmp") / "api"
    python_executable: str = sys.executable
    max_upload_bytes: int = 200 * 1024 * 1024
    max_active_jobs: int = 20
    force_cpu: bool = False
    api_key: str | None = None

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "ApiConfig":
        root = repo_root or Path.cwd()
        force_cpu = os.environ.get("LIVEPORTRAIT_API_FORCE_CPU", "").lower() in {"1", "true", "yes"}
        api_key = os.environ.get("LIVEPORTRAIT_API_KEY") or None
        return cls(
            repo_root=root,
            data_dir=Path(os.environ.get("LIVEPORTRAIT_API_DATA_DIR", root / "tmp" / "api")),
            python_executable=os.environ.get("LIVEPORTRAIT_API_PYTHON", sys.executable),
            max_upload_bytes=int(os.environ.get("LIVEPORTRAIT_API_MAX_UPLOAD_BYTES", 200 * 1024 * 1024)),
            max_active_jobs=int(os.environ.get("LIVEPORTRAIT_API_MAX_ACTIVE_JOBS", 20)),
            force_cpu=force_cpu,
            api_key=api_key,
        )

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir if self.data_dir.is_absolute() else self.repo_root / self.data_dir

    @property
    def db_path(self) -> Path:
        return self.resolved_data_dir / "jobs.sqlite3"

    @property
    def jobs_dir(self) -> Path:
        return self.resolved_data_dir / "jobs"
