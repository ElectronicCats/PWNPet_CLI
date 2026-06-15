"""`pwnpet session` — interactive REPL over a persistent BLE connection.

Connects once and keeps the link open across all commands, eliminating
the per-command scan + service-discovery + disconnect overhead (~5-10 s
per invocation). Disconnect happens only on 'exit', 'quit', or Ctrl+D.
feed always sends the fixed amount (50).
"""

from __future__ import annotations

import argparse
import asyncio
import shlex

from .. import chars, transport, ui
from ..errors import GattError, UsageError
from . import add_target_arg, resolve_target
from . import (
    feed_cmd, flag_cmd, missions_cmd, passkey_cmd,
    pet_cmd, play_cmd, read_cmd, rename_cmd, status_cmd, write_cmd,
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
_BLE_COUNT    = 0x01
_BLE_GET      = 0x02
_BLE_REMOVE   = 0x03
_BLE_BLOCK    = 0x04
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


async def _cmd_feed(conn: transport.Connection, argv: list[str]) -> None:
    await feed_cmd.execute(conn)


async def _cmd_pet(conn: transport.Connection, argv: list[str]) -> None:
    await pet_cmd.execute(conn)


async def _cmd_play(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError("play requires a hex argument (e.g. 0xAABBCCDD)")
    await play_cmd.execute(conn, argv[0])


async def _cmd_status(conn: transport.Connection, argv: list[str]) -> None:
    await status_cmd.execute(conn)


async def _cmd_rename(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError("rename requires a name argument (max 16 bytes)")
    await rename_cmd.execute(conn, argv[0])


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
    _parser = argparse.ArgumentParser(prog="missions", add_help=False, exit_on_error=False)
    _parser.add_argument("--hint", metavar="<id>", type=int)
    try:
        ns = _parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as exc:
        raise UsageError(f"missions: {exc}")
    await missions_cmd.execute(conn, ns.hint)


async def _cmd_flag(conn: transport.Connection, argv: list[str]) -> None:
    if not argv:
        raise UsageError("flag requires a mission id (e.g. flag 4)")
    try:
        mid = int(argv[0])
    except ValueError:
        raise UsageError(f"flag: expected a mission id number, got {argv[0]!r}")
    await flag_cmd.execute(conn, mid)


_DISPATCH_TABLE = {
    "feed":       _cmd_feed,
    "pet":        _cmd_pet,
    "play":       _cmd_play,
    "status":     _cmd_status,
    "rename":     _cmd_rename,
    "passkey":    _cmd_passkey,
    "read":       _cmd_read,
    "write":      _cmd_write,
    "missions":   _cmd_missions,
    "flag":       _cmd_flag,
    "friendship": _dispatch_friendship,
}


async def _dispatch(conn: transport.Connection, cmd: str, argv: list[str]) -> None:
    handler = _DISPATCH_TABLE.get(cmd)
    if handler is None:
        ui.print_error("cmd", f"unknown command: {cmd!r}. Type 'help'.")
        return
    await handler(conn, argv)


async def _repl(conn: transport.Connection, addr: str) -> None:
    ui.console.print(f"[green]Connected to {addr}.[/]")
    ui.console.print("[dim]Type 'help' for available commands, 'exit' or Ctrl+D to disconnect.[/]\n")
    creature_dead = False
    try:
        await _dispatch(conn, "status", [])
        creature_dead = await _creature_is_dead(conn)
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
            ui.print_help(creature_dead)
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
            ui.console.print("[yellow]Factory reset initiated. Device will reboot in ~1 s.[/]")
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
