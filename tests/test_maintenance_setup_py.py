from __future__ import annotations

import pathlib

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
