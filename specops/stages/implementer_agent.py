"""Implementer agent workflow orchestration."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from specops.agents.implementer_nodes import (
    proposer_node,
    refiner_node,
    reviewer_node,
)
from specops.agents.state_graphs import ImplementerState
from specops.config import get_settings
from specops.models.spec import SpecModel

logger = structlog.get_logger(__name__)


def should_refine(state: ImplementerState) -> str:
    """
    Conditional edge: route based on reviewer approval.

    Returns:
        "refine" if not approved and iterations remain, else "done"
    """
    approved = state.get("approved", False)
    iteration = state.get("iteration", 0)
    settings = get_settings()

    if approved:
        return "done"

    if iteration < settings.max_implementer_iterations - 1:
        return "refine"

    # Max iterations reached
    logger.warning(
        "max_implementer_iterations_reached",
        iteration=iteration,
        max=settings.max_implementer_iterations,
    )
    return "done"


def build_implementer_graph() -> Any:
    """
    Build and compile the implementer workflow graph.

    Graph flow:
    proposer → reviewer → conditional:
      - if approved: END
      - if not approved and iterations < max: refiner → reviewer
      - else: END

    Returns:
        Compiled LangGraph workflow
    """
    graph = StateGraph(ImplementerState)

    # Add nodes
    graph.add_node("proposer", proposer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("refiner", refiner_node)

    # Define edges
    graph.set_entry_point("proposer")
    graph.add_edge("proposer", "reviewer")

    # Conditional edge from reviewer
    graph.add_conditional_edges(
        "reviewer",
        should_refine,
        {"refine": "refiner", "done": END},
    )

    # Refiner loops back to reviewer
    graph.add_edge("refiner", "reviewer")

    return graph.compile()


def run_implementer_workflow(
    spec: SpecModel,
    plan: dict[str, Any],
    run_id: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Execute implementer workflow: spec + plan → code.

    Args:
        spec: Validated SpecModel
        plan: Plan output from planner
        run_id: Run identifier (generated if not provided)
        output_dir: Directory to write outputs

    Returns:
        Code output dict with metadata

    Raises:
        RuntimeError: If implementer fails
    """
    if run_id is None:
        run_id = f"run_{uuid.uuid4().hex[:8]}"

    output_dir = Path("outputs") / run_id if output_dir is None else Path(output_dir)

    # Create output directory
    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    logger.info("implementer_workflow_starting", run_id=run_id)

    # Build and compile graph
    graph = build_implementer_graph()

    # Prepare initial state
    initial_state: ImplementerState = {
        "spec": spec.model_dump(),
        "plan": plan,
        "proposals": [],
        "reviews": [],
        "current_code": "",
        "iteration": 0,
        "approved": False,
    }

    # Run workflow with iteration tracking
    settings = get_settings()
    for iteration in range(settings.max_implementer_iterations):
        initial_state["iteration"] = iteration

        try:
            result_state = graph.invoke(initial_state)
        except Exception as e:
            logger.error(
                "implementer_workflow_failed",
                run_id=run_id,
                iteration=iteration,
                error=str(e),
            )
            raise RuntimeError(f"Implementer workflow failed at iteration {iteration}: {e}") from e

        # Update for next iteration
        initial_state = result_state

        # Check if approved
        if result_state.get("approved", False):
            logger.info("implementer_approval_achieved", iteration=iteration)
            break

    # Extract final code
    final_code = result_state.get("current_code", "")

    # Write implementation files
    impl_file = src_dir / "implementation.py"
    with open(impl_file, "w", encoding="utf-8") as f:
        f.write(final_code)

    # Write code summary
    summary = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "iterations": result_state.get("iteration", 0) + 1,
        "approved": result_state.get("approved", False),
        "final_score": (
            result_state["reviews"][-1].get("score", 0)
            if result_state.get("reviews")
            else 0
        ),
        "proposal_count": len(result_state.get("proposals", [])),
        "review_count": len(result_state.get("reviews", [])),
    }

    summary_file = output_dir / "code_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(
        "implementer_workflow_success",
        run_id=run_id,
        impl_file=str(impl_file),
        summary_file=str(summary_file),
    )

    return {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "code": final_code,
        "summary": summary,
        "proposals": result_state.get("proposals", []),
        "reviews": result_state.get("reviews", []),
    }
