"""Plan and run state models."""

from pydantic import BaseModel, Field


class PlanOutput(BaseModel):
    """Output from the planner agent."""

    tasks: list[str] = Field(
        ...,
        description="Ordered list of implementation tasks",
    )
    design_summary: str = Field(
        ...,
        description="High-level design approach",
    )
    impacted_modules: list[str] = Field(
        default_factory=list,
        description="Modules or files expected to be modified/created",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Identified risks and mitigations",
    )
    test_strategy: str = Field(
        ...,
        description="Testing approach (unit, integration, acceptance)",
    )


class RunState(BaseModel):
    """Pipeline run execution state."""

    status: str = Field(
        ...,
        description=(
            "Current status: CREATED, PLAN_APPROVED, IMPLEMENTATION_IN_PROGRESS, "
            "TESTS_IN_PROGRESS, QUALITY_PASS, APPROVAL_2_APPROVED, DEPLOYED, FAILED"
        ),
    )
    created_at: str = Field(
        ...,
        description="ISO 8601 creation timestamp",
    )
    updated_at: str = Field(
        ...,
        description="ISO 8601 last update timestamp",
    )
    approvals: dict[str, bool] = Field(
        default_factory=dict,
        description="Approval checkpoints (e.g., 'checkpoint_1': True, 'checkpoint_2': False)",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status": "PLAN_APPROVED",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:00Z",
                "approvals": {"checkpoint_1": True, "checkpoint_2": False},
            }
        }
