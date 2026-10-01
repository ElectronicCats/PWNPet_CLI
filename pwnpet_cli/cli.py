"""argparse setup and subcommand dispatch."""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from typing import Sequence

from . import __version__, ui
from .errors import CliError, UsageError
from .commands import (
    add_target_arg,
    scan_cmd,
    target_cmd,
    status_cmd,
    read_cmd,
    write_cmd,
    feed_cmd,
    pet_cmd,
    play_cmd,
    passkey_cmd,
    rename_cmd,
    owner_cmd,
    session_cmd,
    missions_cmd,
    flag_cmd,
    addon_cmd,
    clock_cmd,
    led_cmd,
)


class _Parser(argparse.ArgumentParser):
    """ArgumentParser subclass that exits 1 with spec-formatted error.

    argparse's default error() exits 2; spec §8 unifies all usage errors
    at exit 1. Overriding here keeps argparse-rejected errors and
    application-raised UsageError consistent.
    """

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        ui.print_error("usage", message)
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="pwnpet",
        description=(
            "BLE toolkit for the PwnPet badge. "
            "Run without a subcommand to open an interactive session."
        ),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"pwnpet {__version__}",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show full tracebacks on errors.",
    )
    parser.set_defaults(handler=None)

    subparsers = parser.add_subparsers(dest="cmd", metavar="<command>")
    subparsers.required = False  # allow bare --help/--version without a subcommand
    session_cmd.add_parser(subparsers)  # primary interface — listed first
    scan_cmd.add_parser(subparsers)
    target_cmd.add_parser(subparsers)
    status_cmd.add_parser(subparsers)
    read_cmd.add_parser(subparsers)
    write_cmd.add_parser(subparsers)
    feed_cmd.add_parser(subparsers)
    pet_cmd.add_parser(subparsers)
    play_cmd.add_parser(subparsers)
    passkey_cmd.add_parser(subparsers)
    rename_cmd.add_parser(subparsers)
    owner_cmd.add_parser(subparsers)
    missions_cmd.add_parser(subparsers)
    flag_cmd.add_parser(subparsers)
    addon_cmd.add_parser(subparsers)
    clock_cmd.add_parser(subparsers)
    led_cmd.add_parser(subparsers)
    return parser


async def _run(coro: object) -> int:
    """Run *coro* with a custom asyncio exception handler that silences the
    BrokenPipeError emitted by dbus-fast when Bleak tears down a D-Bus
    connection that was already closed by a prior timeout cleanup.  The
    exception is harmless (the failed attempt was retried successfully) but
    Python's default handler prints an alarming traceback to stderr."""
    loop = asyncio.get_running_loop()
    orig = loop.get_exception_handler()

    def _handler(lp: asyncio.AbstractEventLoop, ctx: dict) -> None:
        if isinstance(ctx.get("exception"), BrokenPipeError):
            return
        (orig or lp.default_exception_handler)(lp, ctx)

    loop.set_exception_handler(_handler)
    return await coro  # type: ignore[return-value]


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # No subcommand → default to session (single-connection interactive mode).
    handler = args.handler if args.handler is not None else session_cmd.run

    try:
        result = handler(args)
        if asyncio.iscoroutine(result):
            return asyncio.run(_run(result)) or 0
        return result or 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        ui.console.print()
        return 0
    except UsageError as exc:
        if args.handler is None:
            # Implicit session with no target: guide the user instead of printing an error.
            parser.print_help()
            ui.err_console.print(
                "\n[dim]No target set. Use 'pwnpet target set <addr|name>' "
                "or 'pwnpet session --target <addr|name>' to connect.[/]"
            )
            return 0
        ui.print_error(exc.category, exc.message)
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        return exc.exit_code
    except CliError as exc:
        ui.print_error(exc.category, exc.message)
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        return exc.exit_code
