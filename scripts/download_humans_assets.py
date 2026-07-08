# coding: utf-8

import argparse
import sys
import urllib.request
from pathlib import Path
from typing import Sequence

try:
    from huggingface_hub import snapshot_download
except ModuleNotFoundError:  # pragma: no cover - exercised on fresh machines
    snapshot_download = None


DEFAULT_REPO_ID = "KlingTeam/LivePortrait"
HUMANS_ALLOW_PATTERNS = ["liveportrait/*"]
HUMANS_IGNORE_PATTERNS = [
    "*.git*",
    "README.md",
    "docs/*",
    "insightface/*",
    "liveportrait_animals/*",
]
MEDIAPIPE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
)
MEDIAPIPE_MODEL_RELATIVE_PATH = Path("pretrained_weights") / "mediapipe" / "blaze_face_short_range.tflite"


def download_humans_assets(
    repo_root: Path,
    repo_id: str = DEFAULT_REPO_ID,
    force_mediapipe: bool = False,
) -> None:
    repo_root = repo_root.resolve()
    weights_dir = repo_root / "pretrained_weights"
    _assert_no_legacy_detector_dir(weights_dir)
    _download_humans_weights(repo_id=repo_id, local_dir=weights_dir)
    _download_file(
        MEDIAPIPE_MODEL_URL,
        repo_root / MEDIAPIPE_MODEL_RELATIVE_PATH,
        force=force_mediapipe,
    )
    _assert_no_legacy_detector_dir(weights_dir)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download commercial-safe Humans mode assets for GPU regression."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID, help="Hugging Face model repository.")
    parser.add_argument(
        "--force-mediapipe",
        action="store_true",
        help="Re-download the MediaPipe face detector model even if it already exists.",
    )
    args = parser.parse_args(argv)

    try:
        download_humans_assets(
            repo_root=args.repo_root,
            repo_id=args.repo_id,
            force_mediapipe=args.force_mediapipe,
        )
    except Exception as exc:
        print(f"Asset download failed: {exc}", file=sys.stderr)
        return 1

    print("Humans mode assets are ready.")
    return 0


def _download_humans_weights(repo_id: str, local_dir: Path) -> None:
    if snapshot_download is None:
        raise RuntimeError("Install huggingface_hub before downloading LivePortrait weights.")

    snapshot_download(
        repo_id=repo_id,
        repo_type="model",
        local_dir=str(local_dir),
        allow_patterns=HUMANS_ALLOW_PATTERNS,
        ignore_patterns=HUMANS_IGNORE_PATTERNS,
    )


def _download_file(url: str, destination: Path, force: bool = False) -> None:
    if destination.exists() and not force:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    urllib.request.urlretrieve(url, tmp_path)
    tmp_path.replace(destination)


def _assert_no_legacy_detector_dir(weights_dir: Path) -> None:
    legacy_dir = weights_dir / ("insight" + "face")
    if legacy_dir.exists():
        raise RuntimeError(
            "Commercial-safe assets cannot include the legacy detector directory. "
            f"Remove {legacy_dir} before continuing."
        )


if __name__ == "__main__":
    raise SystemExit(main())

