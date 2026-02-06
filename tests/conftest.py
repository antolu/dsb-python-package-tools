from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_stdin_for_survey(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock stdin/stdout before survey module can initialize."""
    # Create a mock stdin that has a fileno method
    mock_stdin = MagicMock()
    mock_stdin.buffer = MagicMock()
    mock_stdin.buffer.fileno.return_value = 0
    mock_stdin.fileno.return_value = 0

    mock_stdout = MagicMock()
    mock_stdout.buffer = MagicMock()
    mock_stdout.buffer.fileno.return_value = 1
    mock_stdout.fileno.return_value = 1

    monkeypatch.setattr(sys, "stdin", mock_stdin)
    monkeypatch.setattr(sys, "stdout", mock_stdout)
