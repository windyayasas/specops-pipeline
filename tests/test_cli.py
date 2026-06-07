"""Tests for CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specops.cli import app
from specops.storage.run_store import RunStore

runner = CliRunner()


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_run_missing_spec_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["run", "nonexistent_spec.json"])
        assert result.exit_code != 0

    def test_run_success_skip_approval(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        spec_file = tmp_path / "test_spec.json"
        spec_file.write_text("{}")

        mock_spec = MagicMock()
        mock_spec.feature_objective = "Build health endpoint"

        with (
            patch("specops.cli.parse_spec_file", return_value=mock_spec),
            patch("specops.cli.run_planner_workflow", return_value={"plan": {"tasks": [], "design_summary": ""}}),
            patch(
                "specops.cli.run_implementer_workflow",
                return_value={"code": "# code", "summary": {"iterations": 1, "approved": True}},
            ),
            patch("specops.cli.run_test_gen_workflow", return_value={"tests": "# tests", "summary": {}}),
            patch("specops.cli.run_quality_gate", return_value={"passed": True, "results": {}}),
        ):
            result = runner.invoke(app, ["run", str(spec_file), "--skip-approval"])

        assert result.exit_code == 0
        assert "Pipeline completed successfully" in result.output

    def test_run_with_custom_run_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}")

        mock_spec = MagicMock()
        mock_spec.feature_objective = "test"

        with (
            patch("specops.cli.parse_spec_file", return_value=mock_spec),
            patch("specops.cli.run_planner_workflow", return_value={"plan": {"tasks": []}}),
            patch("specops.cli.run_implementer_workflow", return_value={"code": "", "summary": {}}),
            patch("specops.cli.run_test_gen_workflow", return_value={"summary": {}}),
            patch("specops.cli.run_quality_gate", return_value={"passed": True, "results": {}}),
        ):
            result = runner.invoke(
                app, ["run", str(spec_file), "--skip-approval", "--run-id", "custom_run_xyz"]
            )

        assert result.exit_code == 0
        assert "custom_run_xyz" in result.output

    def test_run_quality_gate_failure_with_skip_approval(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}")

        from specops.stages.quality_gate import QualityGateError

        mock_spec = MagicMock()
        mock_spec.feature_objective = "test"

        with (
            patch("specops.cli.parse_spec_file", return_value=mock_spec),
            patch("specops.cli.run_planner_workflow", return_value={"plan": {"tasks": []}}),
            patch("specops.cli.run_implementer_workflow", return_value={"code": "", "summary": {}}),
            patch("specops.cli.run_test_gen_workflow", return_value={"summary": {}}),
            patch("specops.cli.run_quality_gate", side_effect=QualityGateError("quality failed")),
        ):
            result = runner.invoke(app, ["run", str(spec_file), "--skip-approval"])

        # With --skip-approval the quality gate failure is caught but pipeline continues
        assert result.exit_code == 0

    def test_run_approval_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}")

        mock_spec = MagicMock()
        mock_spec.feature_objective = "test"

        with (
            patch("specops.cli.parse_spec_file", return_value=mock_spec),
            patch("specops.cli.run_planner_workflow", return_value={"plan": {"tasks": []}}),
            patch("specops.cli.ApprovalManager") as MockApproval,
        ):
            mock_mgr = MockApproval.return_value
            mock_mgr.request_approval.return_value = False
            result = runner.invoke(app, ["run", str(spec_file)])

        assert result.exit_code != 0

    def test_run_with_custom_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}")
        custom_out = tmp_path / "my_outputs"

        mock_spec = MagicMock()
        mock_spec.feature_objective = "test"

        with (
            patch("specops.cli.parse_spec_file", return_value=mock_spec),
            patch("specops.cli.run_planner_workflow", return_value={"plan": {"tasks": []}}),
            patch("specops.cli.run_implementer_workflow", return_value={"code": "", "summary": {}}),
            patch("specops.cli.run_test_gen_workflow", return_value={"summary": {}}),
            patch("specops.cli.run_quality_gate", return_value={"passed": True, "results": {}}),
        ):
            result = runner.invoke(
                app, ["run", str(spec_file), "--skip-approval", "--output-dir", str(custom_out)]
            )

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------


class TestStatusCommand:
    def test_status_run_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status", "nonexistent_run_abc"])
        assert result.exit_code != 0

    def test_status_run_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "outputs" / "run_status_test"
        run_dir.mkdir(parents=True)
        store = RunStore(run_dir)
        store.save_state(
            {
                "run_id": "run_status_test",
                "status": "DEPLOYED",
                "plan": {"tasks": ["task1", "task2"], "design_summary": "A simple design"},
            }
        )

        result = runner.invoke(app, ["status", "run_status_test"])
        assert result.exit_code == 0
        assert "DEPLOYED" in result.output

    def test_status_with_code_summary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "outputs" / "run_with_code"
        run_dir.mkdir(parents=True)
        store = RunStore(run_dir)
        store.save_state(
            {
                "run_id": "run_with_code",
                "status": "DEPLOYED",
                "plan": {"tasks": [], "design_summary": ""},
                "code_summary": {"iterations": 2, "approved": True},
            }
        )

        result = runner.invoke(app, ["status", "run_with_code"])
        assert result.exit_code == 0
        assert "Iterations" in result.output or "iterations" in result.output.lower()

    def test_status_with_custom_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        custom_dir = tmp_path / "custom_outputs"
        custom_dir.mkdir()
        store = RunStore(custom_dir)
        store.save_state({"run_id": "run_custom", "status": "QUALITY_PASS"})

        result = runner.invoke(app, ["status", "run_custom", "--output-dir", str(custom_dir)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# list-runs command
# ---------------------------------------------------------------------------


class TestListRunsCommand:
    def test_list_runs_no_outputs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["list-runs"])
        assert result.exit_code == 0
        assert "No runs found" in result.output

    def test_list_runs_empty_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "outputs").mkdir()
        result = runner.invoke(app, ["list-runs"])
        assert result.exit_code == 0
        assert "No runs found" in result.output

    def test_list_runs_with_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        outputs = tmp_path / "outputs"
        outputs.mkdir()

        run_dir = outputs / "run_listed"
        run_dir.mkdir()
        store = RunStore(run_dir)
        store.save_state({"run_id": "run_listed", "status": "DEPLOYED"})

        result = runner.invoke(app, ["list-runs"])
        assert result.exit_code == 0
        assert "run_listed" in result.output

    def test_list_runs_custom_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        custom = tmp_path / "custom_base"
        custom.mkdir()
        run_dir = custom / "run_xyz"
        run_dir.mkdir()
        store = RunStore(run_dir)
        store.save_state({"run_id": "run_xyz", "status": "QUALITY_PASS"})

        result = runner.invoke(app, ["list-runs", "--output-dir", str(custom)])
        assert result.exit_code == 0
        assert "run_xyz" in result.output
