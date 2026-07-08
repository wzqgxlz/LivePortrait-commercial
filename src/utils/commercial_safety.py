# coding: utf-8

from pathlib import Path


def assert_commercial_safe_environment(repo_root=None):
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    legacy_weight_dir = root / "pretrained_weights" / ("insight" + "face")
    if legacy_weight_dir.exists():
        raise RuntimeError(
            "This commercial-safe build cannot run with legacy InsightFace weights present. "
            f"Remove {legacy_weight_dir} before starting."
        )

