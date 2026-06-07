"""Quality gate orchestration: ruff, mypy, pytest, bandit."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class QualityGateError(Exception):
    """Raised when quality gate check fails."""



def run_quality_gate(
    code_path: str | Path,
    test_path: str | Path | None = None,
    output_file: str | Path | None = None,
) -> dict[str, Any]:
    """
    Run full quality gate: ruff check → mypy → pytest → bandit.

    Args:
        code_path: Path to code file or directory
        test_path: Path to test directory (optional, for pytest)
        output_file: Path to write quality_report.json (optional)

    Returns:
        Quality report dict with all results

    Raises:
        QualityGateError: If any tool fails
    """
    code_path = Path(code_path)
    if test_path:
        test_path = Path(test_path)

    logger.info("quality_gate_starting", code_path=str(code_path))

    report: dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "code_path": str(code_path),
        "results": {},
        "passed": True,
        "errors": [],
    }

    # 1. Ruff check (linting)
    logger.info("quality_gate_ruff_starting")
    try:
        ruff_result = _run_ruff(code_path)
        report["results"]["ruff"] = ruff_result
        if not ruff_result["passed"]:
            report["passed"] = False
            report["errors"].append(f"Ruff failed: {ruff_result.get('error', '')}")
            logger.warning("quality_gate_ruff_failed", errors=ruff_result.get("errors"))
        else:
            logger.info("quality_gate_ruff_passed")
    except Exception as e:
        logger.error("quality_gate_ruff_error", error=str(e))
        report["passed"] = False
        report["errors"].append(f"Ruff error: {e!s}")

    # 2. Mypy check (type checking)
    logger.info("quality_gate_mypy_starting")
    try:
        mypy_result = _run_mypy(code_path)
        report["results"]["mypy"] = mypy_result
        if not mypy_result["passed"]:
            report["passed"] = False
            report["errors"].append(f"Mypy failed: {mypy_result.get('error', '')}")
            logger.warning("quality_gate_mypy_failed", errors=mypy_result.get("errors"))
        else:
            logger.info("quality_gate_mypy_passed")
    except Exception as e:
        logger.error("quality_gate_mypy_error", error=str(e))
        report["passed"] = False
        report["errors"].append(f"Mypy error: {e!s}")

    # 3. Pytest (unit and integration tests)
    if test_path and test_path.exists():
        logger.info("quality_gate_pytest_starting")
        try:
            pytest_result = _run_pytest(test_path)
            report["results"]["pytest"] = pytest_result
            if not pytest_result["passed"]:
                report["passed"] = False
                report["errors"].append(f"Pytest failed: {pytest_result.get('error', '')}")
                logger.warning("quality_gate_pytest_failed", output=pytest_result.get("output"))
            else:
                logger.info("quality_gate_pytest_passed")
        except Exception as e:
            logger.error("quality_gate_pytest_error", error=str(e))
            report["passed"] = False
            report["errors"].append(f"Pytest error: {e!s}")
    else:
        report["results"]["pytest"] = {"skipped": True, "reason": "No test path provided"}
        logger.info("quality_gate_pytest_skipped")

    # 4. Bandit (security scan)
    logger.info("quality_gate_bandit_starting")
    try:
        bandit_result = _run_bandit(code_path)
        report["results"]["bandit"] = bandit_result
        if not bandit_result["passed"]:
            report["passed"] = False
            report["errors"].append(f"Bandit found issues: {bandit_result.get('error', '')}")
            logger.warning("quality_gate_bandit_failed", issues=bandit_result.get("issues"))
        else:
            logger.info("quality_gate_bandit_passed")
    except Exception as e:
        logger.error("quality_gate_bandit_error", error=str(e))
        report["passed"] = False
        report["errors"].append(f"Bandit error: {e!s}")

    # Write report
    if output_file:
        output_file = Path(output_file)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info("quality_gate_report_written", file=str(output_file))

    # Log final result
    if report["passed"]:
        logger.info("quality_gate_passed")
    else:
        logger.error("quality_gate_failed", error_count=len(report["errors"]))
        raise QualityGateError(f"Quality gate failed with errors: {report['errors']}")

    return report


def _run_ruff(code_path: Path) -> dict[str, Any]:
    """Run ruff linter."""
    try:
        result = subprocess.run(
            ["ruff", "check", str(code_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        return {
            "passed": result.returncode == 0,
            "exit_code": result.returncode,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
            "errors": result.stdout.split("\n") if result.returncode != 0 else [],
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "Ruff timeout"}
    except FileNotFoundError:
        return {"passed": False, "error": "Ruff not installed"}


def _run_mypy(code_path: Path) -> dict[str, Any]:
    """Run mypy type checker."""
    try:
        result = subprocess.run(
            ["mypy", str(code_path), "--strict"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        return {
            "passed": result.returncode == 0,
            "exit_code": result.returncode,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
            "errors": result.stdout.split("\n") if result.returncode != 0 else [],
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "Mypy timeout"}
    except FileNotFoundError:
        return {"passed": False, "error": "Mypy not installed"}


def _run_pytest(test_path: Path) -> dict[str, Any]:
    """Run pytest test suite."""
    try:
        result = subprocess.run(
            [
                "pytest",
                str(test_path),
                "-v",
                "--tb=short",
                "--color=no",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        return {
            "passed": result.returncode == 0,
            "exit_code": result.returncode,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "Pytest timeout"}
    except FileNotFoundError:
        return {"passed": False, "error": "Pytest not installed"}


def _run_bandit(code_path: Path) -> dict[str, Any]:
    """Run bandit security scanner."""
    try:
        result = subprocess.run(
            ["bandit", "-r", str(code_path), "-f", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Bandit returns 0 if no issues, 1 if issues found
        # Parse JSON output
        issues = []
        try:
            output = json.loads(result.stdout) if result.stdout else {}
            issues = output.get("results", [])
        except json.JSONDecodeError:
            pass

        return {
            "passed": result.returncode == 0,
            "exit_code": result.returncode,
            "issues": issues,
            "issue_count": len(issues),
            "error": None if result.returncode == 0 else "Security issues found",
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "Bandit timeout"}
    except FileNotFoundError:
        return {"passed": False, "error": "Bandit not installed"}
