"""`pwnpet target {set|show|clear}` — manage stored target badge."""

from __future__ import annotations

import argparse

from .. import target as target_store, ui
from .. import transport


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("target", help="Manage the persisted target badge.")
    inner = parser.add_subparsers(dest="action", metavar="<action>")
    inner.required = True

    p_set = inner.add_parser("set", help="Set target by MAC or local name.")
    p_set.add_argument("addr_or_name", help="MAC (AA:BB:CC:DD:EE:FF) or name (PwnPet_XXXX).")
    p_set.set_defaults(handler=run_set)

    p_show = inner.add_parser("show", help="Print current target.")
    p_show.set_defaults(handler=run_show)

    p_clear = inner.add_parser("clear", help="Forget the stored target.")
    p_clear.set_defaults(handler=run_clear)


def _looks_like_mac(s: str) -> bool:
    parts = s.split(":")
    if len(parts) != 6:
        return False
    return all(len(p) == 2 and all(c in "0123456789abcdefABCDEF" for c in p) for p in parts)


async def run_set(args: argparse.Namespace) -> int:
    arg = args.addr_or_name
    if _looks_like_mac(arg):
        target_store.save(arg.upper(), name=None)
        return 0
    # Treat as local name → mini-scan to resolve. TargetNotFoundError
    # propagates to main() naturally on no/multiple match.
    device = await transport.resolve_name_to_device(arg)
    target_store.save(device.address.upper(), name=arg)
    return 0


def run_show(args: argparse.Namespace) -> int:
    loaded = target_store.load()
    if loaded is None:
        ui.console.print("[dim](none)[/]")
    else:
        addr, name = loaded
        if name:
            ui.console.print(f"[bold]{name}[/]  [dim]{addr}[/]")
        else:
            ui.console.print(f"[dim]{addr}[/]")
    return 0


def run_clear(args: argparse.Namespace) -> int:
    target_store.clear()
    return 0
