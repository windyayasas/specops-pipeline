"""FastAPI REST API for SpecOps Pipeline."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from specops.models.spec import SpecModel
from specops.observability.logging import bind_run_id, setup_logging
from specops.stages.implementer_agent import run_implementer_workflow
from specops.stages.intake import parse_spec_file
from specops.stages.planner_agent import run_planner_workflow
from specops.stages.test_gen_agent import run_test_gen_workflow
from specops.storage.run_store import RunStore

logger = structlog.get_logger(__name__)

# Setup logging
setup_logging(log_level="INFO", json_format=True)

app = FastAPI(
    title="SpecOps Pipeline API",
    description="Multi-agent AI-native spec-driven development pipeline",
    version="0.1.0",
)


class RunRequest(BaseModel):
    """Request to start a new pipeline run."""

    spec_file: str
    """Path to spec file"""

    run_id: Optional[str] = None
    """Custom run ID (auto-generated if not provided)"""

    auto_approve: bool = False
    """Skip approval checkpoints"""


class RunResponse(BaseModel):
    """Response from run start."""

    run_id: str
    timestamp: str
    status: str


class RunStatus(BaseModel):
    """Run status response."""

    run_id: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    plan: Optional[dict[str, Any]] = None
    code_summary: Optional[dict[str, Any]] = None


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "specops-pipeline"}


@app.post("/runs", response_model=RunResponse)
def create_run(request: RunRequest) -> RunResponse:
    """
    Start a new pipeline run.

    Args:
        request: Run request with spec file path

    Returns:
        Run metadata with ID and status
    """
    try:
        # Generate run ID
        run_id = request.run_id or f"run_{uuid.uuid4().hex[:8]}"
        bind_run_id(run_id)

        logger.info("api_run_starting", spec_file=request.spec_file, run_id=run_id)

        # Create output directory
        output_dir = Path("outputs") / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Parse spec
        spec = parse_spec_file(request.spec_file)

        # Run planner
        plan_output = run_planner_workflow(spec, run_id=run_id, output_dir=output_dir)
        plan = plan_output["plan"]

        # Run implementer
        impl_output = run_implementer_workflow(
            spec,
            plan,
            run_id=run_id,
            output_dir=output_dir,
        )

        # Run test generation
        test_output = run_test_gen_workflow(
            spec,
            impl_output["code"],
            run_id=run_id,
            output_dir=output_dir,
        )

        # Save state
        store = RunStore(output_dir)
        state = {
            "run_id": run_id,
            "status": "QUALITY_PASS",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "plan": plan,
            "code_summary": impl_output.get("summary"),
            "test_summary": test_output.get("summary"),
        }
        store.save_state(state)

        logger.info("api_run_success", run_id=run_id)

        return RunResponse(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            status="INITIATED",
        )

    except Exception as e:
        logger.error("api_run_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Run failed: {str(e)}")


@app.get("/runs/{run_id}", response_model=RunStatus)
def get_run_status(run_id: str) -> RunStatus:
    """
    Get status of a pipeline run.

    Args:
        run_id: Run identifier

    Returns:
        Current run status and metadata
    """
    try:
        output_dir = Path("outputs") / run_id
        store = RunStore(output_dir)

        state = store.load_state()
        if state is None:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

        logger.info("api_run_status_retrieved", run_id=run_id)

        return RunStatus(
            run_id=run_id,
            status=state.get("status", "UNKNOWN"),
            created_at=state.get("created_at"),
            updated_at=state.get("updated_at"),
            plan=state.get("plan"),
            code_summary=state.get("code_summary"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("api_get_run_status_failed", run_id=run_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")


@app.post("/runs/{run_id}/approve")
def approve_run(run_id: str, checkpoint: int = Query(1, ge=1, le=2)) -> dict[str, str]:
    """
    Approve a pipeline run at a checkpoint.

    Args:
        run_id: Run identifier
        checkpoint: Checkpoint number (1 or 2)

    Returns:
        Approval confirmation
    """
    try:
        output_dir = Path("outputs") / run_id
        store = RunStore(output_dir)

        state = store.load_state()
        if state is None:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

        # Update approvals
        if "approvals" not in state:
            state["approvals"] = {}

        checkpoint_key = f"checkpoint_{checkpoint}"
        state["approvals"][checkpoint_key] = True
        state["updated_at"] = datetime.utcnow().isoformat() + "Z"

        store.save_state(state)

        logger.info("api_run_approved", run_id=run_id, checkpoint=checkpoint)

        return {
            "run_id": run_id,
            "checkpoint": checkpoint_key,
            "approved": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("api_approve_run_failed", run_id=run_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@app.get("/runs/{run_id}/audit")
def get_run_audit(run_id: str) -> dict[str, Any]:
    """
    Get audit trail for a run.

    Args:
        run_id: Run identifier

    Returns:
        Audit events timeline
    """
    try:
        output_dir = Path("outputs") / run_id
        audit_file = output_dir / ".audit.jsonl"

        if not audit_file.exists():
            return {"run_id": run_id, "events": []}

        # Read JSONL audit file
        import json

        events = []
        with open(audit_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

        logger.info("api_audit_retrieved", run_id=run_id, event_count=len(events))

        return {"run_id": run_id, "events": events}

    except Exception as e:
        logger.error("api_get_audit_failed", run_id=run_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Audit retrieval failed: {str(e)}")


@app.get("/runs", response_model=dict[str, list[str]])
def list_runs() -> dict[str, list[str]]:
    """
    List all available runs.

    Returns:
        List of run IDs
    """
    try:
        base_path = Path("outputs")
        if not base_path.exists():
            return {"runs": []}

        runs = sorted([d.name for d in base_path.iterdir() if d.is_dir()])

        logger.info("api_list_runs", count=len(runs))

        return {"runs": runs}

    except Exception as e:
        logger.error("api_list_runs_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")
