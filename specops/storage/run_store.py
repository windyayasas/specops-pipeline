"""Pipeline run state persistence."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RunStore:
    """Persistent storage for run state and metadata."""

    def __init__(self, run_dir: str | Path):
        """
        Initialize run store.

        Args:
            run_dir: Directory to store run files
        """
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, state: dict[str, Any]) -> None:
        """
        Save current run state.

        Args:
            state: State dict to persist
        """
        state_file = self.run_dir / ".state.json"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
        logger.info("run_state_saved", file=str(state_file))

    def load_state(self) -> dict[str, Any] | None:
        """
        Load saved run state if it exists.

        Returns:
            State dict or None if not found
        """
        state_file = self.run_dir / ".state.json"
        if not state_file.exists():
            return None

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        logger.info("run_state_loaded", file=str(state_file))
        return state

    def save_run_metadata(self, run_id: str, metadata: dict[str, Any]) -> None:
        """
        Save run metadata.

        Args:
            run_id: Run identifier
            metadata: Run metadata
        """
        run_file = self.run_dir / ".run.json"
        data = {
            "run_id": run_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "metadata": metadata,
        }
        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("run_metadata_saved", file=str(run_file), run_id=run_id)

    def load_run_metadata(self) -> dict[str, Any] | None:
        """
        Load run metadata if it exists.

        Returns:
            Metadata dict or None if not found
        """
        run_file = self.run_dir / ".run.json"
        if not run_file.exists():
            return None

        with open(run_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("run_metadata_loaded", file=str(run_file))
        return data

    def save_artifact(self, name: str, content: str | bytes) -> Path:
        """
        Save a run artifact (code, tests, etc.).

        Args:
            name: Artifact name (e.g., "implementation.py")
            content: File content

        Returns:
            Path where artifact was saved
        """
        artifact_path = self.run_dir / name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            with open(artifact_path, "wb") as f:
                f.write(content)
        else:
            with open(artifact_path, "w", encoding="utf-8") as f:
                f.write(content)

        logger.info("run_artifact_saved", file=str(artifact_path), name=name)
        return artifact_path

    def load_artifact(self, name: str) -> str | None:
        """
        Load a run artifact.

        Args:
            name: Artifact name

        Returns:
            Artifact content or None if not found
        """
        artifact_path = self.run_dir / name
        if not artifact_path.exists():
            return None

        with open(artifact_path, "r", encoding="utf-8") as f:
            return f.read()
