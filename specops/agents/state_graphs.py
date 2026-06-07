"""LangGraph state definitions for pipeline workflows."""

from typing import Any, TypedDict


class ImplementerState(TypedDict):
    """State for the code implementer workflow."""

    spec: dict[str, Any]
    """Original specification as dict."""

    plan: dict[str, Any]
    """Plan output from planner agent."""

    proposals: list[dict[str, Any]]
    """All code proposals generated during iterations."""

    reviews: list[dict[str, Any]]
    """All code reviews generated during iterations."""

    current_code: str
    """Current iteration code (from proposer or refiner)."""

    iteration: int
    """Current iteration number (0-indexed)."""

    approved: bool
    """Whether code has passed review."""


class TestGenState(TypedDict):
    """State for the test generation workflow."""

    spec: dict[str, Any]
    """Original specification."""

    acceptance_criteria: list[str]
    """Acceptance criteria from spec."""

    code: str
    """Implementation code to test."""

    test_proposals: list[dict[str, Any]]
    """All test proposals from test proposer."""

    validation_feedback: list[dict[str, Any]]
    """All feedback from test validator."""

    final_tests: str
    """Final test code (approved by validator)."""

    iteration: int
    """Current iteration number."""

    complete: bool
    """Whether test generation is complete."""


class PlannerState(TypedDict):
    """State for the planner workflow."""

    spec: dict[str, Any]
    """Original specification."""

    plan: dict[str, Any]
    """Generated plan."""
