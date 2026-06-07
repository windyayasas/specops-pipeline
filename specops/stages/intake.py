"""Spec intake and parsing utilities."""

import json
from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import ValidationError

from specops.models.spec import SpecModel

logger = structlog.get_logger(__name__)


def _normalize_spec_keys(spec: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize camelCase spec keys to snake_case for Pydantic validation.

    Handles both camelCase (from JSON) and snake_case (already normalized).
    """
    key_mapping = {
        "featureObjective": "feature_objective",
        "userStory": "user_story",
        "businessRules": "business_rules",
        "acceptanceCriteria": "acceptance_criteria",
        "nonFunctionalRequirements": "non_functional_requirements",
        "outOfScope": "out_of_scope",
    }

    normalized = {}
    for key, value in spec.items():
        # Map camelCase to snake_case, or keep as-is if already snake_case
        new_key = key_mapping.get(key, key)
        normalized[new_key] = value

    return normalized


def parse_spec_file(file_path: str | Path) -> SpecModel:
    """
    Parse a specification file (JSON, YAML, or Markdown with YAML frontmatter).

    Args:
        file_path: Path to spec file

    Returns:
        Validated SpecModel instance

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If format is unsupported or parsing fails
        ValidationError: If spec doesn't match schema
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Spec file not found: {file_path}")

    suffix = file_path.suffix.lower()

    try:
        if suffix == ".json":
            spec_dict = _parse_json(file_path)
        elif suffix in (".yaml", ".yml"):
            spec_dict = _parse_yaml(file_path)
        elif suffix in (".md", ".markdown"):
            spec_dict = _parse_markdown(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        # Normalize keys
        spec_dict = _normalize_spec_keys(spec_dict)

        # Validate against SpecModel
        spec = SpecModel(**spec_dict)

        logger.info(
            "spec_parsed_successfully",
            file=str(file_path),
            feature_objective=spec.feature_objective[:50] + "...",
        )

        return spec

    except json.JSONDecodeError as e:
        logger.error("json_parse_error", file=str(file_path), error=str(e))
        raise ValueError(f"Invalid JSON in {file_path}: {e}") from e
    except yaml.YAMLError as e:
        logger.error("yaml_parse_error", file=str(file_path), error=str(e))
        raise ValueError(f"Invalid YAML in {file_path}: {e}") from e
    except ValidationError as e:
        logger.error(
            "spec_validation_error",
            file=str(file_path),
            errors=e.errors(),
        )
        # Include field paths in error message
        error_msg = "Spec validation failed:\n"
        for error in e.errors():
            field = ".".join(str(x) for x in error["loc"])
            error_msg += f"  - {field}: {error['msg']}\n"
        raise ValueError(error_msg) from e


def _parse_json(file_path: Path) -> dict[str, Any]:
    """Parse JSON file."""
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def _parse_yaml(file_path: Path) -> dict[str, Any]:
    """Parse YAML file."""
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("YAML root must be an object/mapping")
        return data


def _parse_markdown(file_path: Path) -> dict[str, Any]:
    """Parse Markdown file with YAML frontmatter."""
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Check for YAML frontmatter (--- at start and somewhere in middle)
    if not content.startswith("---"):
        raise ValueError("Markdown file must start with --- for YAML frontmatter")

    # Find closing ---
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Markdown frontmatter not properly closed")

    frontmatter = parts[1].strip()
    data = yaml.safe_load(frontmatter)

    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter root must be an object/mapping")

    return data
