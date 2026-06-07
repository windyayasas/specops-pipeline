"""Jinja2 prompt templates for agents."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template

# Initialize Jinja2 environment
_TEMPLATE_DIR = Path(__file__).parent / "prompts"

# Create directory if it doesn't exist
_TEMPLATE_DIR.mkdir(exist_ok=True)

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_template(name: str) -> Template:
    """Get a prompt template by name."""
    return _env.get_template(name)


def render_planner_prompt(
    feature_objective: str,
    user_story: str,
    business_rules: list[str],
    acceptance_criteria: list[str],
    non_functional_requirements: list[str],
    out_of_scope: list[str],
) -> str:
    """Render planner agent prompt."""
    tmpl = get_template("planner_prompt.j2")
    return tmpl.render(
        feature_objective=feature_objective,
        user_story=user_story,
        business_rules=business_rules,
        acceptance_criteria=acceptance_criteria,
        non_functional_requirements=non_functional_requirements,
        out_of_scope=out_of_scope,
    )


def render_proposer_prompt(
    feature_objective: str,
    user_story: str,
    business_rules: list[str],
    acceptance_criteria: list[str],
    non_functional_requirements: list[str],
    plan_tasks: list[str],
    design_summary: str,
) -> str:
    """Render code proposer agent prompt."""
    tmpl = get_template("proposer_prompt.j2")
    return tmpl.render(
        feature_objective=feature_objective,
        user_story=user_story,
        business_rules=business_rules,
        acceptance_criteria=acceptance_criteria,
        non_functional_requirements=non_functional_requirements,
        plan_tasks=plan_tasks,
        design_summary=design_summary,
    )


def render_reviewer_prompt(
    proposal: str,
    feature_objective: str,
    acceptance_criteria: list[str],
) -> str:
    """Render code reviewer agent prompt."""
    tmpl = get_template("reviewer_prompt.j2")
    return tmpl.render(
        proposal=proposal,
        feature_objective=feature_objective,
        acceptance_criteria=acceptance_criteria,
    )


def render_refiner_prompt(
    proposal: str,
    feedback: str,
) -> str:
    """Render code refiner agent prompt."""
    tmpl = get_template("refiner_prompt.j2")
    return tmpl.render(
        proposal=proposal,
        feedback=feedback,
    )


def render_test_proposer_prompt(
    code: str,
    acceptance_criteria: list[str],
    feature_objective: str,
) -> str:
    """Render test proposer agent prompt."""
    tmpl = get_template("test_proposer_prompt.j2")
    return tmpl.render(
        code=code,
        acceptance_criteria=acceptance_criteria,
        feature_objective=feature_objective,
    )


def render_test_validator_prompt(
    tests: str,
    code: str,
    acceptance_criteria: list[str],
) -> str:
    """Render test validator agent prompt."""
    tmpl = get_template("test_validator_prompt.j2")
    return tmpl.render(
        tests=tests,
        code=code,
        acceptance_criteria=acceptance_criteria,
    )
