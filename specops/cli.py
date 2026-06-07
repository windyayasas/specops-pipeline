"""CLI interface for SpecOps Pipeline using Typer."""

from pathlib import Path

import typer

from specops.observability.logging import bind_run_id, get_logger, setup_logging
from specops.stages.approval import ApprovalManager
from specops.stages.implementer_agent import run_implementer_workflow
from specops.stages.intake import parse_spec_file
from specops.stages.planner_agent import run_planner_workflow
from specops.stages.quality_gate import QualityGateError, run_quality_gate
from specops.stages.test_gen_agent import run_test_gen_workflow
from specops.storage.run_store import RunStore

logger = get_logger(__name__)

app = typer.Typer(
    name="specops",
    help="SpecOps: Multi-agent AI-native spec-driven development pipeline",
)


def setup_app_logging() -> None:
    """Initialize application logging."""
    setup_logging(log_level="INFO", json_format=False)


@app.command()
def run(
    spec_file: str = typer.Argument(
        ...,
        help="Path to spec file (JSON, YAML, or Markdown with YAML frontmatter)",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory (default: ./outputs/{run_id})",
    ),
    skip_approval: bool = typer.Option(
        False,
        "--skip-approval",
        help="Skip approval checkpoints (CI mode)",
    ),
    run_id: str | None = typer.Option(
        None,
        "--run-id",
        help="Custom run ID (default: auto-generated)",
    ),
) -> None:
    """
    Execute the full pipeline: spec → plan → implement → test → quality → deploy.
    """
    setup_app_logging()

    try:
        # Parse spec
        logger.info("cli_run_starting", spec_file=spec_file)
        spec = parse_spec_file(spec_file)

        # Determine output directory
        if output_dir is None:
            from uuid import uuid4

            run_id = run_id or f"run_{uuid4().hex[:8]}"
            output_dir_path = Path("outputs") / run_id
        else:
            output_dir_path = Path(output_dir)
            run_id = run_id or output_dir_path.name

        bind_run_id(run_id)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        # Initialize run store and approvals
        store = RunStore(output_dir_path)
        approvals = ApprovalManager()
        approvals.register_checkpoint(
            "checkpoint_1",
            "Review implementation plan before coding begins.",
        )
        approvals.register_checkpoint(
            "checkpoint_2",
            "Review code quality report before deployment.",
        )

        # Phase 1: Planner
        logger.info("cli_planner_starting")
        plan_output = run_planner_workflow(spec, run_id=run_id, output_dir=output_dir_path)
        plan = plan_output["plan"]

        # Approval checkpoint 1
        if not skip_approval:
            details = {
                "Tasks": plan.get("tasks", [])[:3],  # First 3 tasks
                "Design": plan.get("design_summary", "")[:200],
                "Risks": plan.get("risks", [])[:2],
            }
            if not approvals.request_approval("checkpoint_1", details):
                logger.error("cli_checkpoint_1_rejected")
                typer.echo("\nPipeline cancelled at approval checkpoint 1.", err=True)
                raise typer.Exit(code=1)
        logger.info("cli_checkpoint_1_approved")

        # Phase 2: Implementer
        logger.info("cli_implementer_starting")
        impl_output = run_implementer_workflow(
            spec,
            plan,
            run_id=run_id,
            output_dir=output_dir_path,
        )
        code = impl_output["code"]

        # Phase 3: Test Generation
        logger.info("cli_test_gen_starting")
        test_output = run_test_gen_workflow(
            spec,
            code,
            run_id=run_id,
            output_dir=output_dir_path,
        )

        # Phase 4: Quality Gates
        logger.info("cli_quality_gate_starting")
        try:
            quality_report = run_quality_gate(
                code_path=output_dir_path / "src",
                test_path=output_dir_path / "tests",
                output_file=output_dir_path / "quality_report.json",
            )
            logger.info("cli_quality_gate_passed")
        except QualityGateError as e:
            logger.error("cli_quality_gate_failed", error=str(e))
            if not skip_approval:
                typer.echo(f"\nQuality gate failed: {e}", err=True)
                raise typer.Exit(code=1) from None

        # Approval checkpoint 2
        if not skip_approval:
            details = {
                "Quality Score": f"{quality_report.get('results', {}).get('ruff', {}).get('passed', False)}",
                "Tests Passed": f"{quality_report.get('results', {}).get('pytest', {}).get('passed', False)}",
                "Security Issues": len(quality_report.get("results", {}).get("bandit", {}).get("issues", [])),
            }
            if not approvals.request_approval("checkpoint_2", details):
                logger.error("cli_checkpoint_2_rejected")
                typer.echo("\nPipeline cancelled at approval checkpoint 2.", err=True)
                raise typer.Exit(code=1)
        logger.info("cli_checkpoint_2_approved")

        # Save final state
        final_state = {
            "status": "DEPLOYED",
            "run_id": run_id,
            "plan": plan,
            "code_summary": impl_output.get("summary"),
            "test_summary": test_output.get("summary"),
            "quality_report": quality_report,
        }
        store.save_state(final_state)

        logger.info("cli_run_success", run_id=run_id)
        typer.echo(f"\n✅ Pipeline completed successfully! Run ID: {run_id}")
        typer.echo(f"📁 Outputs: {output_dir_path}")

    except Exception as e:
        logger.error("cli_run_failed", error=str(e), exc_info=True)
        typer.echo(f"\n❌ Pipeline failed: {e}", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def status(
    run_id: str = typer.Argument(..., help="Run ID to check"),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory",
    ),
) -> None:
    """Check status of a pipeline run."""
    setup_app_logging()

    try:
        output_dir_path = Path("outputs") / run_id if output_dir is None else Path(output_dir)

        store = RunStore(output_dir_path)
        state = store.load_state()

        if state is None:
            typer.echo(f"No run state found for {run_id}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"\nRun ID: {state.get('run_id', run_id)}")
        typer.echo(f"Status: {state.get('status', 'UNKNOWN')}")

        if "plan" in state:
            plan = state["plan"]
            typer.echo("\n📋 Plan:")
            typer.echo(f"  Tasks: {len(plan.get('tasks', []))}")
            typer.echo(f"  Design: {plan.get('design_summary', '')[:100]}...")

        if "code_summary" in state:
            typer.echo("\n💻 Code:")
            typer.echo(f"  Iterations: {state['code_summary'].get('iterations', 0)}")
            typer.echo(f"  Approved: {state['code_summary'].get('approved', False)}")

    except Exception as e:
        logger.error("cli_status_failed", error=str(e))
        typer.echo(f"\n❌ Status check failed: {e}", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def list_runs(
    output_base: str | None = typer.Option(
        "outputs",
        "--output-dir",
        "-o",
        help="Base output directory",
    ),
) -> None:
    """List all available runs."""
    setup_app_logging()

    try:
        base_path = Path(output_base)
        if not base_path.exists():
            typer.echo("No runs found.")
            return

        runs = sorted([d for d in base_path.iterdir() if d.is_dir()])

        if not runs:
            typer.echo("No runs found.")
            return

        typer.echo("\n📊 Available Runs:")
        typer.echo("-" * 50)

        for run_dir in runs:
            store = RunStore(run_dir)
            state = store.load_state()
            status = state.get("status", "UNKNOWN") if state else "NO STATE"
            typer.echo(f"  {run_dir.name}: {status}")

    except Exception as e:
        logger.error("cli_list_runs_failed", error=str(e))
        typer.echo(f"\n❌ List failed: {e}", err=True)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
