"""Test generation agent nodes: test_proposer and test_validator."""

import json
import re
from typing import Any

import structlog

from specops.agents.state_graphs import TestGenState
from specops.config import get_settings
from specops.llm.client import GroqClient
from specops.llm.prompts import (
    render_test_proposer_prompt,
    render_test_validator_prompt,
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


def test_proposer_node(state: TestGenState) -> TestGenState:
    """
    Test proposer node: generates unit and integration tests.

    Args:
        state: TestGenState with code and acceptance criteria

    Returns:
        Updated state with test proposal and test_proposals list
    """
    code = state["code"]
    acceptance_criteria = state["acceptance_criteria"]
    spec = state["spec"]
    iteration = state["iteration"]
    settings = get_settings()

    logger.info("test_proposer_node_starting", iteration=iteration)

    client = GroqClient(api_key=settings.groq_api_key)

    # Render prompt
    prompt = render_test_proposer_prompt(
        code=code,
        acceptance_criteria=acceptance_criteria,
        feature_objective=spec.get("feature_objective", ""),
    )

    # Call LLM to generate tests
    try:
        tests_response = client.call(
            prompt=prompt,
            system_prompt="You are an expert test engineer. Write comprehensive pytest tests with good coverage.",
            temperature=0.6,
            max_tokens=4096,
        )
        # Extract tests from markdown if wrapped
        tests = extract_code_from_markdown(tests_response)
    except RuntimeError as e:
        logger.error("test_proposer_llm_call_failed", iteration=iteration, error=str(e))
        raise

    # Store proposal
    proposal = {
        "iteration": iteration,
        "tests": tests,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }
    state["test_proposals"].append(proposal)

    logger.info(
        "test_proposer_node_success",
        iteration=iteration,
        tests_length=len(tests),
    )

    return state


def test_validator_node(state: TestGenState) -> TestGenState:
    """
    Test validator node: validates test coverage vs acceptance criteria.

    Args:
        state: TestGenState with generated tests

    Returns:
        Updated state with validation feedback and complete flag
    """
    code = state["code"]
    acceptance_criteria = state["acceptance_criteria"]
    iteration = state["iteration"]

    # Get latest test proposal
    latest_proposal = state["test_proposals"][-1] if state["test_proposals"] else {}
    tests = latest_proposal.get("tests", "")

    settings = get_settings()

    logger.info("test_validator_node_starting", iteration=iteration)

    client = GroqClient(api_key=settings.groq_api_key)

    # Render prompt
    prompt = render_test_validator_prompt(
        tests=tests,
        code=code,
        acceptance_criteria=acceptance_criteria,
    )

    # Call LLM to validate
    try:
        validation_json = client.json_call(
            prompt=prompt,
            system_prompt="You are a QA engineer evaluating test coverage and quality.",
            temperature=0.3,
            max_tokens=2000,
        )
    except (RuntimeError, ValueError) as e:
        logger.error("test_validator_llm_call_failed", iteration=iteration, error=str(e))
        raise

    # Extract validation results
    valid = validation_json.get("valid", False)
    coverage_score = validation_json.get("coverage_score", 0)
    criteria_coverage = validation_json.get("criteria_coverage", [])
    feedback = validation_json.get("feedback", "")

    # Store feedback
    feedback_record = {
        "iteration": iteration,
        "valid": valid,
        "coverage_score": coverage_score,
        "criteria_coverage": criteria_coverage,
        "feedback": feedback,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }
    state["validation_feedback"].append(feedback_record)

    # Check if complete
    complete = valid or iteration >= (get_settings().max_test_iterations - 1)
    state["complete"] = complete

    if complete:
        state["final_tests"] = tests

    logger.info(
        "test_validator_node_success",
        iteration=iteration,
        valid=valid,
        coverage_score=coverage_score,
        complete=complete,
    )

    return state
