"""`pwnpet rename <name>` — write a new pet name (up to 16 UTF-8 bytes) to 0xC004."""

from __future__ import annotations

import argparse

from .. import chars, transport, ui
from ..errors import UsageError
from . import add_target_arg, resolve_target

_MAX_NAME_BYTES = 16


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("rename", help="Change the pet's name (max 16 bytes).")
    parser.add_argument("name", help="New name for the badge pet.")
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def run(args: argparse.Namespace) -> int:
    payload = args.name.encode("utf-8")
    if len(payload) == 0:
        raise UsageError("name cannot be empty")
    if len(payload) > _MAX_NAME_BYTES:
        raise UsageError(
            f"name too long: {len(payload)} bytes (max {_MAX_NAME_BYTES} UTF-8 bytes)"
        )

    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await conn.write(chars.NAME_TO_UUID["rename"], payload)
        name_bytes = await conn.read(chars.NAME_TO_UUID["name"])

    confirmed = name_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
    ui.console.print(f"name: {confirmed}")
    return 0
