from __future__ import annotations

import argparse
import dataclasses
import json
import os
import pathlib
import sys

import rich

from ._log_parser import parse_log
from ._manifest import load_manifest
from ._runner import run_steps
from ._steps import STEPS
from ._types import LogParseError, StepContext

_BUNDLED_MANIFEST = pathlib.Path(__file__).parent / "manifest.json"
_DEFAULT_MANIFEST_URL = os.environ.get(
    "MAINTENANCE_MANIFEST_URL", str(_BUNDLED_MANIFEST)
)


def _cmd_run(args: argparse.Namespace) -> None:
    renovate_output = None
    if args.log:
        log_path = pathlib.Path(args.log)
        if log_path.exists():
            try:
                renovate_output = parse_log(log_path)
                rich.print(
                    f"[bold blue].[/bold blue] Parsed renovate log: "
                    f"{len(renovate_output.branches)} branches"
                )
            except LogParseError as e:
                rich.print(
                    f"[bold red]✗[/bold red] Failed to parse renovate log: {e}",
                    file=sys.stderr,
                )
        else:
            rich.print(
                f"[bold yellow]![/bold yellow] Log file not found: {log_path}",
                file=sys.stderr,
            )

    manifest = load_manifest(args.manifest, _BUNDLED_MANIFEST)

    token = os.environ.get("RENOVATE_TOKEN") or os.environ.get("GITLAB_TOKEN") or ""
    repository = (
        os.environ.get("RENOVATE_REPOSITORIES")
        or os.environ.get("CI_PROJECT_PATH")
        or ""
    )
    gitlab_base = os.environ.get("RENOVATE_ENDPOINT", "https://gitlab.cern.ch/api/v4")
    if gitlab_base.endswith("/api/v4"):
        gitlab_base = gitlab_base[: -len("/api/v4")]

    ctx = StepContext(
        renovate_output=renovate_output,
        manifest=manifest,
        gitlab_token=token,
        dry_run=args.dry_run,
        repository=repository,
        gitlab_base=gitlab_base,
    )

    run_steps(ctx, STEPS)


def _cmd_parse_log(args: argparse.Namespace) -> None:
    try:
        output = parse_log(pathlib.Path(args.log))
        print(json.dumps(dataclasses.asdict(output), indent=2, default=str))
    except LogParseError as e:
        rich.print(f"[bold red]✗[/bold red] {e}", file=sys.stderr)
        sys.exit(1)


def make_parser(
    main_parser: argparse.ArgumentParser | None = None,
) -> argparse.ArgumentParser:
    parser = main_parser or argparse.ArgumentParser(
        description="Run acc-py maintenance steps."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run all maintenance steps")
    run_parser.add_argument(
        "--log", default=None, help="Path to renovate JSON log file"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Print actions, make no changes"
    )
    run_parser.add_argument(
        "--manifest",
        default=_DEFAULT_MANIFEST_URL,
        help="URL or path to deprecation manifest JSON",
    )
    run_parser.set_defaults(func=_cmd_run)

    parse_parser = subparsers.add_parser(
        "parse-log", help="Dump parsed renovate log as JSON"
    )
    parse_parser.add_argument(
        "--log", required=True, help="Path to renovate JSON log file"
    )
    parse_parser.set_defaults(func=_cmd_parse_log)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = make_parser()
    args = parser.parse_args(argv)
    args.func(args)
