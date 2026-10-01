"""`pwnpet addon` -- control Tamal / Villa Cloud Add-On via BLE -> I2C.

The Badge forwards commands via I2C to Add-On address 0x50.

Usage:
  pwnpet addon ping                        Check communication (0x50 -> 0xAD)
  pwnpet addon set <eyes|blush|sauce|all> <1|0>  Manual LED control
  pwnpet addon blink <eyes|blush|sauce|all> <period_ds>  Blink mode
  pwnpet addon anim <1-7|0>                Select animation mode (1-7 or 0=off/auto)
  pwnpet addon off                         Turn off all LEDs
"""

from __future__ import annotations

import argparse

from .. import bitmaps, chars, transport, ui
from ..errors import GattError, UsageError
from . import _ops

OLED_CHAR_UUID = chars._u16(0xC00A)

# I2C Protocol registers for Addon
REG_LED_SET = 0x01
REG_LED_BLINK = 0x02
REG_LED_ALL_OFF = 0x03
REG_ANIM_MODE = 0x04
REG_PING = 0xFF

# Opcode for Badge BLE -> I2C passthrough
OP_ADDON_WRITE = 0x20
OP_ADDON_PING = 0x21
OP_ADDON_STATUS = 0x22

LED_MAP = {
    "eyes": 0x01,
    "ojos": 0x01,
    "blush": 0x02,
    "mejillas": 0x02,
    "sauce": 0x04,
    "salsa": 0x04,
    "all": 0x07,
    "todos": 0x07,
}


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "addon",
        help="Control Tamal Add-On via BLE -> I2C.",
    )
    from . import add_target_arg
    add_target_arg(parser)

    sub = parser.add_subparsers(dest="addon_cmd", metavar="<action>")
    sub.required = True

    # 1. STATUS
    sub.add_parser("status", help="Get Add-On connection status over BLE (0x22)")

    # 2. PING
    sub.add_parser("ping", help="Check communication with Add-On (0x50)")

    # 2. ANIM
    p_anim = sub.add_parser("anim", help="Set animation sequence (1-7 or 0)")
    p_anim.add_argument("mode", type=int, help="Animation mode: 1-7 or 0")

    # 3. SET
    p_set = sub.add_parser("set", help="Manual LED control")
    p_set.add_argument("led", help="LED: eyes, blush, sauce, all or bitmask")
    p_set.add_argument("state", type=int, choices=[0, 1], help="State: 1=ON, 0=OFF")

    # 4. BLINK
    p_blink = sub.add_parser("blink", help="Set LED blink rate")
    p_blink.add_argument("led", help="LED: eyes, blush, sauce, all or bitmask")
    p_blink.add_argument("period", type=int, help="Period in tenths of a second (1=100ms)")

    # 5. OFF
    sub.add_parser("off", help="Turn off all LEDs on Add-On")

    parser.set_defaults(handler=run)


def _parse_mask(led_str: str) -> int:
    key = led_str.lower()
    if key in LED_MAP:
        return LED_MAP[key]
    try:
        val = int(led_str, 0)
        return val & 0xFF
    except ValueError:
        raise UsageError(
            f"unknown LED {led_str!r} -- options: eyes, blush, sauce, all, or bitmask"
        )


async def _send_i2c(conn: transport.Connection, reg: int, data: bytes = b"") -> None:
    payload = bytes([OP_ADDON_WRITE, reg]) + data
    try:
        await conn.write(OLED_CHAR_UUID, payload)
    except GattError as exc:
        raise GattError(f"addon: {exc.message}") from exc


async def execute_status(
    conn: transport.Connection, species: str | int | None = None
) -> None:
    try:
        await conn.write(OLED_CHAR_UUID, bytes([OP_ADDON_STATUS]))
        resp = await conn.read(OLED_CHAR_UUID)
        if resp and len(resp) >= 1:
            is_connected = (resp[0] == 0x01)
            last_ping = resp[1] if len(resp) >= 2 else 0x00
            st_code = resp[2] if len(resp) >= 3 else 0x00
            st_name = {0: "DISCONNECTED", 1: "CONNECTING", 2: "CONNECTED", 3: "DISCONNECTING"}.get(st_code, "UNKNOWN")
            if is_connected:
                if species is None:
                    species = await _ops.get_conn_species(conn)
                sprite = bitmaps.get_sprite("friends", species=species)
                if sprite:
                    ui.console.print(f"[cyan]{sprite}[/]")
                ui.ok(f"ADDON: CONNECTED (state={st_name}, ping=0x{last_ping:02X})")
            else:
                ui.warn(f"ADDON: DISCONNECTED (state={st_name}, ping=0x{last_ping:02X})")
        else:
            ui.warn("ADDON: empty status response")
    except GattError as exc:
        raise GattError(f"addon status: {exc.message}") from exc


async def execute_ping(conn: transport.Connection) -> None:
    try:
        await conn.write(OLED_CHAR_UUID, bytes([OP_ADDON_PING]))
        resp = await conn.read(OLED_CHAR_UUID)
        if resp and resp[0] == 0xAD:
            ui.ok("ADDON: OK (0x50 -> 0xAD)")
        else:
            ui.warn(f"ADDON: unexpected response {resp.hex() if resp else 'empty'}")
    except GattError:
        # Fallback to write-only ping
        await _send_i2c(conn, REG_PING)
        ui.ok("ADDON: ping sent (0xFF)")


async def execute_anim(conn: transport.Connection, mode: int) -> None:
    if not (0 <= mode <= 7):
        raise UsageError("mode must be 0-7 (0=auto/off, 1..7=sequences)")
    await _send_i2c(conn, REG_ANIM_MODE, bytes([mode]))
    if mode == 0:
        ui.ok("ADDON: anim mode set to auto/off")
    else:
        ui.ok(f"ADDON: anim sequence {mode} active")


async def execute_set(conn: transport.Connection, led_str: str, state: int) -> None:
    mask = _parse_mask(led_str)
    await _send_i2c(conn, REG_LED_SET, bytes([mask, 1 if state else 0]))
    ui.ok(f"ADDON: set {led_str} (mask=0x{mask:02X}) -> {'ON' if state else 'OFF'}")


async def execute_blink(conn: transport.Connection, led_str: str, period_ds: int) -> None:
    mask = _parse_mask(led_str)
    if not (1 <= period_ds <= 255):
        raise UsageError("period must be 1-255 (tenths of a second)")
    await _send_i2c(conn, REG_LED_BLINK, bytes([mask, period_ds]))
    ui.ok(f"ADDON: blink {led_str} (period={period_ds * 100} ms)")


async def execute_off(conn: transport.Connection) -> None:
    await _send_i2c(conn, REG_LED_ALL_OFF)
    ui.ok("ADDON: all LEDs OFF")


async def run(args: argparse.Namespace) -> int:
    from . import resolve_target

    target = await resolve_target(args)
    async with transport.Connection(target) as conn:
        cmd = args.addon_cmd
        if cmd == "status":
            await execute_status(conn)
        elif cmd == "ping":
            await execute_ping(conn)
        elif cmd == "anim":
            await execute_anim(conn, args.mode)
        elif cmd == "set":
            await execute_set(conn, args.led, args.state)
        elif cmd == "blink":
            await execute_blink(conn, args.led, args.period)
        elif cmd == "off":
            await execute_off(conn)
    return 0
