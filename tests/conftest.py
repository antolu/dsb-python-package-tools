from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest before test collection."""
    # Save original stdin/stdout
    original_stdin = sys.stdin
    original_stdout = sys.stdout

    # Mock stdin/stdout with files that have fileno()
    # This prevents the survey module from crashing on import
    mock_stdin = MagicMock()
    mock_stdin.buffer = MagicMock()
    mock_stdin.buffer.fileno.return_value = 0
    mock_stdin.fileno.return_value = 0

    mock_stdout = MagicMock()
    mock_stdout.buffer = MagicMock()
    mock_stdout.buffer.fileno.return_value = 1
    mock_stdout.fileno.return_value = 1

    sys.stdin = mock_stdin
    sys.stdout = mock_stdout

    try:
        # Force import of modules that use survey, so they initialize with the mocks
        import dsb_devtools.pkginit._input  # noqa: PLC0415
        import dsb_devtools.pkginit._pkginit  # noqa: F401, PLC0415
    except ImportError:
        # If imports fail for other reasons, let it bubble up later or pass here
        pass
    finally:
        # Restore original stdin/stdout so pytest can report results
        sys.stdin = original_stdin
        sys.stdout = original_stdout
