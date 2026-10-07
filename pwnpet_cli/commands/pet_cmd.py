"""`pwnpet pet` -- pet the badge."""
from __future__ import annotations

import argparse
from .. import bitmaps, chars, transport, ui
from . import _ops


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("pet", help="Pet the badge.")
    from . import add_target_arg
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(
    conn: transport.Connection, species: str | int | None = None
) -> None:
    await conn.write(chars.NAME_TO_UUID["pet"], bytes([0x01]))
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
        ui.warn("Your pet is dead! It cannot be petted.")
    else:
        sprite = bitmaps.get_sprite("curious", species=species)
        if sprite:
            ui.console.print(f"[cyan]{sprite}[/]")
        ui.ok("petted")



async def run(args: argparse.Namespace) -> int:
    from . import resolve_target
    target = await resolve_target(args)
    async with transport.Connection(target) as conn:
        await execute(conn)
    return 0
