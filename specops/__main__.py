"""Entry point for SpecOps Pipeline."""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main() -> None:
    """Main entry point: detect mode (CLI vs API) and route accordingly."""
    # Check if running as API (via uvicorn) or CLI
    # For now, default to CLI via Typer
    from specops.cli import app as cli_app

    cli_app()


if __name__ == "__main__":
    main()
