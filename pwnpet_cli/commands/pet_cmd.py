"""`pwnpet pet` — write 0 bytes to 0xC002."""

from __future__ import annotations

import argparse

from .. import chars, transport, ui
from . import add_target_arg, resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("pet", help="Pet the badge.")
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await conn.write(chars.NAME_TO_UUID["pet"], b"")
    ui.ok()
    return 0
