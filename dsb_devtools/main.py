from __future__ import annotations


import argparse
from .pkginit import main as pkginit_main, make_parser as pkginit_make_parser


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="DSB Devtools", usage="dsb-devtools <command> [options]"
    )
    subparsers = parser.add_subparsers(dest="command")
    pkginit_parser = subparsers.add_parser(
        "pkginit", help="Initialize a new Python package"
    )
    pkginit_make_parser(pkginit_parser)

    args = parser.parse_args(argv or [])

    if args.command == "pkginit":
        pkginit_main(args)
    else:
        parser.print_help()
