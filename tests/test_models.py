"""Tests for data models."""

import pytest
from pydantic import ValidationError

from specops.models.audit import AuditEvent
from specops.models.plan import PlanOutput, RunState
from specops.models.spec import SpecModel


class TestSpecModel:
    """Spec model validation tests."""

    def test_spec_model_creation(self):
        """Test creating a valid SpecModel."""
        spec = SpecModel(
            feature_objective="Test feature",
            user_story="As a user...",
            business_rules=["Rule 1"],
            acceptance_criteria=["Criterion 1"],
        )

        assert spec.feature_objective == "Test feature"
        assert spec.user_story == "As a user..."
        assert len(spec.business_rules) == 1

    def test_spec_model_requires_feature_objective(self):
        """Test that feature_objective is required."""
        with pytest.raises(ValidationError):
            SpecModel(user_story="Test")

    def test_spec_model_requires_user_story(self):
        """Test that user_story is required."""
        with pytest.raises(ValidationError):
            SpecModel(feature_objective="Test")

    def test_spec_model_with_empty_lists(self):
        """Test SpecModel with empty lists for optional fields."""
        spec = SpecModel(
            feature_objective="Test",
            user_story="Test story",
            business_rules=[],
            acceptance_criteria=[],
        )

        assert spec.business_rules == []
        assert spec.acceptance_criteria == []


class TestPlanOutput:
    """Plan output model tests."""

    def test_plan_output_creation(self):
        """Test creating a valid PlanOutput."""
        plan = PlanOutput(
            tasks=["Task 1", "Task 2"],
            design_summary="Test design",
            test_strategy="Unit and integration tests",
        )

        assert len(plan.tasks) == 2
        assert plan.design_summary == "Test design"

    def test_plan_output_requires_tasks(self):
        """Test that tasks is required."""
        with pytest.raises(ValidationError):
            PlanOutput(
                design_summary="Test",
                test_strategy="Test",
            )

    def test_plan_output_with_optional_fields(self):
        """Test PlanOutput with optional fields."""
        plan = PlanOutput(
            tasks=["Task 1"],
            design_summary="Design",
            test_strategy="Test",
            impacted_modules=["module1", "module2"],
            risks=["Risk 1"],
        )

        assert len(plan.impacted_modules) == 2
        assert len(plan.risks) == 1


class TestRunState:
    """Run state model tests."""

    def test_run_state_creation(self):
        """Test creating a valid RunState."""
        state = RunState(
            status="CREATED",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        assert state.status == "CREATED"
        assert state.created_at == "2024-01-01T00:00:00Z"

    def test_run_state_requires_status(self):
        """Test that status is required."""
        with pytest.raises(ValidationError):
            RunState(
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )

    def test_run_state_with_approvals(self):
        """Test RunState with approval dict."""
        state = RunState(
            status="PLAN_APPROVED",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            approvals={"checkpoint_1": True, "checkpoint_2": False},
        )

        assert state.approvals["checkpoint_1"] is True
        assert state.approvals["checkpoint_2"] is False


class TestAuditEvent:
    """Audit event model tests."""

    def test_audit_event_creation(self):
        """Test creating a valid AuditEvent."""
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            run_id="run_123",
            stage="planner",
            actor="system",
            event_type="plan_generated",
            status="success",
        )

        assert event.run_id == "run_123"
        assert event.event_type == "plan_generated"
        assert event.status == "success"

    def test_audit_event_requires_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            AuditEvent(
                timestamp="2024-01-01T00:00:00Z",
                run_id="run_123",
                stage="planner",
                # Missing actor, event_type, status
            )

    def test_audit_event_with_details(self):
        """Test AuditEvent with details metadata."""
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            run_id="run_123",
            stage="planner",
            actor="system",
            event_type="plan_generated",
            status="success",
            details={
                "task_count": 5,
                "duration_ms": 2500,
            },
        )

        assert event.details["task_count"] == 5
        assert event.details["duration_ms"] == 2500

    def test_audit_event_details_default_empty(self):
        """Test that details defaults to empty dict."""
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            run_id="run_123",
            stage="planner",
            actor="system",
            event_type="plan_generated",
            status="success",
        )

        assert event.details == {}
