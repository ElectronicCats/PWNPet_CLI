"""`pwnpet play <hex>` — write u32 LE to 0xC003 and read 0xC0FF flag buffer."""

from __future__ import annotations

import argparse

from .. import encoders, format as fmt, transport, ui
from ..errors import UsageError
from . import add_target_arg, resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "play", help="Play with the badge (write u32 magic)."
    )
    parser.add_argument(
        "magic",
        metavar="<hex>",
        help="u32 hex value (0x prefix optional, e.g. 0xAABBCCDD).",
    )
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection, magic_str: str) -> None:
    try:
        magic_bytes = encoders.parse_play_hex(magic_str)
    except ValueError as exc:
        raise UsageError(str(exc))
    result = await conn.play_read_flag(magic_bytes)
    ui.print_decoded(fmt.render_bytes_smart(result))


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn, args.magic)
    return 0
