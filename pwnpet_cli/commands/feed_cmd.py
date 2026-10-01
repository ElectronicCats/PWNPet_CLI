"""`pwnpet feed` — write fixed u8 50 to 0xC001."""

from __future__ import annotations

import argparse

from .. import bitmaps, chars, transport, ui
from ..errors import UsageError
from . import _ops, add_target_arg, resolve_target

_DEFAULT_FEED_AMOUNT = 50


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("feed", help="Feed the badge.")
    add_target_arg(parser)
    parser.add_argument(
        "amount",
        nargs="?",
        type=int,
        default=_DEFAULT_FEED_AMOUNT,
        help="Amount 1-255 (default 50)",
    )
    parser.set_defaults(handler=run)


async def execute(
    conn: transport.Connection,
    amount: int = _DEFAULT_FEED_AMOUNT,
    species: str | int | None = None,
) -> None:
    if not (1 <= amount <= 255):
        raise UsageError("amount must be 1-255")
    await conn.write(chars.NAME_TO_UUID["feed"], bytes([amount]))
    if species is None:
        species = await _ops.get_conn_species(conn)
    sprite = bitmaps.get_sprite("celebrando", species=species)
    if sprite:
        ui.console.print(f"[cyan]{sprite}[/]")
    ui.ok(f"fed {amount}" if amount != 50 else "ok")


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    amount = getattr(args, "amount", _DEFAULT_FEED_AMOUNT)
    async with transport.Connection(addr) as conn:
        await execute(conn, amount)
    return 0
