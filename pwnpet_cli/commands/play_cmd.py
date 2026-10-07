"""`pwnpet play` -- play magic with badge."""
from __future__ import annotations

import argparse
from .. import bitmaps, chars, transport, ui
from ..errors import UsageError
from . import _ops


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("play", help="Play magic.")
    from . import add_target_arg
    add_target_arg(parser)
    parser.add_argument("hex", help="32-bit hex magic")
    parser.set_defaults(handler=run)


async def execute(
    conn: transport.Connection,
    hex_str: str,
    species: str | int | None = None,
) -> None:
    try:
        val = int(hex_str, 16)
        data = val.to_bytes(4, byteorder="little")
    except ValueError:
        raise UsageError(f"invalid hex magic {hex_str!r}")
    await conn.write(chars.NAME_TO_UUID["play"], data)
    state_b = await conn.read(chars.NAME_TO_UUID["state"])
    if species is None:
        species = await _ops.get_conn_species(conn)

    from .. import format as fmt

    st = fmt.render_state(state_b[0] if state_b else 0)
    is_dead = st in (
        "muerto_salud",
        "muerto (salud)",
        "muerto_gordito",
        "muerto (gordito)",
        "muerto0",
        "muerto1",
    )

    if is_dead:
        sprite = bitmaps.get_sprite(st, species=species)
        if sprite:
            ui.console.print(f"[cyan]{sprite}[/]")
        ui.warn("Your pet is dead! It cannot play.")
    else:
        st_name = "leal" if val == 0xDEADBEEF else "paranoia"
        sprite = bitmaps.get_sprite(st_name, species=species)
        if sprite:
            ui.console.print(f"[cyan]{sprite}[/]")
        ui.ok("played magic")



async def run(args: argparse.Namespace) -> int:
    from . import resolve_target
    target = await resolve_target(args)
    async with transport.Connection(target) as conn:
        await execute(conn, args.hex)
    return 0
