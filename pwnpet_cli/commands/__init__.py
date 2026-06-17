"""Subcommand handlers for the pwnpet CLI."""

from __future__ import annotations

import argparse

from .. import target as target_store
from .. import transport
from ..errors import UsageError


def add_target_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target",
        "-t",
        metavar="<addr|name>",
        help="Override the stored target for this command.",
    )


async def resolve_target(args: argparse.Namespace) -> "str | object":
    """Return either a MAC address string or a bleak BLEDevice, depending
    on which path is taken. Subcommand handlers pass the result directly
    to transport.Connection() which accepts either type.

    Path                                      Returns
    --target <name>                           BLEDevice (from a fresh scan)
    --target <MAC>                            str (no scan)
    last_target.json (no --target)            str (cached MAC)
    """
    explicit = getattr(args, "target", None)
    if explicit:
        if ":" in explicit:
            return explicit.upper()
        return await transport.resolve_name_to_device(explicit)

    loaded = target_store.load()
    if loaded is None:
        raise UsageError(
            "no target set. Run 'pwnpet target set <addr|name>' or pass --target."
        )
    addr, _name = loaded
    return addr
