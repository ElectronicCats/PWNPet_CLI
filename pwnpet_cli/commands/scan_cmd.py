"""`pwnpet scan` — discover PwnPet badges in range."""

from __future__ import annotations

import argparse

from .. import transport, ui


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("scan", help="Discover PwnPet badges in range.")
    parser.add_argument(
        "--all", action="store_true", help="Show all BLE devices, not just PwnPet."
    )
    parser.add_argument(
        "--raw", action="store_true", help="Include raw manufacturer data hex column."
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="Scan window in seconds (default 5)."
    )
    parser.set_defaults(handler=run)


async def run(args: argparse.Namespace) -> int:
    hits = await transport.scan(timeout=args.timeout, all_devices=args.all)
    if not hits:
        ui.console.print(
            f"[dim](no PwnPet badges found in {args.timeout:.0f}s — try --all)[/]"
        )
        return 0

    ui.print_scan_results(hits, raw=args.raw)
    return 0
