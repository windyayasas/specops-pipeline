"""Tests for approval checkpoints and manager."""

from typing import Any
from unittest.mock import patch

import pytest

from specops.stages.approval import ApprovalCheckpoint, ApprovalManager


class TestApprovalCheckpoint:
    def test_init_stores_fields(self) -> None:
        cp = ApprovalCheckpoint("checkpoint_1", "Review the implementation plan")
        assert cp.checkpoint_id == "checkpoint_1"
        assert cp.description == "Review the implementation plan"

    def test_request_approval_returns_true_when_confirmed(self) -> None:
        cp = ApprovalCheckpoint("cp1", "Approve this?")
        with patch("typer.confirm", return_value=True):
            result = cp.request_approval()
        assert result is True

    def test_request_approval_returns_false_when_rejected(self) -> None:
        cp = ApprovalCheckpoint("cp1", "Approve this?")
        with patch("typer.confirm", return_value=False):
            result = cp.request_approval()
        assert result is False

    def test_request_approval_with_list_details(self, capsys: pytest.CaptureFixture[str]) -> None:
        cp = ApprovalCheckpoint("cp1", "Check tasks")
        details: dict[str, Any] = {"Tasks": ["task1", "task2"], "Design": "Simple REST API"}
        with patch("typer.confirm", return_value=True):
            result = cp.request_approval(details)
        assert result is True
        captured = capsys.readouterr()
        assert "task1" in captured.out
        assert "Design" in captured.out

    def test_request_approval_with_scalar_details(self, capsys: pytest.CaptureFixture[str]) -> None:
        cp = ApprovalCheckpoint("cp2", "Check score")
        details: dict[str, Any] = {"Score": "95%", "Issues": 0}
        with patch("typer.confirm", return_value=False):
            result = cp.request_approval(details)
        assert result is False
        captured = capsys.readouterr()
        assert "Score" in captured.out

    def test_request_approval_no_details(self, capsys: pytest.CaptureFixture[str]) -> None:
        cp = ApprovalCheckpoint("cp1", "Simple checkpoint")
        with patch("typer.confirm", return_value=True):
            cp.request_approval(details=None)
        captured = capsys.readouterr()
        assert "checkpoint_1" in captured.out or "cp1" in captured.out


class TestApprovalManager:
    def test_init_empty_state(self) -> None:
        mgr = ApprovalManager()
        assert mgr.approvals == {}
        assert mgr.checkpoints == {}

    def test_register_checkpoint(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "Review plan")
        assert "cp1" in mgr.checkpoints
        assert mgr.checkpoints["cp1"].description == "Review plan"

    def test_register_multiple_checkpoints(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "First")
        mgr.register_checkpoint("cp2", "Second")
        assert len(mgr.checkpoints) == 2

    def test_request_approval_unknown_checkpoint_raises(self) -> None:
        mgr = ApprovalManager()
        with pytest.raises(ValueError, match="Unknown checkpoint"):
            mgr.request_approval("not_registered")

    def test_request_approval_approved(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "Test")
        with patch("typer.confirm", return_value=True):
            result = mgr.request_approval("cp1")
        assert result is True
        assert mgr.approvals["cp1"] is True

    def test_request_approval_rejected(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "Test")
        with patch("typer.confirm", return_value=False):
            result = mgr.request_approval("cp1")
        assert result is False
        assert mgr.approvals["cp1"] is False

    def test_request_approval_with_details(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "Test")
        details: dict[str, Any] = {"Tasks": ["t1"], "Score": "ok"}
        with patch("typer.confirm", return_value=True):
            result = mgr.request_approval("cp1", details)
        assert result is True

    def test_is_approved_true(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "Test")
        with patch("typer.confirm", return_value=True):
            mgr.request_approval("cp1")
        assert mgr.is_approved("cp1") is True

    def test_is_approved_false(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "Test")
        with patch("typer.confirm", return_value=False):
            mgr.request_approval("cp1")
        assert mgr.is_approved("cp1") is False

    def test_is_approved_not_registered_returns_false(self) -> None:
        mgr = ApprovalManager()
        assert mgr.is_approved("never_seen") is False

    def test_all_approved_empty_returns_false(self) -> None:
        mgr = ApprovalManager()
        assert mgr.all_approved() is False

    def test_all_approved_all_true(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "First")
        mgr.register_checkpoint("cp2", "Second")
        with patch("typer.confirm", return_value=True):
            mgr.request_approval("cp1")
            mgr.request_approval("cp2")
        assert mgr.all_approved() is True

    def test_all_approved_partial(self) -> None:
        mgr = ApprovalManager()
        mgr.register_checkpoint("cp1", "First")
        mgr.register_checkpoint("cp2", "Second")
        with patch("typer.confirm", return_value=True):
            mgr.request_approval("cp1")
        with patch("typer.confirm", return_value=False):
            mgr.request_approval("cp2")
        assert mgr.all_approved() is False
