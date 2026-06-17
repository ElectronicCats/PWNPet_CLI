"""`pwnpet missions` — list missions and their completion status.

Usage:
  pwnpet missions                 # show all missions with [ ] / [X]
  pwnpet missions --hint <id>     # show the hint for mission <id>
"""

from __future__ import annotations

import argparse

from .. import transport, ui
from . import add_target_arg, resolve_target
from ._ops import fetch_mission_hint, fetch_missions

# mission_list wire format (0xFE08):
#   byte 0       : count (n)
#   bytes 1..2n  : pairs [id, done] for each mission
#                  done == 1 means completed


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "missions",
        help="List missions and completion status.",
    )
    parser.add_argument(
        "--hint",
        metavar="<id>",
        type=int,
        help="Show the hint for the given mission id.",
    )
    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(conn: transport.Connection, hint: int | None = None) -> None:
    creature_name, missions = await fetch_missions(conn)
    hint_text: str | None = None
    if hint is not None:
        hint_text = await fetch_mission_hint(conn, hint)
    ui.print_missions(creature_name, missions)
    if hint_text is not None:
        if hint_text:
            ui.console.print(f'\nHint for mission {hint}: [italic]"{hint_text}"[/]')
        else:
            ui.console.print(f"\n[dim]No hint available for mission {hint}.[/]")


async def run(args: argparse.Namespace) -> int:
    addr = await resolve_target(args)
    async with transport.Connection(addr) as conn:
        await execute(conn, args.hint)
    return 0
