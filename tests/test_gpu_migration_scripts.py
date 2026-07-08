# coding: utf-8

import importlib
import subprocess
import sys
from pathlib import Path


def test_download_humans_assets_uses_allowlist_and_blocks_legacy_detector(tmp_path, monkeypatch):
    module = importlib.import_module("scripts.download_humans_assets")
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        liveportrait_dir = tmp_path / "pretrained_weights" / "liveportrait"
        liveportrait_dir.mkdir(parents=True)
        return str(tmp_path / "pretrained_weights")

    def fake_download_file(url, destination, force=False):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"model")

    monkeypatch.setattr(module, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(module, "_download_file", fake_download_file)

    module.download_humans_assets(repo_root=tmp_path)

    assert calls[0]["allow_patterns"] == ["liveportrait/*"]
    assert "insightface/*" in calls[0]["ignore_patterns"]
    assert "liveportrait_animals/*" in calls[0]["ignore_patterns"]
    assert (tmp_path / "pretrained_weights" / "mediapipe" / "blaze_face_short_range.tflite").exists()


def test_download_humans_assets_fails_when_legacy_detector_dir_exists(tmp_path, monkeypatch):
    module = importlib.import_module("scripts.download_humans_assets")
    legacy_dir = tmp_path / "pretrained_weights" / "insightface"
    legacy_dir.mkdir(parents=True)

    exit_code = module.main(["--repo-root", str(tmp_path)])

    assert exit_code == 1


def test_run_humans_regression_builds_gpu_commands_without_cpu_flags():
    module = importlib.import_module("scripts.run_humans_regression")

    command = module.build_inference_command(
        module.RegressionCase(
            name="video_short",
            source="assets/examples/source/s9.jpg",
            driving="assets/examples/driving/d18.mp4",
            kind="video",
            notes="short driving video",
        ),
        output_dir=Path("animations/gpu_regression_humans"),
        python_executable=Path("python"),
        force_cpu=False,
    )

    assert command[:2] == [str(Path("python")), "inference.py"]
    assert "--flag-force-cpu" not in command
    assert "--no-flag-use-half-precision" not in command
    assert "assets/examples/driving/d18.mp4" in command


def test_run_humans_regression_writes_markdown_report(tmp_path, monkeypatch):
    module = importlib.import_module("scripts.run_humans_regression")
    commands = []

    def fake_run(command, cwd, env, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    exit_code = module.main([
        "--repo-root", str(tmp_path),
        "--case", "image_baseline",
        "--python", sys.executable,
    ])

    reports = list((tmp_path / "docs").glob("humans-gpu-regression-*.md"))
    assert exit_code == 0
    assert len(commands) == 1
    assert reports
    assert "image_baseline" in reports[0].read_text(encoding="utf-8")
