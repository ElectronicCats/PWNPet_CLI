"""`pwnpet pet` — write 0 bytes to 0xC002."""

from __future__ import annotations

import argparse

from .. import bitmaps, chars, transport, ui
from . import _ops, add_target_arg, resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("pet", help="Pet the badge.")
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection, species: str | int | None = None) -> None:
    await conn.write(chars.NAME_TO_UUID["pet"], bytes([0x01]))
    if species is None:
        species = await _ops.get_conn_species(conn)
    sprite = bitmaps.get_sprite("curious", species=species)
    if sprite:
        ui.console.print(f"[cyan]{sprite}[/]")
    ui.ok()


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn)
    return 0
