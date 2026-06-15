"""`pwnpet play <hex>` — write u32 LE to 0xC003 and read 0xC0FF flag buffer."""

from __future__ import annotations

import argparse

from .. import encoders, format as fmt, transport, ui
from ..errors import UsageError
from . import add_target_arg, resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("play", help="Play with the badge (write u32 magic).")
    parser.add_argument("magic", metavar="<hex>", help="u32 hex value (0x prefix optional, e.g. 0xAABBCCDD).")
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def run(args: argparse.Namespace) -> int:
    try:
        magic_bytes = encoders.parse_play_hex(args.magic)
    except ValueError as exc:
        raise UsageError(str(exc))

    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        result = await conn.play_read_flag(magic_bytes)
    decoded = fmt.render_bytes_smart(result)
    if decoded.startswith("PWNPET{"):
        ui.console.print(f"[bold bright_yellow]{decoded}[/]")
    else:
        ui.console.print(decoded)
    return 0
