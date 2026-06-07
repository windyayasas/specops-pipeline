"""Tests for configuration, prompt templates, and state type definitions."""

import os
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Config / Settings
# ---------------------------------------------------------------------------


class TestSettings:
    def test_settings_groq_api_key_field_exists(self) -> None:
        # Verify the field is declared (pydantic_settings may read from .env file)
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_required_field_test"}, clear=False):
            from specops.config import Settings

            settings = Settings()
            assert hasattr(settings, "groq_api_key")

    def test_settings_from_env(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_key_123"}, clear=False):
            # Re-import to get a fresh instance
            from specops.config import Settings

            settings = Settings()
            assert settings.groq_api_key == "gsk_test_key_123"

    def test_settings_default_log_level(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False):
            from specops.config import Settings

            settings = Settings()
            assert settings.log_level == "INFO"

    def test_settings_default_iterations(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False):
            from specops.config import Settings

            settings = Settings()
            assert settings.max_implementer_iterations == 3
            assert settings.max_test_iterations == 2

    def test_settings_default_allowed_paths(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False):
            from specops.config import Settings

            settings = Settings()
            assert "outputs" in settings.allowed_paths

    def test_settings_custom_log_level(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "LOG_LEVEL": "DEBUG"}, clear=False):
            from specops.config import Settings

            settings = Settings()
            assert settings.log_level == "DEBUG"

    def test_get_settings_returns_settings_instance(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False):
            from specops.config import Settings, get_settings

            settings = get_settings()
            assert isinstance(settings, Settings)


# ---------------------------------------------------------------------------
# Prompt template rendering
# ---------------------------------------------------------------------------


class TestPromptRendering:
    def test_get_template_returns_template(self) -> None:
        from specops.llm.prompts import get_template

        tmpl = get_template("planner_prompt.j2")
        assert tmpl is not None

    def test_render_planner_prompt(self) -> None:
        from specops.llm.prompts import render_planner_prompt

        result = render_planner_prompt(
            feature_objective="Build health endpoint",
            user_story="As a DevOps engineer, I want /health",
            business_rules=["Read-only", "No auth required"],
            acceptance_criteria=["GET /health returns 200", "Response includes status"],
            non_functional_requirements=["p95 < 50ms"],
            out_of_scope=["Deep dependency checks"],
        )
        assert isinstance(result, str)
        assert "Build health endpoint" in result
        assert "Read-only" in result

    def test_render_proposer_prompt(self) -> None:
        from specops.llm.prompts import render_proposer_prompt

        result = render_proposer_prompt(
            feature_objective="Simple API",
            user_story="User story here",
            business_rules=["Rule A"],
            acceptance_criteria=["Criterion 1"],
            non_functional_requirements=["Fast"],
            plan_tasks=["Task 1", "Task 2"],
            design_summary="REST endpoint with JSON response",
        )
        assert isinstance(result, str)
        assert "Task 1" in result

    def test_render_reviewer_prompt(self) -> None:
        from specops.llm.prompts import render_reviewer_prompt

        result = render_reviewer_prompt(
            proposal="def health(): return {'status': 'ok'}",
            feature_objective="Health endpoint",
            acceptance_criteria=["Returns 200", "JSON response"],
        )
        assert isinstance(result, str)
        assert "health" in result.lower()

    def test_render_refiner_prompt(self) -> None:
        from specops.llm.prompts import render_refiner_prompt

        result = render_refiner_prompt(
            proposal="def foo(): pass",
            feedback="Add type annotations and docstring",
        )
        assert isinstance(result, str)
        assert "type annotations" in result

    def test_render_test_proposer_prompt(self) -> None:
        from specops.llm.prompts import render_test_proposer_prompt

        result = render_test_proposer_prompt(
            code="def add(a, b): return a + b",
            acceptance_criteria=["Correct addition", "Handle negatives"],
            feature_objective="Add function",
        )
        assert isinstance(result, str)
        assert "add" in result.lower()

    def test_render_test_validator_prompt(self) -> None:
        from specops.llm.prompts import render_test_validator_prompt

        result = render_test_validator_prompt(
            tests="def test_add(): assert add(1,2) == 3",
            code="def add(a, b): return a + b",
            acceptance_criteria=["Correct addition"],
        )
        assert isinstance(result, str)
        assert "test" in result.lower()

    def test_render_planner_prompt_empty_lists(self) -> None:
        from specops.llm.prompts import render_planner_prompt

        result = render_planner_prompt(
            feature_objective="Minimal feature",
            user_story="Story",
            business_rules=[],
            acceptance_criteria=[],
            non_functional_requirements=[],
            out_of_scope=[],
        )
        assert isinstance(result, str)
        assert "Minimal feature" in result


# ---------------------------------------------------------------------------
# Agent state type definitions
# ---------------------------------------------------------------------------


class TestStateGraphTypes:
    def test_implementer_state_structure(self) -> None:
        from specops.agents.state_graphs import ImplementerState

        state: ImplementerState = {
            "spec": {"feature_objective": "test"},
            "plan": {"tasks": ["t1", "t2"]},
            "proposals": [],
            "reviews": [],
            "current_code": "",
            "iteration": 0,
            "approved": False,
        }
        assert state["iteration"] == 0
        assert state["approved"] is False
        assert state["proposals"] == []

    def test_implementer_state_approved(self) -> None:
        from specops.agents.state_graphs import ImplementerState

        state: ImplementerState = {
            "spec": {},
            "plan": {},
            "proposals": [{"code": "def f(): pass"}],
            "reviews": [{"approved": True}],
            "current_code": "def f(): pass",
            "iteration": 2,
            "approved": True,
        }
        assert state["approved"] is True
        assert state["iteration"] == 2

    def test_test_gen_state_structure(self) -> None:
        from specops.agents.state_graphs import TestGenState

        state: TestGenState = {
            "spec": {"feature_objective": "test"},
            "acceptance_criteria": ["crit1", "crit2"],
            "code": "def foo(): pass",
            "test_proposals": [],
            "validation_feedback": [],
            "final_tests": "",
            "iteration": 0,
            "complete": False,
        }
        assert state["complete"] is False
        assert len(state["acceptance_criteria"]) == 2

    def test_test_gen_state_complete(self) -> None:
        from specops.agents.state_graphs import TestGenState

        state: TestGenState = {
            "spec": {},
            "acceptance_criteria": [],
            "code": "def foo(): pass",
            "test_proposals": [{"tests": "def test_foo(): pass"}],
            "validation_feedback": [{"approved": True}],
            "final_tests": "def test_foo(): pass",
            "iteration": 1,
            "complete": True,
        }
        assert state["complete"] is True
        assert state["final_tests"] != ""

    def test_planner_state_structure(self) -> None:
        from specops.agents.state_graphs import PlannerState

        state: PlannerState = {
            "spec": {"feature_objective": "build API", "user_story": "story"},
            "plan": {"tasks": ["task1"], "design_summary": "REST API"},
        }
        assert "spec" in state
        assert "plan" in state
        assert state["plan"]["tasks"] == ["task1"]
