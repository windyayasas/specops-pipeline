"""Planner agent workflow orchestration."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from specops.agents.planner_node import planner_node
from specops.agents.state_graphs import PlannerState
from specops.models.spec import SpecModel

logger = structlog.get_logger(__name__)


def build_planner_graph() -> Any:
    """
    Build and compile the planner workflow graph.

    Returns:
        Compiled LangGraph workflow
    """
    graph = StateGraph(PlannerState)

    # Add single planner node
    graph.add_node("planner", planner_node)

    # Start → Planner → End
    graph.set_entry_point("planner")
    graph.add_edge("planner", END)

    return graph.compile()


def run_planner_workflow(
    spec: SpecModel,
    run_id: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Execute planner workflow: spec → plan.

    Args:
        spec: Validated SpecModel
        run_id: Run identifier (generated if not provided)
        output_dir: Directory to write outputs (default: ./outputs/{run_id}/)

    Returns:
        Plan output dict with metadata

    Raises:
        RuntimeError: If planner fails
    """
    if run_id is None:
        run_id = f"run_{uuid.uuid4().hex[:8]}"

    output_dir = Path("outputs") / run_id if output_dir is None else Path(output_dir)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("planner_workflow_starting", run_id=run_id)

    # Build and compile graph
    graph = build_planner_graph()

    # Prepare initial state
    initial_state: PlannerState = {
        "spec": spec.model_dump(),
        "plan": {},
    }

    # Run workflow
    try:
        result_state = graph.invoke(initial_state)
    except Exception as e:
        logger.error("planner_workflow_failed", run_id=run_id, error=str(e))
        raise RuntimeError(f"Planner workflow failed: {e}") from e

    # Extract plan
    plan = result_state.get("plan", {})

    # Prepare output with metadata
    output = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "plan": plan,
    }

    # Write plan.json
    plan_file = output_dir / "plan.json"
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    logger.info(
        "planner_workflow_success",
        run_id=run_id,
        output_file=str(plan_file),
    )

    return output
