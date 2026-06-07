"""Tests package."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_spec_json(tmp_path: Path) -> Path:
    """Create a sample JSON spec file."""
    spec = {
        "featureObjective": "Implement health check endpoint",
        "userStory": "As a DevOps engineer, I want a health endpoint",
        "businessRules": ["Read-only", "No database calls"],
        "acceptanceCriteria": ["GET /health returns 200"],
        "nonFunctionalRequirements": ["p95 latency < 50ms"],
        "outOfScope": ["Deep dependency checks"],
    }
    spec_file = tmp_path / "spec.json"
    with open(spec_file, "w") as f:
        json.dump(spec, f)
    return spec_file


@pytest.fixture
def sample_spec_yaml(tmp_path: Path) -> Path:
    """Create a sample YAML spec file."""
    spec_yaml = """
featureObjective: Implement health check endpoint
userStory: As a DevOps engineer, I want a health endpoint
businessRules:
  - Read-only
  - No database calls
acceptanceCriteria:
  - GET /health returns 200
nonFunctionalRequirements:
  - p95 latency < 50ms
outOfScope:
  - Deep dependency checks
"""
    spec_file = tmp_path / "spec.yaml"
    with open(spec_file, "w") as f:
        f.write(spec_yaml)
    return spec_file


@pytest.fixture
def sample_spec_markdown(tmp_path: Path) -> Path:
    """Create a sample Markdown spec file with YAML frontmatter."""
    spec_md = """---
featureObjective: Implement health check endpoint
userStory: As a DevOps engineer, I want a health endpoint
businessRules:
  - Read-only
  - No database calls
acceptanceCriteria:
  - GET /health returns 200
nonFunctionalRequirements:
  - p95 latency < 50ms
outOfScope:
  - Deep dependency checks
---

# Health Check Endpoint

This endpoint provides health status information.
"""
    spec_file = tmp_path / "spec.md"
    with open(spec_file, "w") as f:
        f.write(spec_md)
    return spec_file
