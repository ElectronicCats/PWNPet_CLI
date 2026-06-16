"""`pwnpet status` — composite read of all public chars."""

from __future__ import annotations

import argparse

from .. import transport, ui
from . import add_target_arg, resolve_target
from ._ops import fetch_status


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "status", help="Read all public state in one bundle."
    )
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection) -> None:
    values = await fetch_status(conn)
    ui.print_status(values)


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn)
    return 0
