"""Tests for observability logging."""


from specops.observability.logging import (
    bind_run_id,
    clear_run_id,
    get_logger,
    get_run_id,
    setup_logging,
)


class TestStructlogSetup:
    """Structlog setup and configuration tests."""

    def test_setup_logging_json_format(self):
        """Test logging setup with JSON format."""
        setup_logging(log_level="INFO", json_format=True)
        logger = get_logger(__name__)
        assert logger is not None

    def test_setup_logging_dev_format(self):
        """Test logging setup with development format."""
        setup_logging(log_level="DEBUG", json_format=False)
        logger = get_logger(__name__)
        assert logger is not None

    def test_get_logger_returns_bound_logger(self):
        """Test that get_logger returns a structlog logger."""
        logger = get_logger(__name__)
        # structlog returns BoundLoggerLazyProxy or BoundLogger depending on config
        assert logger is not None
        assert hasattr(logger, "info")  # Check it has logging methods

    def test_multiple_logger_instances(self):
        """Test that multiple logger instances work correctly."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1 is not None
        assert logger2 is not None


class TestRunIdContext:
    """Run ID context variable tests."""

    def test_bind_and_get_run_id(self):
        """Test binding and retrieving run ID from context."""
        run_id = "test_run_123"
        bind_run_id(run_id)

        assert get_run_id() == run_id

    def test_clear_run_id(self):
        """Test clearing run ID from context."""
        bind_run_id("test_run_123")
        clear_run_id()

        assert get_run_id() is None

    def test_run_id_default_is_none(self):
        """Test that run_id defaults to None."""
        clear_run_id()
        assert get_run_id() is None

    def test_multiple_run_id_changes(self):
        """Test changing run ID multiple times."""
        bind_run_id("run_1")
        assert get_run_id() == "run_1"

        bind_run_id("run_2")
        assert get_run_id() == "run_2"

        bind_run_id("run_3")
        assert get_run_id() == "run_3"

    def test_run_id_isolation(self):
        """Test that run IDs don't leak between different bindings."""
        clear_run_id()
        bind_run_id("isolated_run")

        assert get_run_id() == "isolated_run"

        clear_run_id()
        assert get_run_id() is None
