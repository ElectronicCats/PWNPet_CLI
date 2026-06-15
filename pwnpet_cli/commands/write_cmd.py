"""`pwnpet write <name|uuid> <hex>` — write hex bytes to a characteristic."""

from __future__ import annotations

import argparse

from .. import chars, encoders, transport, ui
from ..errors import UsageError
from . import add_target_arg, resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("write", help="Write hex bytes to a characteristic.")
    parser.add_argument("char", metavar="<name|uuid>")
    parser.add_argument("payload", metavar="<hex>", help="Hex bytes (even-length, no 0x). Empty string allowed.")
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection, char: str, payload_str: str) -> None:
    try:
        uuid = chars.resolve(char)
    except KeyError:
        raise UsageError(f"unknown char {char!r} (public name or 0xNNNN UUID)")
    try:
        payload = encoders.parse_write_payload(payload_str)
    except ValueError as exc:
        raise UsageError(str(exc))
    await conn.write(uuid, payload)
    ui.ok()


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn, args.char, args.payload)
    return 0
