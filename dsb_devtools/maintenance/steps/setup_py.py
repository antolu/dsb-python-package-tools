from __future__ import annotations

import subprocess
import sys

import rich

from .._types import MaintenanceStep, StepContext


class SetupPyStep(MaintenanceStep):
    name = "setup-py"
    requires_renovate_output = False

    def run(self, ctx: StepContext) -> None:
        if ctx.repo_path is None:
            rich.print(
                "[bold yellow]![/bold yellow] setup-py: no repo_path available, skipping",
                file=sys.stderr,
            )
            return

        result = subprocess.run(
            ["setup.py-migrator", str(ctx.repo_path)],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            if "does not contain a setup.py" in result.stderr:
                return
            rich.print(
                f"[bold red]✗[/bold red] setup-py: migrator failed:\n{result.stderr}",
                file=sys.stderr,
            )
            return

        status = subprocess.run(
            ["git", "-C", str(ctx.repo_path), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            return

        if ctx.dry_run:
            diff = subprocess.run(
                ["git", "-C", str(ctx.repo_path), "diff"],
                check=False,
                capture_output=True,
                text=True,
            )
            rich.print("[bold blue]setup-py (dry-run): would commit:[/bold blue]")
            print(diff.stdout)
            subprocess.run(
                ["git", "-C", str(ctx.repo_path), "checkout", "--", "."],
                check=False,
                capture_output=True,
            )
            return

        subprocess.run(
            ["git", "-C", str(ctx.repo_path), "add", "-u"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(ctx.repo_path),
                "commit",
                "-m",
                "chore: migrate setup.py to pyproject.toml",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(ctx.repo_path), "push"],
            check=True,
        )
