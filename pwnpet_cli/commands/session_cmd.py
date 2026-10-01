"""`pwnpet session` -- interactive REPL over a persistent BLE connection.

Connects once and keeps the link open across all commands, eliminating
the per-command scan + service-discovery + disconnect overhead (~5-10 s
per invocation). Disconnect happens only on 'exit', 'quit', or Ctrl+D.
"""

from __future__ import annotations

import argparse
import asyncio
import shlex

from .. import chars, transport, ui
from ..errors import GattError, UsageError
from . import add_target_arg, resolve_target
from . import (
    feed_cmd,
    flag_cmd,
    led_cmd,
    missions_cmd,
    owner_cmd,
    passkey_cmd,
    pet_cmd,
    play_cmd,
    read_cmd,
    rename_cmd,
    status_cmd,
    write_cmd,
    addon_cmd,
    clock_cmd,
)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "session",
        help="Open an interactive REPL over a persistent BLE connection (default mode).",
    )
    add_target_arg(parser)
    parser.set_defaults(handler=run)


_DEAD_STATES: frozenset[int] = frozenset({4, 5})


async def _creature_is_dead(conn: transport.Connection) -> bool:
    try:
        state_b = await conn.read(chars.NAME_TO_UUID["state"])
        return bool(state_b) and state_b[0] in _DEAD_STATES
    except GattError:
        return False


_FRIENDSHIP_UUID = chars.NAME_TO_UUID["friendship_cmd"]

# Opcodes matching firmware friendship.h FRIENDSHIP_BLE_* constants.
_BLE_COUNT = 0x01
_BLE_GET = 0x02
_BLE_REMOVE = 0x03
_BLE_BLOCK = 0x04
_BLE_PROX_GET = 0x05
_BLE_PROX_SET = 0x06


def _parse_ble_addr(s: str) -> bytes:
    parts = s.split(":")
    if len(parts) != 6 or any(len(p) != 2 for p in parts):
        raise UsageError(f"invalid BLE address {s!r} — expected AA:BB:CC:DD:EE:FF")
    try:
        return bytes(int(p, 16) for p in parts)
    except ValueError:
        raise UsageError(f"invalid BLE address {s!r}")


async def _friendship_cmd(conn: transport.Connection, payload: bytes) -> bytes:
    """Write opcode+args to C008, return raw response bytes."""
    await conn.write(_FRIENDSHIP_UUID, payload)
    return await conn.read(_FRIENDSHIP_UUID)


