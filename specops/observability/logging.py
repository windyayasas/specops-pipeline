"""Structured logging with Structlog."""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# Context variable to hold the current run_id for propagation
_run_id_context: ContextVar[str | None] = ContextVar("run_id", default=None)


def bind_run_id(run_id: str) -> None:
    """
    Bind a run_id to the current context.

    This will be automatically included in all subsequent log messages.
    """
    _run_id_context.set(run_id)


def clear_run_id() -> None:
    """Clear the current run_id from context."""
    _run_id_context.set(None)


def get_run_id() -> str | None:
    """Get the current run_id from context."""
    return _run_id_context.get()


def _add_run_id(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add run_id to log events if set."""
    run_id = get_run_id()
    if run_id:
        event_dict["run_id"] = run_id
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = True,
) -> None:
    """
    Configure structured logging with Structlog.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output JSON; otherwise use dev-friendly format
    """
    # Convert string level to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging first
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            _add_run_id,  # Always add run_id if available
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if json_format else _dev_renderer,
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _dev_renderer(logger: Any, method_name: str, event_dict: dict[str, Any]) -> str:
    """Human-friendly development renderer for logs."""
    timestamp = event_dict.pop("timestamp", "")
    level = event_dict.pop("level", "info").upper()
    run_id = event_dict.pop("run_id", "")

    # Build prefix
    prefix = f"[{timestamp}] [{level}]"
    if run_id:
        prefix += f" [run_id: {run_id}]"

    # Extract event message
    event = event_dict.pop("event", "")
    msg = f"{prefix} {event}"

    # Append remaining context as JSON
    if event_dict:
        msg += " " + json.dumps(event_dict, default=str)

    return msg


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a named logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structlog BoundLogger instance
    """
    return structlog.get_logger(name)
