from __future__ import annotations

import sys

import rich

from ._types import MaintenanceStep, StepContext


def run_steps(ctx: StepContext, steps: list[MaintenanceStep]) -> None:
    for step in steps:
        if step.requires_renovate_output and ctx.renovate_output is None:
            rich.print(
                f"[{step.name}] skipped — no renovate output available",
                file=sys.stderr,
            )
            continue
        step.run(ctx)