async def _dispatch_friendship(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError(
            "friendship requires a subcommand: list, count, remove, block, proximity"
        )
    sub = argv[0]

    if sub == "count":
        raw = await _friendship_cmd(conn, bytes([_BLE_COUNT]))
        ui.ok(str(raw[0]) if raw else "0")

    elif sub == "list":
        count_raw = await _friendship_cmd(conn, bytes([_BLE_COUNT]))
        n = count_raw[0] if count_raw else 0
        for i in range(n):
            entry = await _friendship_cmd(conn, bytes([_BLE_GET, i]))
            if not entry or entry[0] == 0xFF:
                continue
            addr = ":".join(f"{b:02X}" for b in entry[:6])
            if len(entry) >= 20:
                # New format: [addr[6], name[11], name_len, species_lo, flags]
                stored_len = entry[17]
                display_len = min(stored_len, 11)
                name = entry[6 : 6 + display_len].decode("utf-8", errors="replace")
                species_lo = entry[18]
                blocked = bool(entry[19] & 0x01)
                if not name:
                    name = "".join(f"{b:02X}" for b in entry[3:6])
            elif len(entry) >= 12:
                # Legacy format: [addr[6], name[4], species_lo, flags]
                name = entry[6:10].decode("ascii", errors="replace")
                species_lo = entry[10]
                blocked = bool(entry[11] & 0x01)
            else:
                continue
            species_name = chars.SPECIES_TABLE.get(species_lo, "unknown")
            suffix = "  [blocked]" if blocked else ""
            ui.console.print(f"  {addr}  PwnPet_{name}  ({species_name}){suffix}")
        friend_word = "friend" if n == 1 else "friends"
        ui.ok(f"{n} {friend_word}")

    elif sub == "remove":
        if len(argv) < 2:
            raise UsageError("friendship remove <AA:BB:CC:DD:EE:FF>")
        addr = _parse_ble_addr(argv[1])
        raw = await _friendship_cmd(conn, bytes([_BLE_REMOVE]) + addr)
        ui.ok("done" if raw and raw[0] == 0x00 else "not found")

    elif sub == "block":
        if len(argv) < 2:
            raise UsageError("friendship block <AA:BB:CC:DD:EE:FF>")
        addr = _parse_ble_addr(argv[1])
        raw = await _friendship_cmd(conn, bytes([_BLE_BLOCK]) + addr)
        ui.ok("done" if raw and raw[0] == 0x00 else "list full")

    elif sub == "proximity":
        if len(argv) < 2:
            raw = await _friendship_cmd(conn, bytes([_BLE_PROX_GET]))
            state = "on" if raw and raw[0] else "off"
            ui.ok(f"proximity: {state}")
        elif argv[1] in ("on", "off"):
            val = 1 if argv[1] == "on" else 0
            await _friendship_cmd(conn, bytes([_BLE_PROX_SET, val]))
            ui.ok(argv[1])
        else:
            raise UsageError("friendship proximity on|off")

    else:
        raise UsageError(
            f"unknown subcommand {sub!r} — try: list, count, remove, block, proximity"
        )


async def _cmd_play(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError("play requires a hex argument (e.g. 0xAABBCCDD)")
    await play_cmd.execute(conn, argv[0])


async def _cmd_rename(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError("rename requires a name argument (max 16 bytes)")
    await rename_cmd.execute(conn, argv[0])


async def _cmd_owner(conn: transport.Connection, argv: list[str]) -> None:
    # No argv → read; otherwise join the words back into one name (session
    # input is whitespace-split, and owner names may contain spaces).
    name = " ".join(argv) if argv else None
    await owner_cmd.execute(conn, name)


async def _cmd_passkey(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError("passkey requires exactly 3 digits (e.g. 163)")
    await passkey_cmd.execute(conn, argv[0])


async def _cmd_read(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError("read requires a char name or 0xNNNN UUID")
    await read_cmd.execute(conn, argv[0])


async def _cmd_write(conn: transport.Connection, argv: list[str]) -> None:
    if len(argv) < 2:
        raise UsageError("write requires <name|0xNNNN> and <hex-payload>")
    await write_cmd.execute(conn, argv[0], argv[1])


async def _cmd_missions(conn: transport.Connection, argv: list[str]) -> None:
    hint = int(argv[1]) if len(argv) >= 2 and argv[0] == "--hint" else None
    await missions_cmd.execute(conn, hint)


async def _cmd_flag(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError("flag requires a mission id (e.g. flag 4)")
    try:
        mid = int(argv[0])
    except ValueError:
        raise UsageError(f"flag: expected a mission id number, got {argv[0]!r}")
    await flag_cmd.execute(conn, mid)


async def _cmd_oled(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError(
            "oled requires a subcommand: restore, status, ping, neopixel, driver"
        )
    sub = argv[0].lower()

    if sub == "restore":
        await led_cmd.execute_restore(conn)

    elif sub == "status":
        if len(argv) < 3:
            raise UsageError("oled status <page_id> <value>")
        page_id_str = argv[1].lower()
        if page_id_str in led_cmd.STATUS_PAGES:
            page_id = led_cmd.STATUS_PAGES[page_id_str]
        else:
            try:
                page_id = int(page_id_str)
            except ValueError:
                raise UsageError(f"unknown page_id {argv[1]!r}")
        try:
            value = int(argv[2])
        except ValueError:
            raise UsageError(f"invalid value: {argv[2]!r}")
        await led_cmd.execute_status(conn, page_id, value)

    elif sub == "ping":
        await led_cmd.execute_ping(conn)

    elif sub == "driver":
        driver_name = argv[1] if len(argv) > 1 else None
        await led_cmd.execute_driver(conn, driver_name)

    elif sub == "neopixel":
        if len(argv) < 4:
            raise UsageError("oled neopixel <r> <g> <b>")
        try:
            r = int(argv[1])
            g = int(argv[2])
            b = int(argv[3])
        except ValueError:
            raise UsageError("RGB values must be integers (0-255)")
        await led_cmd.execute_neopixel(conn, r, g, b)

    else:
        raise UsageError(
            f"unknown subcommand {sub!r} -- try: restore, status, ping, driver, neopixel"
        )


def _no_args(fn):
    async def _w(conn, _):
        await fn(conn)

    return _w


async def _cmd_feed(conn: transport.Connection, argv: list[str]) -> None:
    amount = feed_cmd._DEFAULT_FEED_AMOUNT
    if argv:
        try:
            amount = int(argv[0])
        except ValueError:
            raise UsageError(f"feed: expected a number, got {argv[0]!r}")
    await feed_cmd.execute(conn, amount)


async def _cmd_addon(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError(
            "addon requires an action: status, ping, anim <1-7|0>, set <led> <1|0>, blink <led> <period>, off"
        )
    action = argv[0].lower()
    if action == "status":
        await addon_cmd.execute_status(conn)
    elif action == "ping":
        await addon_cmd.execute_ping(conn)
    elif action in (
        "anim",
        "anim1",
        "anim2",
        "anim3",
        "anim4",
        "anim5",
        "anim6",
        "anim7",
    ):
        if action.startswith("anim") and len(action) > 4 and action[4:].isdigit():
            mode = int(action[4:])
        elif len(argv) >= 2:
            try:
                mode = int(argv[1])
            except ValueError:
                raise UsageError(f"anim: expected number (0-7), got {argv[1]!r}")
        else:
            raise UsageError("addon anim: expected mode number (0-7)")
        await addon_cmd.execute_anim(conn, mode)
    elif action == "set":
        if len(argv) < 3:
            raise UsageError(
                "addon set: usage 'addon set <eyes|blush|sauce|all> <1|0>'"
            )
        try:
            state = int(argv[2])
        except ValueError:
            raise UsageError(f"set: expected 1 or 0, got {argv[2]!r}")
        await addon_cmd.execute_set(conn, argv[1], state)
    elif action == "blink":
        if len(argv) < 3:
            raise UsageError(
                "addon blink: usage 'addon blink <eyes|blush|sauce|all> <period_ds>'"
            )
        try:
            period = int(argv[2])
        except ValueError:
            raise UsageError(f"blink: expected number, got {argv[2]!r}")
        await addon_cmd.execute_blink(conn, argv[1], period)
    elif action == "off":
        await addon_cmd.execute_off(conn)
    else:
        raise UsageError(
            f"unknown addon action {action!r} -- try: ping, anim, set, blink, off"
        )


async def _cmd_clock(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError(
            "clock requires an action: countdown <sec>, reverse, spin, forward, sweep, pulse, hour <1-12>, mask <hex>, off, status"
        )
    action = argv[0].lower()
    if action == "status":
        await clock_cmd.execute_status(conn)
    elif action in ("countdown", "cd"):
        if len(argv) < 2:
            raise UsageError("clock countdown: usage 'clock countdown <seconds>'")
        try:
            sec = int(argv[1])
        except ValueError:
            raise UsageError(f"countdown: expected number of seconds, got {argv[1]!r}")
        await clock_cmd.execute_countdown(conn, sec)
    elif action in ("reverse", "rev"):
        await clock_cmd.execute_reverse(conn)
    elif action == "spin":
        await clock_cmd.execute_spin(conn)
    elif action in ("forward", "fwd"):
        await clock_cmd.execute_forward(conn)
    elif action == "sweep":
        await clock_cmd.execute_sweep(conn)
    elif action == "pulse":
        await clock_cmd.execute_pulse(conn)
    elif action == "hour":
        if len(argv) < 2:
            raise UsageError("clock hour: usage 'clock hour <1-12>'")
        try:
            hr = int(argv[1])
        except ValueError:
            raise UsageError(f"hour: expected number (1-12), got {argv[1]!r}")
        await clock_cmd.execute_hour(conn, hr)
    elif action == "mask":
        if len(argv) < 2:
            raise UsageError("clock mask: usage 'clock mask <0xHEX|int>'")
        await clock_cmd.execute_mask(conn, argv[1])
    elif action == "off":
        await clock_cmd.execute_off(conn)
    elif action in ("reflex", "game"):
        await clock_cmd.execute_reflex(conn)
    elif action == "hit":
        await clock_cmd.execute_hit(conn)
    elif action in ("secret", "supernova"):
        await clock_cmd.execute_secret(conn)
    elif action in ("ambient", "mood"):
        await clock_cmd.execute_ambient(conn)
    else:
        raise UsageError(
            f"unknown clock action {action!r} -- try: countdown, reverse, spin, forward, sweep, pulse, hour, mask, off, reflex, hit, secret, ambient, status"
        )


async def _cmd_reflex(conn: transport.Connection, argv: list[str]) -> None:
    action = argv[0].lower() if argv else "start"
    if action in ("start", "play", "game"):
        await clock_cmd.execute_reflex(conn)
    elif action == "hit":
        await clock_cmd.execute_hit(conn)
    elif action in ("status", "stat"):
        await clock_cmd.execute_status(conn)
    elif action in ("secret", "supernova"):
        await clock_cmd.execute_secret(conn)
    elif action in ("off", "stop"):
        await clock_cmd.execute_off(conn)
    else:
        raise UsageError("reflex: usage 'reflex [start|hit|status|secret|off]'")


_DISPATCH_TABLE = {
    "feed": _cmd_feed,
    "pet": _no_args(pet_cmd.execute),
    "play": _cmd_play,
    "status": _no_args(status_cmd.execute),
    "rename": _cmd_rename,
    "owner": _cmd_owner,
    "passkey": _cmd_passkey,
    "read": _cmd_read,
    "write": _cmd_write,
    "missions": _cmd_missions,
    "flag": _cmd_flag,
    "led": _cmd_oled,
    "oled": _cmd_oled,
    "addon": _cmd_addon,
    "clock": _cmd_clock,
    "timer": _cmd_clock,
    "reflex": _cmd_reflex,
    "friendship": _dispatch_friendship,
}


async def _dispatch(conn: transport.Connection, cmd: str, argv: list[str]) -> None:
    handler = _DISPATCH_TABLE.get(cmd)
    if handler is None:
        ui.print_error("cmd", f"unknown command: {cmd!r}. Type 'help'.")
        return
    await handler(conn, argv)


from . import _ops


async def _repl(conn: transport.Connection, addr: str) -> None:
    ui.console.print(f"[green]Connected to {addr}.[/]")
    ui.console.print(
        "[dim]Type 'help' for available commands, 'exit' or Ctrl+D to disconnect.[/]\n"
    )
    creature_dead = False
    addon_connected = False
    try:
        await _dispatch(conn, "status", [])
        creature_dead = await _creature_is_dead(conn)
        addon_connected = await _ops.check_addon_connected(conn)
        ui.console.print()
    except (GattError, UsageError):
        pass  # status on connect is best-effort
    while True:
        try:
            line = ui.console.input("[bold cyan](pwnpet)[/] ")
        except (KeyboardInterrupt, EOFError):
            ui.console.print()
            return

        line = line.strip()
        if not line:
            continue

        try:
            parts = shlex.split(line)
        except ValueError as exc:
            ui.print_error("parse", str(exc))
            continue

        cmd = parts[0].lower()
        if cmd in ("exit", "quit"):
            return
        if cmd == "help":
            ui.print_help(creature_dead, addon_connected=addon_connected)
            continue

        if (
            cmd in ("addon", "clock", "timer", "reflex", "led", "oled")
            and not addon_connected
        ):
            ui.print_error(
                "hardware",
                "Add-On hardware not detected. Connect the Tamal SAO Add-On to unlock display and Add-On commands.",
            )
            continue

        if cmd == "arise":
            creature_dead = await _creature_is_dead(conn)
            if not creature_dead:
                ui.print_error(
                    "arise",
                    "command only available when the creature is dead "
                    "(state: muerto_salud or muerto_gordito)",
                )
                continue
            try:
                confirm = ui.console.input(
                    "[bold red]WARNING:[/] This will wipe all saved data and reboot the device.\n"
                    "Type [bold]yes[/] to confirm: "
                )
            except (KeyboardInterrupt, EOFError):
                ui.console.print()
                continue
            if confirm.strip().lower() != "yes":
                ui.console.print("[dim]Aborted.[/]")
                continue
            try:
                await conn.write(chars.NAME_TO_UUID["factory_reset"], bytes([0x01]))
            except GattError:
                ui.console.print(
                    "[red]Arise blocked:[/] the creature died too recently — "
                    "wait 3 minutes after death before using arise."
                )
                continue
            ui.console.print(
                "[yellow]Factory reset initiated. Device will reboot in ~1 s.[/]"
            )
            return

        try:
            await _dispatch(conn, cmd, parts[1:])
            if cmd == "status":
                creature_dead = await _creature_is_dead(conn)
        except KeyboardInterrupt:
            ui.err_console.print("[dim]^C[/]")
        except UsageError as exc:
            ui.print_error("usage", exc.message)
        except GattError as exc:
            ui.print_error("gatt", exc.message)
            if not conn.is_connected:
                ui.console.print("[red]BLE connection lost. Ending session.[/]")
                return


async def run(args: argparse.Namespace) -> int:
    target = await resolve_target(args)
    display_addr = target if isinstance(target, str) else target.address  # type: ignore[union-attr]
    async with transport.Connection(target) as conn:
        await _repl(conn, display_addr)
    return 0
