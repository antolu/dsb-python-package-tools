from __future__ import annotations

import os
import pathlib
from unittest.mock import patch

from dsb_devtools.maintenance.__main__ import _resolve_repo_path
from dsb_devtools.maintenance._types import Manifest, StepContext


def _make_ctx(repo_path: pathlib.Path | None = None) -> StepContext:
    return StepContext(
        renovate_output=None,
        manifest=Manifest(latest="2026.01", base_distributions={}),
        gitlab_token="tok",
        dry_run=True,
        repository="org/repo",
        gitlab_base="https://gitlab.cern.ch",
        repo_path=repo_path,
    )


def test_step_context_accepts_repo_path(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(repo_path=tmp_path)
    assert ctx.repo_path == tmp_path


def test_step_context_accepts_none_repo_path() -> None:
    ctx = _make_ctx(repo_path=None)
    assert ctx.repo_path is None


def test_repo_path_derived_from_env(tmp_path: pathlib.Path) -> None:
    repo_dir = tmp_path / "repos" / "gitlab" / "org" / "repo"
    repo_dir.mkdir(parents=True)
    env = {
        "RENOVATE_BASE_DIR": str(tmp_path),
        "RENOVATE_PLATFORM": "gitlab",
        "RENOVATE_REPOSITORIES": "org/repo",
        "RENOVATE_TOKEN": "tok",
    }
    with patch.dict(os.environ, env, clear=False):
        result = _resolve_repo_path("org/repo")
    assert result == repo_dir


def test_repo_path_none_when_missing(tmp_path: pathlib.Path) -> None:
    env = {
        "RENOVATE_BASE_DIR": str(tmp_path),
        "RENOVATE_PLATFORM": "gitlab",
    }
    with patch.dict(os.environ, env, clear=False):
        result = _resolve_repo_path("org/nonexistent")
    assert result is None
