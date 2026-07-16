"""`pwnpet owner [<name>]` — read or set the badge holder's name.

`pwnpet owner`          reads 0xFE09 and prints the current owner name.
`pwnpet owner <name>`   writes up to 20 UTF-8 bytes to 0xC009 (set_owner).

Distinct from `pwnpet rename`, which names the *pet* (0xC004). The owner is
the human wearing the badge — the primary datum a conference badge shows.
"""

from __future__ import annotations

import argparse

from .. import chars, transport, ui
from ..errors import UsageError
from . import add_target_arg, resolve_target

_MAX_NAME_BYTES = 20


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "owner", help="Read or set the badge holder's name (max 20 bytes)."
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="New owner name. Omit to read the current name.",
    )
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection, name: "str | None") -> None:
    if name is None:
        # Read mode.
        raw = await conn.read(chars.NAME_TO_UUID["owner_name"])
        current = raw.rstrip(b"\x00").decode("utf-8", errors="replace")
        ui.console.print(f"owner: {current}" if current else "owner: [dim](unset)[/]")
        return

    payload = name.encode("utf-8")
    if len(payload) > _MAX_NAME_BYTES:
        raise UsageError(
            f"name too long: {len(payload)} bytes (max {_MAX_NAME_BYTES} UTF-8 bytes)"
        )
    await conn.write(chars.NAME_TO_UUID["set_owner"], payload)
    confirm_b = await conn.read(chars.NAME_TO_UUID["owner_name"])
    confirmed = confirm_b.rstrip(b"\x00").decode("utf-8", errors="replace")
    ui.console.print(f"owner: {confirmed}" if confirmed else "owner: [dim](unset)[/]")


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn, args.name)
    return 0
