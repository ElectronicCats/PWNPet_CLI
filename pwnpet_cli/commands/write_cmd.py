"""`pwnpet write <name|uuid> <hex>` — write hex bytes to a characteristic."""

from __future__ import annotations

import argparse

from .. import chars, encoders, transport
from ..errors import UsageError
from . import add_target_arg, resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("write", help="Write hex bytes to a characteristic.")
    parser.add_argument("char", metavar="<name|uuid>")
    parser.add_argument("payload", metavar="<hex>", help="Hex bytes (even-length, no 0x). Empty string allowed.")
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def run(args: argparse.Namespace) -> int:
    try:
        uuid = chars.resolve(args.char)
    except KeyError:
        raise UsageError(f"unknown char {args.char!r} (use a public name or 0xNNNN UUID)")
    try:
        payload = encoders.parse_write_payload(args.payload)
    except ValueError as exc:
        raise UsageError(str(exc))

    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await conn.write(uuid, payload)
    return 0
