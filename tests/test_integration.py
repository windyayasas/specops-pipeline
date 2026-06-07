"""Integration tests for core pipeline components."""

from pathlib import Path

from specops.audit.logger import AuditLogger
from specops.storage.run_store import RunStore


class TestRunStore:
    """Run store integration tests."""

    def test_save_and_load_state(self, tmp_path: Path):
        """Test saving and loading run state."""
        store = RunStore(tmp_path)

        state = {
            "status": "CREATED",
            "run_id": "test_run_123",
            "data": {"key": "value"},
        }

        store.save_state(state)
        loaded = store.load_state()

        assert loaded is not None
        assert loaded["status"] == "CREATED"
        assert loaded["run_id"] == "test_run_123"

    def test_save_and_load_metadata(self, tmp_path: Path):
        """Test saving and loading run metadata."""
        store = RunStore(tmp_path)

        metadata = {
            "name": "test_run",
            "version": "0.1.0",
        }

        store.save_run_metadata("test_run_123", metadata)
        loaded = store.load_run_metadata()

        assert loaded is not None
        assert loaded["run_id"] == "test_run_123"
        assert loaded["metadata"]["name"] == "test_run"

    def test_load_nonexistent_state(self, tmp_path: Path):
        """Test loading nonexistent state returns None."""
        store = RunStore(tmp_path)
        loaded = store.load_state()

        assert loaded is None

    def test_save_artifact(self, tmp_path: Path):
        """Test saving artifacts."""
        store = RunStore(tmp_path)

        content = "print('Hello, World!')"
        path = store.save_artifact("test.py", content)

        assert path.exists()
        assert path.read_text() == content

    def test_save_artifact_in_subdirectory(self, tmp_path: Path):
        """Test saving artifacts in subdirectories."""
        store = RunStore(tmp_path)

        content = "def test(): pass"
        path = store.save_artifact("src/main.py", content)

        assert path.exists()
        assert path.parent.name == "src"

    def test_load_artifact(self, tmp_path: Path):
        """Test loading saved artifact."""
        store = RunStore(tmp_path)

        content = "test content"
        store.save_artifact("test.txt", content)

        loaded = store.load_artifact("test.txt")
        assert loaded == content

    def test_load_nonexistent_artifact(self, tmp_path: Path):
        """Test loading nonexistent artifact returns None."""
        store = RunStore(tmp_path)
        loaded = store.load_artifact("nonexistent.txt")

        assert loaded is None


class TestAuditLogger:
    """Audit logger integration tests."""

    def test_log_and_retrieve_events(self, tmp_path: Path):
        """Test logging and retrieving audit events."""
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        logger.log_event(
            run_id="run_123",
            stage="planner",
            actor="system",
            event_type="plan_generated",
            status="success",
        )

        events = logger.get_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "plan_generated"

    def test_log_multiple_events(self, tmp_path: Path):
        """Test logging multiple events in sequence."""
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        logger.log_event("run_1", "planner", "system", "plan_start", "started")
        logger.log_event("run_1", "planner", "system", "plan_end", "success")
        logger.log_event("run_2", "planner", "system", "plan_start", "started")

        events = logger.get_events()
        assert len(events) == 3

    def test_filter_events_by_run_id(self, tmp_path: Path):
        """Test filtering events by run ID."""
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        logger.log_event("run_1", "planner", "system", "event_1", "success")
        logger.log_event("run_2", "planner", "system", "event_2", "success")
        logger.log_event("run_1", "planner", "system", "event_3", "success")

        run_1_events = logger.get_events("run_1")
        assert len(run_1_events) == 2

        run_2_events = logger.get_events("run_2")
        assert len(run_2_events) == 1

    def test_get_run_timeline(self, tmp_path: Path):
        """Test getting chronological timeline for a run."""
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        logger.log_event("run_1", "planner", "system", "event_1", "success")
        logger.log_event("run_1", "implementer", "system", "event_2", "success")
        logger.log_event("run_1", "quality", "system", "event_3", "success")

        timeline = logger.get_run_timeline("run_1")
        assert len(timeline) == 3
        assert timeline[0]["stage"] == "planner"
        assert timeline[1]["stage"] == "implementer"
        assert timeline[2]["stage"] == "quality"

    def test_audit_file_created_automatically(self, tmp_path: Path):
        """Test that audit file and directories are created automatically."""
        audit_file = tmp_path / "deep" / "nested" / "audit.jsonl"
        logger = AuditLogger(audit_file)

        logger.log_event("run_1", "planner", "system", "event_1", "success")

        assert audit_file.exists()
        assert audit_file.parent == tmp_path / "deep" / "nested"

    def test_audit_append_only(self, tmp_path: Path):
        """Test that audit logger is append-only (never overwrites)."""
        audit_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(audit_file)

        # Log first event
        logger.log_event("run_1", "planner", "system", "event_1", "success")
        initial_size = audit_file.stat().st_size

        # Log another event
        logger.log_event("run_1", "implementer", "system", "event_2", "success")
        new_size = audit_file.stat().st_size

        # File size should increase (append-only)
        assert new_size > initial_size

        # Both events should exist
        events = logger.get_events()
        assert len(events) == 2
