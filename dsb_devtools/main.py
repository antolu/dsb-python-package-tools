from __future__ import annotations

import argparse

from .pkginit import main as pkginit_main
from .pkginit import make_parser as pkginit_make_parser
from .renovate import make_parser as renovate_make_parser
from .renovate import setup as renovate_setup
from .renovate import teardown as renovate_teardown
from .renovate import update as renovate_update


def _run_pkginit(args: argparse.Namespace) -> None:
    pkginit_main(args)


def _run_renovate(args: argparse.Namespace) -> None:
    if args.command == "setup":
        renovate_setup(project_path=args.project_path, token=args.token)
    elif args.command == "teardown":
        renovate_teardown(project_path=args.project_path, token=args.token)
    elif args.command == "update":
        renovate_update(project_path=args.project_path, token=args.token)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="DSB Devtools", usage="dsb-devtools <command> [options]"
    )
    subparsers = parser.add_subparsers(dest="command")

    pkginit_parser = subparsers.add_parser(
        "pkginit", help="Initialize a new Python package"
    )
    pkginit_make_parser(pkginit_parser)
    pkginit_parser.set_defaults(func=_run_pkginit)

    renovate_parser = subparsers.add_parser(
        "renovate", help="Manage Renovate CI setup for a GitLab project"
    )
    renovate_make_parser(renovate_parser)
    renovate_parser.set_defaults(func=_run_renovate)

    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)
