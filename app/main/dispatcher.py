from __future__ import annotations

import argparse
from collections.abc import Sequence

from app.main.entrypoints import APP_DEFAULT_ENTRYPOINT, APP_ENTRYPOINTS, APP_FUTURE_ENTRYPOINTS
from app.main.help import format_entrypoint_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simple-comment-viewer",
        description="NDGR simple comment viewer entrypoint dispatcher",
    )
    parser.add_argument(
        "--entrypoint",
        "-e",
        default=APP_DEFAULT_ENTRYPOINT,
        choices=sorted(APP_ENTRYPOINTS),
        help=f"entrypoint to run. default: {APP_DEFAULT_ENTRYPOINT}",
    )
    parser.add_argument(
        "--list-entrypoints",
        action="store_true",
        help="show active and planned entrypoints",
    )
    return parser


def dispatch(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, passthrough = parser.parse_known_args(argv)
    if args.list_entrypoints:
        print(format_entrypoint_report(APP_DEFAULT_ENTRYPOINT, APP_ENTRYPOINTS, APP_FUTURE_ENTRYPOINTS))
        return 0
    entrypoint = APP_ENTRYPOINTS[args.entrypoint]
    return entrypoint.runner(passthrough)
