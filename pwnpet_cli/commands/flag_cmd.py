"""`pwnpet flag <mission_id>` — retrieve the flag for a completed mission.

Protocol: write 1-byte mission_id to 0xC005, then read 20-byte flag.
The firmware computes the flag on-demand only if the mission is completed;
otherwise it clears the buffer (all zeros).
"""

from __future__ import annotations

import argparse

from .. import format as fmt, transport, ui
from . import add_target_arg, resolve_target
from ._ops import fetch_flag


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "flag",
        help="Read the flag for a completed mission (0xC005).",
    )
    parser.add_argument(
        "mission_id",
        metavar="<mission_id>",
        type=int,
        help="Mission id (1-based).",
    )
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection, mid: int) -> None:
    flag_bytes = await fetch_flag(conn, mid)
    if flag_bytes is None:
        ui.console.print(f"[dim]Mission {mid} is not completed yet.[/]")
        return
    if all(b == 0 for b in flag_bytes):
        ui.console.print(
            f"[yellow]Mission {mid} is marked complete but the firmware "
            "returned an empty flag — try re-completing the mission.[/]"
        )
        return
    ui.print_decoded(fmt.render_utf8(flag_bytes))


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn, args.mission_id)
    return 0
