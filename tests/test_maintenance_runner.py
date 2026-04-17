from __future__ import annotations

import datetime
import json
import pathlib
import subprocess
import sys
from unittest.mock import MagicMock

from dsb_devtools.maintenance._runner import run_steps
from dsb_devtools.maintenance._types import (
    BaseDist,
    MaintenanceStep,
    Manifest,
    StepContext,
)

FIXTURE_LOG = pathlib.Path(__file__).parent / "fixtures" / "renovate_sa_preisach.log"


def _make_ctx(*, dry_run: bool = True) -> StepContext:
    manifest = Manifest(
        latest="2026.01",
        base_distributions={
            "2026.01": BaseDist(
                tag="2026.01", python="3.14", eol=datetime.date(2031, 1, 1)
            ),
        },
    )
    return StepContext(
        renovate_output=None,
        manifest=manifest,
        gitlab_token="tok",
        dry_run=dry_run,
        repository="org/repo",
        gitlab_base="https://gitlab.cern.ch",
    )


def test_run_steps_calls_step_run() -> None:
    ran = []

    class DummyStep(MaintenanceStep):
        name = "dummy"
        requires_renovate_output = False

        def run(self, ctx: StepContext) -> None:
            ran.append(True)

    run_steps(_make_ctx(), [DummyStep()])
    assert ran == [True]


def test_run_steps_skips_step_requiring_renovate_output_when_none() -> None:
    ran = []

    class NeedsRenovate(MaintenanceStep):
        name = "needs_renovate"
        requires_renovate_output = True

        def run(self, ctx: StepContext) -> None:
            ran.append(True)

    run_steps(_make_ctx(), [NeedsRenovate()])
    assert ran == []


def test_run_steps_runs_step_when_renovate_output_present() -> None:
    ran = []

    class NeedsRenovate(MaintenanceStep):
        name = "needs_renovate"
        requires_renovate_output = True

        def run(self, ctx: StepContext) -> None:
            ran.append(True)

    ctx = _make_ctx()
    ctx.renovate_output = MagicMock()
    run_steps(ctx, [NeedsRenovate()])
    assert ran == [True]


def test_cli_run_dry_run_exits_zero() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsb_devtools",
            "maintenance",
            "run",
            "--log",
            str(FIXTURE_LOG),
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_cli_parse_log_outputs_json() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsb_devtools",
            "maintenance",
            "parse-log",
            "--log",
            str(FIXTURE_LOG),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["repository"] == "dsb/hysteresis/sa-preisach"
