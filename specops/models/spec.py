"""Pydantic models for specification validation."""

from typing import Any, ClassVar

from pydantic import BaseModel, Field


class SpecModel(BaseModel):
    """Represents a feature specification."""

    feature_objective: str = Field(..., description="High-level feature objective")
    user_story: str = Field(..., description="User-centric story description")
    business_rules: list[str] = Field(
        default_factory=list,
        description="Business logic constraints",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Testable acceptance criteria",
    )
    non_functional_requirements: list[str] = Field(
        default_factory=list,
        description="NFRs (performance, security, reliability, etc.)",
    )
    out_of_scope: list[str] = Field(
        default_factory=list,
        description="Explicitly out-of-scope items",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "feature_objective": "Implement health check endpoint",
                "user_story": "As a DevOps engineer...",
                "business_rules": ["Must be read-only", "No database calls"],
                "acceptance_criteria": [
                    "GET /health returns 200 with status=ok"
                ],
                "non_functional_requirements": ["p95 latency < 50ms"],
                "out_of_scope": ["Deep dependency checks"],
            }
        }
