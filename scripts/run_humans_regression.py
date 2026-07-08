# coding: utf-8

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List, Sequence


DEFAULT_OUTPUT_DIR = Path("animations") / "gpu_regression_humans"
DEFAULT_REPORT_DIR = Path("docs")


@dataclass(frozen=True)
class RegressionCase:
    name: str
    source: str
    driving: str
    kind: str
    notes: str


REGRESSION_CASES = {
    "image_baseline": RegressionCase(
        name="image_baseline",
        source="assets/examples/source/s9.jpg",
        driving="assets/examples/driving/d12.jpg",
        kind="image",
        notes="Baseline static image-driven generation.",
    ),
    "template_short": RegressionCase(
        name="template_short",
        source="assets/examples/source/s9.jpg",
        driving="assets/examples/driving/d1.pkl",
        kind="template",
        notes="Short 16-frame motion-template generation.",
    ),
    "video_short": RegressionCase(
        name="video_short",
        source="assets/examples/source/s9.jpg",
        driving="assets/examples/driving/d18.mp4",
        kind="video",
        notes="Short real driving-video generation.",
    ),
    "multi_face_source": RegressionCase(
        name="multi_face_source",
        source="assets/examples/source/s0.jpg",
        driving="assets/examples/driving/d8.jpg",
        kind="image",
        notes="Source image that may produce multiple detections.",
    ),
    "closeup_source": RegressionCase(
        name="closeup_source",
        source="assets/examples/source/s23.jpg",
        driving="assets/examples/driving/d30.jpg",
        kind="image",
        notes="Close-up source for crop-boundary review.",
    ),
}


def build_inference_command(
    case: RegressionCase,
    output_dir: Path,
    python_executable: Path,
    force_cpu: bool = False,
) -> List[str]:
    command = [
        str(python_executable),
        "inference.py",
        "-s",
        case.source,
        "-d",
        case.driving,
        "-o",
        str(output_dir),
    ]
    if force_cpu:
        command.extend(["--flag-force-cpu", "--no-flag-use-half-precision"])
    return command


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Humans mode GPU regression cases.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Regression output directory.")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR, help="Directory for the markdown report.")
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help="Python executable to run inference.")
    parser.add_argument(
        "--case",
        action="append",
        choices=sorted(REGRESSION_CASES),
        help="Case name to run. Repeat to run multiple cases. Defaults to all cases.",
    )
    parser.add_argument(
        "--force-cpu",
        action="store_true",
        help="Use CPU flags for local smoke testing. GPU migration runs should leave this off.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    case_names = args.case or list(REGRESSION_CASES)
    cases = [REGRESSION_CASES[name] for name in case_names]
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    report_dir = args.report_dir
    if not report_dir.is_absolute():
        report_dir = repo_root / report_dir

    results = []
    for case in cases:
        command = build_inference_command(
            case=case,
            output_dir=output_dir,
            python_executable=args.python,
            force_cpu=args.force_cpu,
        )
        completed = _run_command(command, cwd=repo_root)
        results.append((case, completed.returncode, completed.stdout, completed.stderr, command))
        if completed.returncode != 0:
            _write_report(report_dir, cases=results)
            return completed.returncode

    _write_report(report_dir, cases=results)
    return 0


def _run_command(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(command, cwd=str(cwd), env=env, text=True, capture_output=True)


def _write_report(report_dir: Path, cases: Iterable[tuple]) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"humans-gpu-regression-{date.today().isoformat()}.md"
    lines = [
        f"# Humans GPU Regression - {date.today().isoformat()}",
        "",
        "## Cases",
        "",
        "| Case | Type | Result | Source | Driving | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case, returncode, stdout, stderr, command in cases:
        result = "pass" if returncode == 0 else f"fail ({returncode})"
        lines.append(
            f"| `{case.name}` | {case.kind} | {result} | `{case.source}` | `{case.driving}` | {case.notes} |"
        )
    lines.extend(["", "## Commands", ""])
    for case, returncode, stdout, stderr, command in cases:
        lines.append(f"### {case.name}")
        lines.append("")
        lines.append("```powershell")
        lines.append(" ".join(f'"{part}"' if " " in part else part for part in command))
        lines.append("```")
        lines.append("")
        if returncode != 0:
            lines.append("stderr:")
            lines.append("```text")
            lines.append(stderr.strip())
            lines.append("```")
            lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


if __name__ == "__main__":
    raise SystemExit(main())

