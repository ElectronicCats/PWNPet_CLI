"""`pwnpet passkey <digits>` — write 3 BCD bytes to 0x5E02."""

from __future__ import annotations

import argparse

from .. import chars, encoders, transport
from ..errors import UsageError
from . import add_target_arg, resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("passkey", help="Submit 3-digit passkey.")
    parser.add_argument("digits", metavar="<digits>", help="Exactly 3 ASCII digits, e.g. 123.")
    parser.add_argument("--times", metavar="N", type=int, default=1,
                        help="Send the passkey N times in a single connection (1–255).")
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def run(args: argparse.Namespace) -> int:
    if not 1 <= args.times <= 255:
        raise UsageError("--times must be between 1 and 255")

    try:
        payload = encoders.parse_passkey(args.digits)
    except ValueError as exc:
        raise UsageError(str(exc))

    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        for _ in range(args.times):
            await conn.write(chars.NAME_TO_UUID["passkey_input"], payload)
    return 0
