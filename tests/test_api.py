"""Tests for FastAPI endpoints."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from specops.api import app
from specops.storage.run_store import RunStore

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_state(tmp_path: Path, run_id: str, status: str = "QUALITY_PASS") -> Path:
    """Create a run directory with a saved state and return the run dir."""
    run_dir = tmp_path / "outputs" / run_id
    run_dir.mkdir(parents=True)
    store = RunStore(run_dir)
    store.save_state(
        {
            "run_id": run_id,
            "status": status,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    )
    return run_dir


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_ok(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "specops-pipeline"


# ---------------------------------------------------------------------------
# List runs
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_list_runs_no_outputs_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        response = client.get("/runs")
        assert response.status_code == 200
        assert response.json()["runs"] == []

    def test_list_runs_returns_run_ids(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        (outputs / "run_aaa").mkdir()
        (outputs / "run_bbb").mkdir()

        response = client.get("/runs")
        assert response.status_code == 200
        assert set(response.json()["runs"]) == {"run_aaa", "run_bbb"}


# ---------------------------------------------------------------------------
# Get run status
# ---------------------------------------------------------------------------


class TestGetRunStatus:
    def test_get_run_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        response = client.get("/runs/nonexistent_run_xyz")
        assert response.status_code == 404

    def test_get_run_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        _make_run_state(tmp_path, "run_test123", "QUALITY_PASS")

        response = client.get("/runs/run_test123")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "run_test123"
        assert data["status"] == "QUALITY_PASS"
        assert data["created_at"] == "2024-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Approve run
# ---------------------------------------------------------------------------


class TestApproveRun:
    def test_approve_run_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        response = client.post("/runs/nonexistent_xyz/approve")
        assert response.status_code == 404

    def test_approve_run_checkpoint_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        _make_run_state(tmp_path, "run_approve1")

        response = client.post("/runs/run_approve1/approve?checkpoint=1")
        assert response.status_code == 200
        data = response.json()
        assert data["approved"] is True
        assert data["checkpoint"] == "checkpoint_1"
        assert data["run_id"] == "run_approve1"

    def test_approve_run_checkpoint_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        _make_run_state(tmp_path, "run_approve2")

        response = client.post("/runs/run_approve2/approve?checkpoint=2")
        assert response.status_code == 200
        assert response.json()["checkpoint"] == "checkpoint_2"

    def test_approve_run_persists_approval(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        _make_run_state(tmp_path, "run_persist")

        client.post("/runs/run_persist/approve?checkpoint=1")

        run_dir = tmp_path / "outputs" / "run_persist"
        store = RunStore(run_dir)
        state = store.load_state()
        assert state is not None
        assert state["approvals"]["checkpoint_1"] is True


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class TestGetAudit:
    def test_get_audit_no_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        response = client.get("/runs/run_noaudit/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["run_id"] == "run_noaudit"

    def test_get_audit_with_events(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "outputs" / "run_audit"
        run_dir.mkdir(parents=True)
        audit_file = run_dir / ".audit.jsonl"
        audit_file.write_text(
            '{"event": "plan_generated", "timestamp": "2024-01-01T00:00:00Z"}\n'
            '{"event": "code_implemented", "timestamp": "2024-01-01T00:01:00Z"}\n'
        )

        response = client.get("/runs/run_audit/audit")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 2
        assert data["events"][0]["event"] == "plan_generated"


# ---------------------------------------------------------------------------
# Create run (POST /runs)
# ---------------------------------------------------------------------------


class TestCreateRun:
    def test_create_run_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        mock_spec = MagicMock()
        mock_spec.feature_objective = "Test feature"

        with (
            patch("specops.api.parse_spec_file", return_value=mock_spec),
            patch("specops.api.run_planner_workflow", return_value={"plan": {"tasks": []}}),
            patch(
                "specops.api.run_implementer_workflow",
                return_value={"code": "# code", "summary": {}},
            ),
            patch(
                "specops.api.run_test_gen_workflow",
                return_value={"tests": "# tests", "summary": {}},
            ),
        ):
            response = client.post("/runs", json={"spec_file": "sample.json"})

        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "INITIATED"

    def test_create_run_with_custom_run_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        mock_spec = MagicMock()
        mock_spec.feature_objective = "Test"

        with (
            patch("specops.api.parse_spec_file", return_value=mock_spec),
            patch("specops.api.run_planner_workflow", return_value={"plan": {"tasks": []}}),
            patch("specops.api.run_implementer_workflow", return_value={"code": "", "summary": {}}),
            patch("specops.api.run_test_gen_workflow", return_value={"tests": "", "summary": {}}),
        ):
            response = client.post(
                "/runs", json={"spec_file": "sample.json", "run_id": "my_custom_run"}
            )

        assert response.status_code == 200
        assert response.json()["run_id"] == "my_custom_run"

    def test_create_run_spec_parse_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

        with patch("specops.api.parse_spec_file", side_effect=ValueError("bad spec")):
            response = client.post("/runs", json={"spec_file": "bad.json"})

        assert response.status_code == 500
        assert "Run failed" in response.json()["detail"]
