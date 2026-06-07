"""Approval checkpoints for the pipeline."""

from datetime import datetime
from typing import Any

import structlog
import typer

logger = structlog.get_logger(__name__)


class ApprovalCheckpoint:
    """Approval checkpoint with user confirmation."""

    def __init__(self, checkpoint_id: str, description: str):
        """
        Initialize checkpoint.

        Args:
            checkpoint_id: Unique identifier (e.g., "checkpoint_1")
            description: Human-readable description
        """
        self.checkpoint_id = checkpoint_id
        self.description = description

    def request_approval(self, details: dict[str, Any] | None = None) -> bool:
        """
        Request user approval via CLI prompt.

        Args:
            details: Additional context details to display

        Returns:
            True if approved, False if rejected
        """
        logger.info("approval_requested", checkpoint=self.checkpoint_id)

        print(f"\n{'=' * 70}")
        print(f"Approval Checkpoint: {self.checkpoint_id}")
        print(f"{'=' * 70}")
        print(f"\n{self.description}\n")

        if details:
            print("Details:")
            for key, value in details.items():
                if isinstance(value, list):
                    print(f"  {key}:")
                    for item in value:
                        print(f"    - {item}")
                else:
                    print(f"  {key}: {value}")
            print()

        approved = typer.confirm("Do you approve?", default=False)

        timestamp = datetime.utcnow().isoformat() + "Z"
        logger.info(
            "approval_decision",
            checkpoint=self.checkpoint_id,
            approved=approved,
            timestamp=timestamp,
        )

        return approved


class ApprovalManager:
    """Manages approval workflow for pipeline."""

    def __init__(self):
        """Initialize manager."""
        self.approvals: dict[str, bool] = {}
        self.checkpoints: dict[str, ApprovalCheckpoint] = {}

    def register_checkpoint(self, checkpoint_id: str, description: str) -> None:
        """Register an approval checkpoint."""
        self.checkpoints[checkpoint_id] = ApprovalCheckpoint(checkpoint_id, description)

    def request_approval(
        self,
        checkpoint_id: str,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """
        Request approval at a checkpoint.

        Args:
            checkpoint_id: ID of checkpoint
            details: Context details

        Returns:
            True if approved
        """
        if checkpoint_id not in self.checkpoints:
            raise ValueError(f"Unknown checkpoint: {checkpoint_id}")

        checkpoint = self.checkpoints[checkpoint_id]
        approved = checkpoint.request_approval(details)

        self.approvals[checkpoint_id] = approved
        return approved

    def is_approved(self, checkpoint_id: str) -> bool:
        """Check if checkpoint was approved."""
        return self.approvals.get(checkpoint_id, False)

    def all_approved(self) -> bool:
        """Check if all checkpoints are approved."""
        return all(self.approvals.values()) if self.approvals else False
