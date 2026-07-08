# coding: utf-8

import importlib
from pathlib import Path

import pytest


def test_commercial_safety_scan_reports_disallowed_runtime_reference(tmp_path):
    scanner = importlib.import_module("scripts.commercial_safety_scan")
    disallowed_symbol = "FaceAnalysis" + "DIY"
    risky_file = tmp_path / "src" / "utils" / "legacy_detector.py"
    risky_file.parent.mkdir(parents=True)
    risky_file.write_text(f"detector = {disallowed_symbol}\n", encoding="utf-8")

    issues = scanner.scan_paths([risky_file])

    assert len(issues) == 1
    assert issues[0].path == risky_file
    assert issues[0].term == disallowed_symbol


def test_commercial_safety_scan_allows_license_documentation(tmp_path):
    scanner = importlib.import_module("scripts.commercial_safety_scan")
    disallowed_symbol = "FaceAnalysis" + "DIY"
    docs_file = tmp_path / "THIRD_PARTY_LICENSES.md"
    docs_file.write_text(f"Legacy symbol documented: {disallowed_symbol}\n", encoding="utf-8")

    issues = scanner.scan_paths([docs_file])

    assert issues == []


def test_commercial_environment_check_blocks_legacy_weight_directory(tmp_path):
    commercial_safety = importlib.import_module("src.utils.commercial_safety")
    insightface_dir = tmp_path / "pretrained_weights" / ("insight" + "face")
    insightface_dir.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="commercial-safe build"):
        commercial_safety.assert_commercial_safe_environment(tmp_path)
