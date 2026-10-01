"""`pwnpet play <hex>` — write u32 LE to 0xC003 and read 0xC0FF flag buffer."""

from __future__ import annotations

import argparse

from .. import bitmaps, encoders, format as fmt, transport, ui
from ..errors import UsageError
from . import _ops, add_target_arg, resolve_target


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


async def execute(
    conn: transport.Connection,
    magic_str: str,
    species: str | int | None = None,
) -> None:
    try:
        magic_bytes = encoders.parse_play_hex(magic_str)
    except ValueError as exc:
        raise UsageError(str(exc))
    val = int.from_bytes(magic_bytes, byteorder="little")
    if species is None:
        species = await _ops.get_conn_species(conn)
    st = "leal" if val == 0xDEADBEEF else "paranoia"
    sprite = bitmaps.get_sprite(st, species=species)
    if sprite:
        ui.console.print(f"[cyan]{sprite}[/]")
    result = await conn.play_read_flag(magic_bytes)
    ui.print_decoded(fmt.render_bytes_smart(result))


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn, args.magic)
    return 0
