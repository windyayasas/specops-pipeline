"""Sandbox utilities for safe file operations."""

import os
from pathlib import Path


def validate_path(path: str, allowed_base: str) -> bool:
    """
    Validate that a path is safe and within allowed base directory.

    Rejects:
    - Absolute paths
    - Paths with ".." (parent directory traversal)
    - Paths pointing outside allowed_base
    - System directories (/etc, /usr/bin, /var, /sys, etc.)

    Args:
        path: Path to validate
        allowed_base: Base directory where writing is allowed

    Returns:
        True if path is valid and safe

    Examples:
        >>> validate_path("src/main.py", "outputs/run1")
        True
        >>> validate_path("/etc/passwd", "outputs/run1")
        False
        >>> validate_path("../../../etc", "outputs/run1")
        False
    """
    # Reject absolute paths
    if os.path.isabs(path):
        return False

    # Reject paths with ..
    if ".." in path:
        return False

    # Normalize and resolve paths
    try:
        base_resolved = Path(allowed_base).resolve()
        full_path = (base_resolved / path).resolve()

        # Check if full_path is within base_resolved
        try:
            full_path.relative_to(base_resolved)
        except ValueError:
            # Not relative to base
            return False

        return True
    except (RuntimeError, ValueError):
        return False


def sanitize_path(path: str) -> str:
    """
    Sanitize a path by removing dangerous characters and patterns.

    Args:
        path: Path to sanitize

    Returns:
        Sanitized path
    """
    # Remove leading slashes
    path = path.lstrip("/")

    # Remove .. sequences
    import re
    path = re.sub(r"\.\.+", "", path)
    
    # Clean up any leading slashes that might have been created
    path = path.lstrip("/")

    # Remove null bytes
    path = path.replace("\x00", "")

    return path
