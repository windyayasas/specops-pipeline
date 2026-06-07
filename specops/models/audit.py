"""Audit trail models for compliance and traceability."""

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """Single audit event in the execution trail."""

    timestamp: str = Field(
        ...,
        description="ISO 8601 event timestamp",
    )
    run_id: str = Field(
        ...,
        description="Unique identifier for the run",
    )
    stage: str = Field(
        ...,
        description="Pipeline stage (intake, planner, implementer, test_gen, quality, approval, etc.)",
    )
    actor: str = Field(
        ...,
        description="Who/what triggered the event (user, system, agent_name)",
    )
    event_type: str = Field(
        ...,
        description="Event class (spec_loaded, plan_generated, proposal_created, review_feedback, etc.)",
    )
    status: str = Field(
        ...,
        description="Outcome status (success, failure, pending, approved, rejected)",
    )
    details: dict = Field(
        default_factory=dict,
        description="Event-specific metadata (prompt_hash, iteration, feedback, etc.)",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "timestamp": "2024-01-15T10:30:45Z",
                "run_id": "run_abc123",
                "stage": "planner",
                "actor": "system",
                "event_type": "plan_generated",
                "status": "success",
                "details": {
                    "prompt_hash": "sha256_...",
                    "task_count": 5,
                    "duration_ms": 2500,
                },
            }
        }
