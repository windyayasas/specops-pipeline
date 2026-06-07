"""Implementer agent nodes: proposer, reviewer, refiner."""

import re

import structlog

from specops.agents.state_graphs import ImplementerState
from specops.config import get_settings
from specops.llm.client import GroqClient
from specops.llm.prompts import (
    render_proposer_prompt,
    render_refiner_prompt,
    render_reviewer_prompt,
)

logger = structlog.get_logger(__name__)


def extract_code_from_markdown(text: str, language: str = "python") -> str:
    """
    Extract code from markdown code blocks.

    Handles:
    - ```python ... ```
    - ```{language} ... ```
    - ``` ... ```

    Args:
        text: Text potentially containing markdown code blocks
        language: Code language to look for (default: python)

    Returns:
        Extracted code or original text if no blocks found
    """
    # Try to extract from ```python ... ``` blocks
    pattern = rf"```(?:{language})?\n(.*?)\n```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # If no markdown blocks, return as-is
    return text.strip()


def proposer_node(state: ImplementerState) -> ImplementerState:
    """
    Code proposer node: generates code proposal based on spec and plan.

    Args:
        state: ImplementerState with spec, plan, and current iteration

    Returns:
        Updated state with current_code and proposals list updated
    """
    spec = state["spec"]
    plan = state["plan"]
    iteration = state["iteration"]
    settings = get_settings()

    logger.info(
        "proposer_node_starting",
        iteration=iteration,
    )

    client = GroqClient(api_key=settings.groq_api_key)

    # Render prompt
    prompt = render_proposer_prompt(
        feature_objective=spec.get("feature_objective", ""),
        user_story=spec.get("user_story", ""),
        business_rules=spec.get("business_rules", []),
        acceptance_criteria=spec.get("acceptance_criteria", []),
        non_functional_requirements=spec.get("non_functional_requirements", []),
        plan_tasks=plan.get("tasks", []),
        design_summary=plan.get("design_summary", ""),
    )

    # Call LLM to generate code
    try:
        code_response = client.call(
            prompt=prompt,
            system_prompt="You are an expert Python engineer. Write clean, production-quality code with type hints and docstrings.",
            temperature=0.7,
            max_tokens=4096,
        )
        # Extract code from markdown if wrapped
        code = extract_code_from_markdown(code_response)
    except RuntimeError as e:
        logger.error("proposer_llm_call_failed", iteration=iteration, error=str(e))
        raise

    # Store proposal
    proposal = {
        "iteration": iteration,
        "code": code,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }
    state["proposals"].append(proposal)
    state["current_code"] = code

    logger.info(
        "proposer_node_success",
        iteration=iteration,
        code_length=len(code),
    )

    return state


def reviewer_node(state: ImplementerState) -> ImplementerState:
    """
    Code reviewer node: reviews proposal and provides verdict + feedback.

    Args:
        state: ImplementerState with current_code

    Returns:
        Updated state with review feedback and approved flag
    """
    spec = state["spec"]
    code = state["current_code"]
    iteration = state["iteration"]
    settings = get_settings()

    logger.info("reviewer_node_starting", iteration=iteration)

    client = GroqClient(api_key=settings.groq_api_key)

    # Render prompt
    prompt = render_reviewer_prompt(
        proposal=code,
        feature_objective=spec.get("feature_objective", ""),
        acceptance_criteria=spec.get("acceptance_criteria", []),
    )

    # Call LLM to review
    try:
        review_json = client.json_call(
            prompt=prompt,
            system_prompt="You are a rigorous code reviewer. Evaluate code against acceptance criteria.",
            temperature=0.3,
            max_tokens=2000,
        )
    except (RuntimeError, ValueError) as e:
        logger.error("reviewer_llm_call_failed", iteration=iteration, error=str(e))
        raise

    # Extract approval and feedback
    approved = review_json.get("approved", False)
    score = review_json.get("score", 0)
    issues = review_json.get("issues", [])
    feedback = review_json.get("feedback", "")

    # Store review
    review = {
        "iteration": iteration,
        "approved": approved,
        "score": score,
        "issues": issues,
        "feedback": feedback,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }
    state["reviews"].append(review)
    state["approved"] = approved

    logger.info(
        "reviewer_node_success",
        iteration=iteration,
        approved=approved,
        score=score,
        issue_count=len(issues),
    )

    return state


def refiner_node(state: ImplementerState) -> ImplementerState:
    """
    Code refiner node: refines code based on review feedback.

    Args:
        state: ImplementerState with current_code and latest review feedback

    Returns:
        Updated state with refined current_code
    """
    code = state["current_code"]
    iteration = state["iteration"]
    settings = get_settings()

    # Get latest review feedback
    latest_review = state["reviews"][-1] if state["reviews"] else {}
    feedback = latest_review.get("feedback", "")

    logger.info("refiner_node_starting", iteration=iteration)

    client = GroqClient(api_key=settings.groq_api_key)

    # Render prompt
    prompt = render_refiner_prompt(proposal=code, feedback=feedback)

    # Call LLM to refine
    try:
        refined_code = client.call(
            prompt=prompt,
            system_prompt="You are an expert Python engineer. Refine code based on feedback, maintaining quality and clarity.",
            temperature=0.5,
            max_tokens=4096,
        )
    except RuntimeError as e:
        logger.error("refiner_llm_call_failed", iteration=iteration, error=str(e))
        raise

    state["current_code"] = refined_code

    logger.info(
        "refiner_node_success",
        iteration=iteration,
        refined_code_length=len(refined_code),
    )

    return state
