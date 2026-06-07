"""Tests for quality gate orchestration."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specops.stages.quality_gate import (
    QualityGateError,
    _run_bandit,
    _run_mypy,
    _run_pytest,
    _run_ruff,
    run_quality_gate,
)

# ---------------------------------------------------------------------------
# _run_ruff
# ---------------------------------------------------------------------------


class TestRunRuff:
    def test_ruff_passes(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = _run_ruff(tmp_path)
        assert result["passed"] is True
        assert result["exit_code"] == 0

    def test_ruff_fails_with_errors(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="E501 line too long", stderr="")
            result = _run_ruff(tmp_path)
        assert result["passed"] is False
        assert result["error"] is not None

    def test_ruff_not_installed(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _run_ruff(tmp_path)
        assert result["passed"] is False
        assert "not installed" in result["error"]

    def test_ruff_timeout(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 60)):
            result = _run_ruff(tmp_path)
        assert result["passed"] is False
        assert "timeout" in result["error"].lower()


# ---------------------------------------------------------------------------
# _run_mypy
# ---------------------------------------------------------------------------


class TestRunMypy:
    def test_mypy_passes(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
            result = _run_mypy(tmp_path)
        assert result["passed"] is True

    def test_mypy_fails(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="error: missing type annotation", stderr=""
            )
            result = _run_mypy(tmp_path)
        assert result["passed"] is False
        assert result["error"] is not None

    def test_mypy_not_installed(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _run_mypy(tmp_path)
        assert result["passed"] is False
        assert "not installed" in result["error"]

    def test_mypy_timeout(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("mypy", 60)):
            result = _run_mypy(tmp_path)
        assert result["passed"] is False
        assert "timeout" in result["error"].lower()


# ---------------------------------------------------------------------------
# _run_pytest
# ---------------------------------------------------------------------------


class TestRunPytest:
    def test_pytest_passes(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="5 passed", stderr="")
            result = _run_pytest(tmp_path)
        assert result["passed"] is True

    def test_pytest_fails(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="1 failed", stderr="")
            result = _run_pytest(tmp_path)
        assert result["passed"] is False

    def test_pytest_not_installed(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _run_pytest(tmp_path)
        assert result["passed"] is False
        assert "not installed" in result["error"]

    def test_pytest_timeout(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pytest", 300)):
            result = _run_pytest(tmp_path)
        assert result["passed"] is False
        assert "timeout" in result["error"].lower()


# ---------------------------------------------------------------------------
# _run_bandit
# ---------------------------------------------------------------------------


class TestRunBandit:
    def test_bandit_passes_no_issues(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout='{"results": []}', stderr=""
            )
            result = _run_bandit(tmp_path)
        assert result["passed"] is True
        assert result["issue_count"] == 0

    def test_bandit_fails_with_issues(self, tmp_path: Path) -> None:
        issues = [{"test_id": "B101", "issue_text": "assert detected"}]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout=json.dumps({"results": issues}), stderr=""
            )
            result = _run_bandit(tmp_path)
        assert result["passed"] is False
        assert result["issue_count"] == 1
        assert result["issues"] == issues

    def test_bandit_not_installed(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _run_bandit(tmp_path)
        assert result["passed"] is False
        assert "not installed" in result["error"]

    def test_bandit_timeout(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("bandit", 60)):
            result = _run_bandit(tmp_path)
        assert result["passed"] is False
        assert "timeout" in result["error"].lower()

    def test_bandit_invalid_json_output(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
            result = _run_bandit(tmp_path)
        # Should not raise, issues should default to empty
        assert result["issue_count"] == 0


# ---------------------------------------------------------------------------
# run_quality_gate (integration)
# ---------------------------------------------------------------------------


class TestRunQualityGate:
    def _passing_subprocess(self) -> MagicMock:
        return MagicMock(returncode=0, stdout='{"results": []}', stderr="")

    def test_all_checks_pass(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._passing_subprocess()
            result = run_quality_gate(tmp_path / "src")

        assert result["passed"] is True
        assert "ruff" in result["results"]
        assert "mypy" in result["results"]
        assert "bandit" in result["results"]

    def test_ruff_failure_raises_quality_gate_error(self, tmp_path: Path) -> None:
        def _side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
            if "ruff" in cmd:
                return MagicMock(returncode=1, stdout="E501 error", stderr="")
            return MagicMock(returncode=0, stdout='{"results": []}', stderr="")

        with patch("subprocess.run", side_effect=_side_effect), pytest.raises(QualityGateError):
            run_quality_gate(tmp_path / "src")

    def test_mypy_failure_raises_quality_gate_error(self, tmp_path: Path) -> None:
        def _side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
            if "mypy" in cmd:
                return MagicMock(returncode=1, stdout="type error", stderr="")
            return MagicMock(returncode=0, stdout='{"results": []}', stderr="")

        with patch("subprocess.run", side_effect=_side_effect), pytest.raises(QualityGateError):
            run_quality_gate(tmp_path / "src")

    def test_writes_output_file(self, tmp_path: Path) -> None:
        output_file = tmp_path / "quality_report.json"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._passing_subprocess()
            run_quality_gate(tmp_path / "src", output_file=output_file)

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "passed" in data
        assert "results" in data

    def test_includes_pytest_when_test_path_exists(self, tmp_path: Path) -> None:
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._passing_subprocess()
            result = run_quality_gate(tmp_path / "src", test_path=test_dir)

        assert "pytest" in result["results"]
        assert result["results"]["pytest"].get("skipped") is not True

    def test_skips_pytest_when_no_test_path(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._passing_subprocess()
            result = run_quality_gate(tmp_path / "src")

        assert result["results"]["pytest"]["skipped"] is True

    def test_skips_pytest_when_test_path_not_exist(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._passing_subprocess()
            result = run_quality_gate(tmp_path / "src", test_path=tmp_path / "nonexistent_tests")

        assert result["results"]["pytest"]["skipped"] is True

    def test_bandit_failure_raises_quality_gate_error(self, tmp_path: Path) -> None:
        issues = [{"test_id": "B101"}]

        def _side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
            if "bandit" in cmd:
                return MagicMock(returncode=1, stdout=json.dumps({"results": issues}), stderr="")
            return MagicMock(returncode=0, stdout='{"results": []}', stderr="")

        with patch("subprocess.run", side_effect=_side_effect), pytest.raises(QualityGateError):
            run_quality_gate(tmp_path / "src")

    def test_report_contains_timestamp(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._passing_subprocess()
            result = run_quality_gate(tmp_path / "src")

        assert "timestamp" in result
        assert result["timestamp"].endswith("Z")
