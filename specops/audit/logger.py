"""Append-only JSONL audit trail."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class AuditLogger:
    """Append-only JSONL audit trail for compliance and traceability."""

    def __init__(self, audit_file: str | Path):
        """
        Initialize audit logger.

        Args:
            audit_file: Path to JSONL audit file
        """
        self.audit_file = Path(audit_file)
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        run_id: str,
        stage: str,
        actor: str,
        event_type: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an audit event (append-only).

        Args:
            run_id: Run identifier
            stage: Pipeline stage
            actor: Who/what triggered event
            event_type: Event class
            status: Outcome status
            details: Event-specific metadata
        """
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "run_id": run_id,
            "stage": stage,
            "actor": actor,
            "event_type": event_type,
            "status": status,
            "details": details or {},
        }

        # Append to JSONL file (never overwrite)
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        logger.debug(
            "audit_event_logged",
            run_id=run_id,
            event_type=event_type,
            status=status,
        )

    def get_events(self, run_id: str | None = None) -> list[dict[str, Any]]:
        """
        Retrieve all audit events (optionally filtered by run_id).

        Args:
            run_id: Optional run ID to filter

        Returns:
            List of audit events
        """
        if not self.audit_file.exists():
            return []

        events = []
        with open(self.audit_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if run_id is None or event.get("run_id") == run_id:
                        events.append(event)
                except json.JSONDecodeError:
                    logger.warning("audit_line_decode_error", line=line[:50])

        return events

    def get_run_timeline(self, run_id: str) -> list[dict[str, Any]]:
        """
        Get chronological event timeline for a run.

        Args:
            run_id: Run identifier

        Returns:
            Sorted list of events
        """
        events = self.get_events(run_id)
        # Already in chronological order due to append-only design
        return events
