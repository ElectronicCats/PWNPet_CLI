"""`pwnpet read <name|uuid> [--watch] [--passkey D]` — read a characteristic."""

from __future__ import annotations

import argparse
import asyncio

from .. import chars, encoders, format as fmt, transport, ui
from ..errors import GattError, UsageError
from . import add_target_arg, resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "read", help="Read a characteristic by name or UUID."
    )
    parser.add_argument(
        "char",
        metavar="<name|uuid>",
        help="Public name (e.g. happiness) or 0xNNNN UUID.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Loop and re-read every --interval seconds.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Watch interval seconds (default 1.0).",
    )
    parser.add_argument(
        "--passkey",
        metavar="<digits>",
        help="Write 3 BCD passkey then read in same connection.",
    )
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection, char: str) -> None:
    try:
        uuid = chars.resolve(char)
    except KeyError:
        raise UsageError(f"unknown char {char!r} (public name or 0xNNNN UUID)")
    raw = await conn.read(uuid)
    ui.print_decoded(ui.decode(char, raw))


async def run(args: argparse.Namespace) -> int:
    try:
        uuid = chars.resolve(args.char)
    except KeyError:
        raise UsageError(
            f"unknown char {args.char!r} (use a public name or 0xNNNN UUID)"
        )

    if args.watch and args.passkey:
        raise UsageError("--watch and --passkey are mutually exclusive")

    addr = await resolve_target(args)

    async with transport.Connection(addr) as conn:
        if args.passkey:
            try:
                passkey_bytes = encoders.parse_passkey(args.passkey)
            except ValueError as exc:
                raise UsageError(str(exc))
            await conn.write(chars.NAME_TO_UUID["passkey_input"], passkey_bytes)
            raw = await conn.read(uuid)
            ui.print_decoded(ui.decode(args.char, raw))
            return 0

        if args.watch:
            try:
                while True:
                    try:
                        raw = await conn.read(uuid)
                    except GattError as exc:
                        ui.warn(f"connection lost: {exc}")
                        return 1
                    ui.print_decoded(ui.decode(args.char, raw))
                    await asyncio.sleep(args.interval)
            except (asyncio.CancelledError, KeyboardInterrupt):
                return 0

        raw = await conn.read(uuid)
        ui.print_decoded(ui.decode(args.char, raw))
        return 0
