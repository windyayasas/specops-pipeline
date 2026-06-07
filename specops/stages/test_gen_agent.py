"""Test generation agent workflow orchestration."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from specops.agents.state_graphs import TestGenState
from specops.agents.test_gen_nodes import (
    test_proposer_node,
    test_validator_node,
)
from specops.config import get_settings
from specops.models.spec import SpecModel

logger = structlog.get_logger(__name__)


def should_refine_tests(state: TestGenState) -> str:
    """
    Conditional edge: route based on test validator result.

    Returns:
        "refine" if not valid and iterations remain, else "done"
    """
    complete = state.get("complete", False)

    return "done" if complete else "refine"


def build_test_gen_graph() -> Any:
    """
    Build and compile the test generation workflow graph.

    Graph flow:
    test_proposer → test_validator → conditional:
      - if valid or max_iterations: END
      - else: test_proposer (loop)

    Returns:
        Compiled LangGraph workflow
    """
    graph = StateGraph(TestGenState)

    # Add nodes
    graph.add_node("test_proposer", test_proposer_node)
    graph.add_node("test_validator", test_validator_node)

    # Define edges
    graph.set_entry_point("test_proposer")
    graph.add_edge("test_proposer", "test_validator")

    # Conditional edge from validator
    graph.add_conditional_edges(
        "test_validator",
        should_refine_tests,
        {"refine": "test_proposer", "done": END},
    )

    return graph.compile()


def run_test_gen_workflow(
    spec: SpecModel,
    code: str,
    run_id: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Execute test generation workflow: code + spec → tests.

    Args:
        spec: Validated SpecModel
        code: Implementation code to test
        run_id: Run identifier (generated if not provided)
        output_dir: Directory to write outputs

    Returns:
        Test output dict with metadata

    Raises:
        RuntimeError: If test generation fails
    """
    if run_id is None:
        run_id = f"run_{uuid.uuid4().hex[:8]}"

    output_dir = Path("outputs") / run_id if output_dir is None else Path(output_dir)

    # Create output directory
    tests_dir = output_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    logger.info("test_gen_workflow_starting", run_id=run_id)

    # Build and compile graph
    graph = build_test_gen_graph()

    # Prepare initial state
    initial_state: TestGenState = {
        "spec": spec.model_dump(),
        "acceptance_criteria": spec.acceptance_criteria,
        "code": code,
        "test_proposals": [],
        "validation_feedback": [],
        "final_tests": "",
        "iteration": 0,
        "complete": False,
    }

    # Run workflow with iteration tracking
    settings = get_settings()
    for iteration in range(settings.max_test_iterations):
        initial_state["iteration"] = iteration

        try:
            result_state = graph.invoke(initial_state)
        except Exception as e:
            logger.error(
                "test_gen_workflow_failed",
                run_id=run_id,
                iteration=iteration,
                error=str(e),
            )
            raise RuntimeError(f"Test gen workflow failed at iteration {iteration}: {e}") from e

        # Update for next iteration
        initial_state = result_state

        # Check if complete
        if result_state.get("complete", False):
            logger.info("test_gen_completion_achieved", iteration=iteration)
            break

    # Extract final tests
    final_tests = result_state.get("final_tests", "")

    # Write test files
    test_file = tests_dir / "test_acceptance_criteria.py"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(final_tests)

    # Write test summary
    summary = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "iterations": result_state.get("iteration", 0) + 1,
        "complete": result_state.get("complete", False),
        "final_coverage_score": (
            result_state["validation_feedback"][-1].get("coverage_score", 0)
            if result_state.get("validation_feedback")
            else 0
        ),
        "test_proposal_count": len(result_state.get("test_proposals", [])),
        "validation_feedback_count": len(result_state.get("validation_feedback", [])),
    }

    summary_file = output_dir / "test_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(
        "test_gen_workflow_success",
        run_id=run_id,
        test_file=str(test_file),
        summary_file=str(summary_file),
    )

    return {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tests": final_tests,
        "summary": summary,
        "test_proposals": result_state.get("test_proposals", []),
        "validation_feedback": result_state.get("validation_feedback", []),
    }
