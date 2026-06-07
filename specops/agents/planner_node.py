"""Planner agent node."""

import json
from typing import Any

import structlog

from specops.agents.state_graphs import PlannerState
from specops.config import get_settings
from specops.llm.client import GroqClient
from specops.llm.prompts import render_planner_prompt
from specops.models.plan import PlanOutput

logger = structlog.get_logger(__name__)


def planner_node(state: PlannerState) -> PlannerState:
    """
    Planner agent node: converts spec to implementation plan.

    Args:
        state: PlannerState with spec

    Returns:
        Updated state with generated plan

    Raises:
        RuntimeError: If LLM call fails
        ValueError: If plan JSON parsing fails
    """
    spec = state["spec"]
    settings = get_settings()

    logger.info(
        "planner_node_starting",
        feature=spec.get("feature_objective", "")[:50],
    )

    # Initialize Groq client
    client = GroqClient(api_key=settings.groq_api_key)

    # Render prompt
    prompt = render_planner_prompt(
        feature_objective=spec.get("feature_objective", ""),
        user_story=spec.get("user_story", ""),
        business_rules=spec.get("business_rules", []),
        acceptance_criteria=spec.get("acceptance_criteria", []),
        non_functional_requirements=spec.get("non_functional_requirements", []),
        out_of_scope=spec.get("out_of_scope", []),
    )

    # Call LLM
    try:
        plan_json = client.json_call(
            prompt=prompt,
            system_prompt="You are an expert architect creating implementation plans.",
            temperature=0.5,
            max_tokens=3000,
        )
    except (RuntimeError, ValueError) as e:
        logger.error("planner_llm_call_failed", error=str(e))
        raise

    # Validate plan structure
    try:
        plan_output = PlanOutput(**plan_json)
        plan_dict = plan_output.model_dump()

        logger.info(
            "planner_node_success",
            task_count=len(plan_dict.get("tasks", [])),
        )

        state["plan"] = plan_dict
        return state

    except Exception as e:
        logger.error(
            "planner_plan_validation_failed",
            error=str(e),
            plan_json=plan_json,
        )
        raise
