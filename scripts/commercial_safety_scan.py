# coding: utf-8

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


def _term(*parts: str) -> str:
    return "".join(parts)


DISALLOWED_TERMS = (
    _term("FaceAnalysis", "DIY"),
    _term("buffalo", "_l"),
    _term("insight", "face_root"),
    _term("dependencies/", "insight", "face"),
    _term("pretrained_weights/", "insight", "face"),
)

DEFAULT_TARGETS = (
    "src",
    "scripts",
    "requirements.txt",
    "requirements_base.txt",
    "requirements_macOS.txt",
    "app.py",
    "app_animals.py",
    "inference.py",
    "inference_animals.py",
)

EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "docs",
    "tests",
}

EXCLUDED_NAMES = {
    "THIRD_PARTY_LICENSES.md",
}


@dataclass(frozen=True)
class ScanIssue:
    path: Path
    line_number: int
    term: str
    line: str


def scan_paths(paths: Sequence[Path]) -> List[ScanIssue]:
    issues: List[ScanIssue] = []
    for file_path in _iter_files(paths):
        if not _should_scan(file_path):
            continue
        issues.extend(_scan_file(file_path))
    return issues


def default_scan_paths(repo_root: Path) -> List[Path]:
    return [repo_root / target for target in DEFAULT_TARGETS if (repo_root / target).exists()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan runtime files for commercial-risk detector references.")
    parser.add_argument("paths", nargs="*", type=Path, help="Files or directories to scan.")
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    paths = args.paths or default_scan_paths(repo_root)
    issues = scan_paths(paths)
    if not issues:
        print("Commercial safety scan passed.")
        return 0

    print("Commercial safety scan failed:")
    for issue in issues:
        print(f"{issue.path}:{issue.line_number}: found {issue.term}: {issue.line.strip()}")
    return 1


def _iter_files(paths: Sequence[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    yield child


def _should_scan(path: Path) -> bool:
    if path.name in EXCLUDED_NAMES:
        return False
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return False
    if path.suffix.lower() in {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".pkl", ".onnx", ".pth"}:
        return False
    return True


def _scan_file(path: Path) -> List[ScanIssue]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")

    issues: List[ScanIssue] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        normalized_line = line.replace("\\", "/")
        for term in DISALLOWED_TERMS:
            if term in normalized_line:
                issues.append(
                    ScanIssue(
                        path=path,
                        line_number=line_number,
                        term=term,
                        line=line,
                    )
                )
    return issues


if __name__ == "__main__":
    raise SystemExit(main())

