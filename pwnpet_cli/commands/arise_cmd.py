"""`pwnpet arise` -- resurrect a dead creature via factory reset."""
from __future__ import annotations

import argparse

from .. import bitmaps, chars, format as fmt, transport, ui
from ..errors import GattError, UsageError
from . import _ops

_DEAD_STATES = (
    "muerto_salud",
    "muerto (salud)",
    "muerto_gordito",
    "muerto (gordito)",
    "muerto0",
    "muerto1",
)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "arise", help="Factory reset a dead creature to resurrect it."
    )
    from . import add_target_arg

    add_target_arg(parser)
    parser.set_defaults(handler=run)


async def execute(
    conn: transport.Connection,
    addon_connected: bool | None = None,
    species: str | int | None = None,
) -> bool:
    """Execute arise resurrection command.

    Returns True if factory reset was initiated, False if aborted or blocked.
    """
    state_b = await conn.read(chars.NAME_TO_UUID["state"])
    st = fmt.render_state(state_b[0] if state_b else 0)
    if st not in _DEAD_STATES:
        raise UsageError(
            "arise: command only available when the creature is dead "
            "(state: muerto_salud or muerto_gordito)"
        )

    try:
        confirm = ui.console.input(
            "[bold red]WARNING:[/] This will wipe all saved data and reboot the device.\n"
            "Type [bold]yes[/] to confirm: "
        )
    except (KeyboardInterrupt, EOFError):
        ui.console.print()
        return False

    if confirm.strip().lower() != "yes":
        ui.console.print("[dim]Aborted.[/]")
        return False

    if species is None:
        species = await _ops.get_conn_species(conn)
    if addon_connected is None:
        addon_connected = await _ops.check_addon_connected(conn)

    sprite = bitmaps.get_sprite(
        "arise", species=species, addon_connected=addon_connected
    )
    if sprite:
        ui.console.print(f"[cyan]{sprite}[/]")

    try:
        await conn.write(chars.NAME_TO_UUID["factory_reset"], bytes([0x01]))
    except GattError:
        ui.console.print(
            "[red]Arise blocked:[/] the creature died too recently — "
            "wait 3 minutes after death before using arise."
        )
        return False

    ui.console.print(
        "[yellow]Factory reset initiated. Device will reboot in ~1 s.[/]"
    )
    return True


async def run(args: argparse.Namespace) -> int:
    from . import resolve_target

    target = await resolve_target(args)
    async with transport.Connection(target) as conn:
        await execute(conn)
    return 0
