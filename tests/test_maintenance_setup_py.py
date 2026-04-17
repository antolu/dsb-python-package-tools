from __future__ import annotations

import os
import pathlib
import subprocess
from unittest.mock import patch

from dsb_devtools.maintenance.__main__ import _resolve_repo_path
from dsb_devtools.maintenance._types import Manifest, StepContext
from dsb_devtools.maintenance.steps.setup_py import SetupPyStep


def _make_ctx(
    repo_path: pathlib.Path | None = None,
    *,
    dry_run: bool = True,
) -> StepContext:
    return StepContext(
        renovate_output=None,
        manifest=Manifest(latest="2026.01", base_distributions={}),
        gitlab_token="tok",
        dry_run=dry_run,
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


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_setup_py_step_skips_when_no_repo_path() -> None:
    step = SetupPyStep()
    ctx = _make_ctx(repo_path=None)
    step.run(ctx)


def test_setup_py_step_noop_when_no_setup_py(tmp_path: pathlib.Path) -> None:
    step = SetupPyStep()
    ctx = _make_ctx(repo_path=tmp_path)
    migrator_result = _completed(1, stderr=f"{tmp_path} does not contain a setup.py")
    with patch("subprocess.run", return_value=migrator_result) as mock_run:
        step.run(ctx)
    assert mock_run.call_count == 1


def test_setup_py_step_noop_when_no_git_changes(tmp_path: pathlib.Path) -> None:
    step = SetupPyStep()
    ctx = _make_ctx(repo_path=tmp_path)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        if "setup.py-migrator" in cmd[0]:
            return _completed(0)
        if "status" in cmd:
            return _completed(0, stdout="")
        return _completed(0)

    with patch("subprocess.run", side_effect=fake_run) as mock_run:
        step.run(ctx)
    called_cmds = [c.args[0] for c in mock_run.call_args_list]
    assert not any("commit" in str(c) for c in called_cmds)


def test_setup_py_step_commits_when_changes(tmp_path: pathlib.Path) -> None:
    step = SetupPyStep()
    ctx = _make_ctx(repo_path=tmp_path, dry_run=False)

    calls = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if "setup.py-migrator" in cmd[0]:
            return _completed(0)
        if "status" in cmd:
            return _completed(0, stdout="M pyproject.toml\nD setup.py\n")
        return _completed(0)

    with patch("subprocess.run", side_effect=fake_run):
        step.run(ctx)

    flat = [str(c) for c in calls]
    assert any("add" in s for s in flat)
    assert any("commit" in s for s in flat)
    assert any("push" in s for s in flat)


def test_setup_py_step_dry_run_prints_diff_and_restores(tmp_path: pathlib.Path) -> None:
    step = SetupPyStep()
    ctx = _make_ctx(repo_path=tmp_path, dry_run=True)

    calls = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if "setup.py-migrator" in cmd[0]:
            return _completed(0)
        if "status" in cmd:
            return _completed(0, stdout="M pyproject.toml\n")
        if "diff" in cmd:
            return _completed(0, stdout="--- a/pyproject.toml\n+++ b/pyproject.toml\n")
        return _completed(0)

    with patch("subprocess.run", side_effect=fake_run):
        step.run(ctx)

    flat = [str(c) for c in calls]
    assert any("diff" in s for s in flat)
    assert any("checkout" in s for s in flat)
    assert not any("commit" in s for s in flat)
