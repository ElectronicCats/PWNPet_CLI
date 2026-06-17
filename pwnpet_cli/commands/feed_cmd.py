"""`pwnpet feed` — write fixed u8 50 to 0xC001."""

from __future__ import annotations

import argparse

from .. import chars, transport, ui
from . import add_target_arg, resolve_target

_FEED_PAYLOAD = bytes([50])


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("feed", help="Feed the badge.")
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection) -> None:
    await conn.write(chars.NAME_TO_UUID["feed"], _FEED_PAYLOAD)
    ui.ok()


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn)
    return 0
