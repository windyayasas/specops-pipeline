"""Tests for sandbox path validation."""

import pytest

from specops.sandbox.path_validator import sanitize_path, validate_path


class TestPathValidator:
    """Path validation tests."""

    def test_relative_path_valid(self):
        """Test that relative paths within allowed base are valid."""
        assert validate_path("src/main.py", "outputs/run1") is True
        assert validate_path("tests/test_main.py", "outputs/run1") is True
        assert validate_path("nested/deep/file.py", "outputs/run1") is True

    def test_absolute_path_rejected(self):
        """Test that absolute paths are rejected."""
        assert validate_path("/etc/passwd", "outputs/run1") is False
        assert validate_path("/usr/bin/python", "outputs/run1") is False

    def test_parent_directory_traversal_rejected(self):
        """Test that .. patterns are rejected."""
        assert validate_path("../../../etc", "outputs/run1") is False
        assert validate_path("src/../../../secret", "outputs/run1") is False
        assert validate_path("..\\..\\secret", "outputs/run1") is False

    def test_path_escaping_attempt_rejected(self):
        """Test that attempts to escape base directory are rejected."""
        # This would try to escape allowed base
        assert validate_path("../../etc/passwd", "outputs/run1") is False

    def test_path_within_nested_base(self):
        """Test paths within nested base directories."""
        assert validate_path("file.py", "outputs/run1/deep/nested") is True

    def test_empty_path(self):
        """Test empty path handling."""
        result = validate_path("", "outputs/run1")
        # Empty path should resolve to base, which is within base
        assert result is True

    def test_simple_filename(self):
        """Test simple filenames are valid."""
        assert validate_path("implementation.py", "outputs") is True
        assert validate_path("tests.py", "outputs") is True

    def test_dot_in_filename(self):
        """Test that dots in filenames (extensions) are allowed."""
        assert validate_path("test.py", "outputs") is True
        assert validate_path("data.json", "outputs") is True


class TestPathSanitizer:
    """Path sanitization tests."""

    def test_sanitize_removes_leading_slashes(self):
        """Test that leading slashes are removed."""
        assert sanitize_path("/etc/passwd") == "etc/passwd"
        assert sanitize_path("//double/slash") == "double/slash"

    def test_sanitize_removes_parent_directory(self):
        """Test that .. sequences are removed."""
        assert sanitize_path("../secret") == "secret"
        # After removing .. from src/../other we get src/other (slashes remain)
        result = sanitize_path("src/../other")
        assert ".." not in result

    def test_sanitize_removes_null_bytes(self):
        """Test that null bytes are removed."""
        assert sanitize_path("file\x00.py") == "file.py"

    def test_sanitize_preserves_safe_paths(self):
        """Test that safe paths are mostly preserved."""
        assert sanitize_path("src/main.py") == "src/main.py"
        assert sanitize_path("tests/test_main.py") == "tests/test_main.py"
