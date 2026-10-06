"""`pwnpet feed` -- feed the badge."""
from __future__ import annotations

import argparse
from .. import bitmaps, chars, format as fmt, transport, ui
from ..errors import GattError, UsageError
from . import _ops

_DEFAULT_FEED_AMOUNT = 50


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("feed", help="Feed the badge.")
    from . import add_target_arg
    add_target_arg(parser)
    parser.add_argument("amount", nargs="?", type=int, default=_DEFAULT_FEED_AMOUNT, help="Amount 1-255 (default 50)")
    parser.set_defaults(handler=run)


async def execute(
    conn: transport.Connection,
    amount: int = _DEFAULT_FEED_AMOUNT,
    species: str | int | None = None,
) -> None:
    if not (1 <= amount <= 255):
        raise UsageError("amount must be 1-255")
    await conn.write(chars.NAME_TO_UUID["feed"], bytes([amount]))

    state_b = await conn.read(chars.NAME_TO_UUID["state"])
    hungry_b = await conn.read(chars.NAME_TO_UUID["hungry"])
    if species is None:
        species = await _ops.get_conn_species(conn)

    st = fmt.render_state(state_b[0] if state_b else 0)
    hungry_val = fmt.render_u16_le(hungry_b)

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
        ui.warn("Your pet is dead! It cannot eat.")
    else:
        if hungry_val >= 900:
            sprite_name = "gordito3"
        elif hungry_val >= 750:
            sprite_name = "gordito2"
        elif hungry_val >= 600:
            sprite_name = "gordito1"
        else:
            sprite_name = "celebrando"

        sprite = bitmaps.get_sprite(sprite_name, species=species)
        if sprite:
            ui.console.print(f"[cyan]{sprite}[/]")
        ui.ok(f"fed {amount}")


async def run(args: argparse.Namespace) -> int:
    from . import resolve_target
    target = await resolve_target(args)
    async with transport.Connection(target) as conn:
        await execute(conn, args.amount)
    return 0

