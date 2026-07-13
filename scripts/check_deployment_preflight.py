# coding: utf-8

import argparse
import ctypes.util
import importlib
import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.commercial_safety_scan import default_scan_paths, scan_paths


REQUIRED_MODEL_FILES = (
    Path("pretrained_weights") / "liveportrait" / "landmark.onnx",
    Path("pretrained_weights") / "liveportrait" / "base_models" / "appearance_feature_extractor.pth",
    Path("pretrained_weights") / "liveportrait" / "base_models" / "motion_extractor.pth",
    Path("pretrained_weights") / "liveportrait" / "base_models" / "spade_generator.pth",
    Path("pretrained_weights") / "liveportrait" / "base_models" / "warping_module.pth",
    Path("pretrained_weights") / "liveportrait" / "retargeting_models" / "stitching_retargeting_module.pth",
    Path("pretrained_weights") / "mediapipe" / "blaze_face_short_range.tflite",
)
REQUIRED_IMPORTS = ("fastapi", "uvicorn", "numpy", "torch", "cv2", "onnxruntime", "mediapipe")
REQUIRED_SYSTEM_COMMANDS = ("ffmpeg", "ffprobe")
REQUIRED_SHARED_LIBRARIES = {
    "libGLESv2.so.2": "GLESv2",
    "libEGL.so.1": "EGL",
    "libGL.so.1": "GL",
    "libglib-2.0.so.0": "glib-2.0",
}
TEMPLATE_API_KEY = "replace-with-a-long-random-secret"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    required: bool
    message: str
    details: dict | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"pass", "skip"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LivePortrait deployment preflight checks.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root to inspect.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a human-readable report.")
    parser.add_argument("--skip-gpu", action="store_true", help="Skip CUDA/GPU availability checks.")
    parser.add_argument("--skip-imports", action="store_true", help="Skip Python package import checks.")
    parser.add_argument(
        "--skip-system-deps",
        action="store_true",
        help="Skip OS command and shared-library checks. Use only on non-deployment machines.",
    )
    parser.add_argument(
        "--allow-missing-api-key",
        action="store_true",
        help="Warn instead of failing when LIVEPORTRAIT_API_KEY is missing or still set to the template value.",
    )
    args = parser.parse_args(argv)

    results = run_preflight(
        repo_root=args.repo_root,
        skip_gpu=args.skip_gpu,
        skip_imports=args.skip_imports,
        skip_system_deps=args.skip_system_deps,
        allow_missing_api_key=args.allow_missing_api_key,
    )
    payload = {
        "status": "passed" if all(result.ok for result in results if result.required) else "failed",
        "repo_root": str(args.repo_root.resolve()),
        "checks": [result.__dict__ for result in results],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_report(payload)
    return 0 if payload["status"] == "passed" else 1


def run_preflight(
    repo_root: Path,
    skip_gpu: bool = False,
    skip_imports: bool = False,
    skip_system_deps: bool = False,
    allow_missing_api_key: bool = False,
) -> list[CheckResult]:
    repo_root = repo_root.resolve()
    results = [
        _check_python_version(),
        _check_repo_files(repo_root),
        _check_required_models(repo_root),
        _check_blocked_paths(repo_root),
        _check_commercial_safety(repo_root),
        _check_api_environment(allow_missing_api_key=allow_missing_api_key),
    ]
    results.extend(_check_system_dependencies(skip=skip_system_deps))
    results.extend(_check_imports(skip=skip_imports))
    results.append(_check_gpu(skip=skip_gpu))
    return results


def _check_python_version() -> CheckResult:
    version = sys.version_info
    ok = version >= (3, 9)
    return CheckResult(
        name="python.version",
        status="pass" if ok else "fail",
        required=True,
        message=f"Python {platform.python_version()}",
        details={"executable": sys.executable},
    )


def _check_repo_files(repo_root: Path) -> CheckResult:
    required = [
        Path("inference.py"),
        Path("src") / "api" / "app.py",
        Path("scripts") / "start_gpu_api_server.sh",
        Path("scripts") / "commercial_safety_scan.py",
        Path("THIRD_PARTY_LICENSES.md"),
    ]
    missing = [str(path) for path in required if not (repo_root / path).exists()]
    return CheckResult(
        name="repo.required_files",
        status="pass" if not missing else "fail",
        required=True,
        message="Required repository files are present." if not missing else "Required repository files are missing.",
        details={"missing": missing},
    )


def _check_required_models(repo_root: Path) -> CheckResult:
    missing = [str(path) for path in REQUIRED_MODEL_FILES if not (repo_root / path).exists()]
    present = [str(path) for path in REQUIRED_MODEL_FILES if (repo_root / path).exists()]
    return CheckResult(
        name="models.humans_mode",
        status="pass" if not missing else "fail",
        required=True,
        message="Humans mode and MediaPipe model files are present." if not missing else "Model files are missing.",
        details={"present": present, "missing": missing},
    )


def _check_blocked_paths(repo_root: Path) -> CheckResult:
    blocked = [
        Path("pretrained_weights") / ("insight" + "face"),
        Path("src") / "utils" / "dependencies" / ("insight" + "face"),
    ]
    found = [str(path) for path in blocked if (repo_root / path).exists()]
    return CheckResult(
        name="commercial.blocked_paths",
        status="pass" if not found else "fail",
        required=True,
        message="Blocked detector paths are absent." if not found else "Blocked detector paths are present.",
        details={"found": found},
    )


def _check_commercial_safety(repo_root: Path) -> CheckResult:
    issues = scan_paths(default_scan_paths(repo_root))
    return CheckResult(
        name="commercial.safety_scan",
        status="pass" if not issues else "fail",
        required=True,
        message="Commercial safety scan passed." if not issues else "Commercial safety scan found issues.",
        details={
            "issues": [
                {
                    "path": str(issue.path),
                    "line_number": issue.line_number,
                    "term": issue.term,
                }
                for issue in issues
            ]
        },
    )


def _check_api_environment(allow_missing_api_key: bool) -> CheckResult:
    api_key = os.environ.get("LIVEPORTRAIT_API_KEY")
    missing_or_template = not api_key or api_key == TEMPLATE_API_KEY
    required = not allow_missing_api_key
    status = "fail" if missing_or_template and required else "warn" if missing_or_template else "pass"
    numeric_vars = {
        "LIVEPORTRAIT_API_MAX_UPLOAD_BYTES": os.environ.get("LIVEPORTRAIT_API_MAX_UPLOAD_BYTES", "209715200"),
        "LIVEPORTRAIT_API_MAX_ACTIVE_JOBS": os.environ.get("LIVEPORTRAIT_API_MAX_ACTIVE_JOBS", "20"),
        "LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER": os.environ.get("LIVEPORTRAIT_API_MAX_ACTIVE_JOBS_PER_OWNER", "3"),
        "LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB": os.environ.get("LIVEPORTRAIT_API_MAX_RETRIES_PER_JOB", "2"),
    }
    invalid_numeric = [name for name, value in numeric_vars.items() if not _is_positive_int(value)]
    if invalid_numeric:
        status = "fail"
        required = True
    return CheckResult(
        name="api.environment",
        status=status,
        required=required,
        message="API environment is deployable." if status == "pass" else "API environment needs review.",
        details={
            "api_key_configured": bool(api_key),
            "api_key_is_template": api_key == TEMPLATE_API_KEY,
            "data_dir": os.environ.get("LIVEPORTRAIT_API_DATA_DIR", "tmp/api"),
            "force_cpu": os.environ.get("LIVEPORTRAIT_API_FORCE_CPU", "0"),
            "invalid_numeric_vars": invalid_numeric,
            "numeric_vars": numeric_vars,
        },
    )


def _check_system_dependencies(skip: bool) -> list[CheckResult]:
    if skip:
        return [
            CheckResult(
                name="system.commands",
                status="skip",
                required=True,
                message="System command checks skipped.",
                details={"commands": list(REQUIRED_SYSTEM_COMMANDS)},
            ),
            CheckResult(
                name="system.shared_libraries",
                status="skip",
                required=True,
                message="Shared-library checks skipped.",
                details={"libraries": list(REQUIRED_SHARED_LIBRARIES)},
            ),
        ]

    command_paths = {command: shutil.which(command) for command in REQUIRED_SYSTEM_COMMANDS}
    missing_commands = [command for command, path in command_paths.items() if not path]
    library_paths = {
        library: ctypes.util.find_library(lookup_name)
        for library, lookup_name in REQUIRED_SHARED_LIBRARIES.items()
    }
    missing_libraries = [library for library, path in library_paths.items() if not path]

    return [
        CheckResult(
            name="system.commands",
            status="pass" if not missing_commands else "fail",
            required=True,
            message=(
                "Required system commands are available."
                if not missing_commands
                else "Required system commands are missing."
            ),
            details={"paths": command_paths, "missing": missing_commands},
        ),
        CheckResult(
            name="system.shared_libraries",
            status="pass" if not missing_libraries else "fail",
            required=True,
            message=(
                "Required shared libraries are available."
                if not missing_libraries
                else "Required shared libraries are missing."
            ),
            details={"paths": library_paths, "missing": missing_libraries},
        ),
    ]


def _check_imports(skip: bool) -> list[CheckResult]:
    if skip:
        return [
            CheckResult(
                name="python.imports",
                status="skip",
                required=True,
                message="Python import checks skipped.",
                details={"imports": list(REQUIRED_IMPORTS)},
            )
        ]
    results = []
    for module_name in REQUIRED_IMPORTS:
        try:
            module = importlib.import_module(module_name)
            status = "pass"
            message = f"Imported {module_name}."
            details = {"version": str(getattr(module, "__version__", ""))}
        except Exception as exc:
            status = "fail"
            message = f"Could not import {module_name}."
            details = {"error": f"{type(exc).__name__}: {exc}"}
        results.append(CheckResult(module_name, status, True, message, details))
    return results


def _check_gpu(skip: bool) -> CheckResult:
    if skip:
        return CheckResult(
            name="gpu.cuda",
            status="skip",
            required=True,
            message="GPU check skipped.",
            details={},
        )
    try:
        torch = importlib.import_module("torch")
        available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if available else 0
        devices = [torch.cuda.get_device_name(index) for index in range(device_count)]
    except Exception as exc:
        return CheckResult(
            name="gpu.cuda",
            status="fail",
            required=True,
            message="Could not check CUDA through PyTorch.",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )
    return CheckResult(
        name="gpu.cuda",
        status="pass" if available else "fail",
        required=True,
        message="CUDA is available to PyTorch." if available else "CUDA is not available to PyTorch.",
        details={"device_count": device_count, "devices": devices},
    )


def _is_positive_int(value: str) -> bool:
    try:
        return int(value) > 0
    except ValueError:
        return False


def _print_report(payload: dict) -> None:
    print(f"Deployment preflight: {payload['status']}")
    print(f"Repository: {payload['repo_root']}")
    for check in payload["checks"]:
        label = check["status"].upper()
        required = "required" if check["required"] else "optional"
        print(f"{label}: {check['name']} ({required}) - {check['message']}")


if __name__ == "__main__":
    raise SystemExit(main())
