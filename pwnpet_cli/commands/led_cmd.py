"""`pwnpet oled` -- control OLED SH1106 display via BLE -> I2C.

The Badge exposes characteristic 0xC00A (led_control) which receives
a payload and forwards it over I2C to the OLED SH1106 (address 0x3C).

BLE payload format (OLED Protocol):
  [REG] [DATA_0] ... [DATA_N]

  OLED Registers:
    REG = 0x00 (restore) :  Exit text mode, resume creature animation
    REG = 0x03 (status)  :  [page_id] [value]
    REG = 0xFF (ping)    :  (Badge queries OLED I2C, responds with 0x3C)

  Status page_id values:
    0 = general status
    1 = species
    2 = owner
    3 = battery
    4 = connection

Usage:
  pwnpet oled restore                      Restore creature animation
  pwnpet oled status <page_id> <value>     Show status page
  pwnpet oled ping                         Check OLED communication
"""

from __future__ import annotations

import argparse

from .. import chars, transport, ui
from ..errors import GattError, UsageError

OLED_CHAR_UUID = chars._u16(0xC00A)

# OLED I2C Protocol registers
REG_OLED_RESTORE = 0x00
REG_OLED_STATUS = 0x03
REG_OLED_PING = 0xFF

# Status page IDs
STATUS_PAGES = {
    "general": 0,
    "status": 0,
    "species": 1,
    "owner": 2,
    "battery": 3,
    "connection": 4,
    "conn": 4,
}


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "oled",
        help="Control OLED SH1106 display via BLE -> I2C.",
    )
    from . import add_target_arg

    add_target_arg(parser)

    sub = parser.add_subparsers(dest="oled_cmd", metavar="<action>")
    sub.required = True

    # 1. OLED RESTORE
    sub.add_parser("restore", help="Exit text mode, restore creature animation")

    # 3. OLED STATUS
    p_status = sub.add_parser("status", help="Show status page on OLED")
    p_status.add_argument(
        "page_id",
        help="Page: general/status/species/owner/battery/connection (0-4)",
    )
    p_status.add_argument("value", type=int, help="Status value to display")

    # 4. OLED PING
    sub.add_parser("ping", help="Check Badge -> OLED I2C communication")

    # 5. OLED DRIVER
    p_driver = sub.add_parser("driver", help="Get or set active OLED driver type")
    p_driver.add_argument(
        "driver_name",
        nargs="?",
        default=None,
        help="Driver type: ssd1306_64, sh1106_64, ssd1306_32 (or omit to query)",
    )

    parser.set_defaults(handler=run)


async def _send(conn: transport.Connection, payload: bytes) -> None:
    """Write payload to Badge; Badge forwards it over I2C to OLED."""
    try:
        await conn.write(OLED_CHAR_UUID, payload)
    except GattError as exc:
        raise GattError(f"oled: {exc.message}") from exc


async def execute_restore(conn: transport.Connection) -> None:
    """Exit text mode and restore creature animation on the OLED."""
    await _send(conn, bytes([REG_OLED_RESTORE]))
    ui.ok("OLED: creature animation restored")


async def execute_status(conn: transport.Connection, page_id: int, value: int) -> None:
    await _send(conn, bytes([REG_OLED_STATUS, page_id, value]))
    ui.ok(f"OLED: status page {page_id} = {value}")


async def execute_ping(conn: transport.Connection) -> None:
    """Send PING to Badge, read OLED I2C response (0x3C)."""
    try:
        await conn.write(OLED_CHAR_UUID, bytes([REG_OLED_PING]))
        raw = await conn.read(OLED_CHAR_UUID)
    except GattError as exc:
        raise GattError(f"oled ping: {exc.message}") from exc
    if raw and raw[0] == 0x3C:
        ui.ok("OLED I2C responded OK (0x3C)")
    else:
        resp = raw.hex() if raw else "(empty)"
        ui.warn(f"unexpected response from OLED: {resp}")


OP_OLED_DRIVER = 0x30

DRIVER_MAP = {
    "ssd1306_64": 0,
    "ssd1306": 0,
    "0": 0,
    "sh1106_64": 1,
    "sh1106": 1,
    "1": 1,
    "ssd1306_32": 2,
    "32": 2,
    "2": 2,
}

DRIVER_NAMES = {
    0: 'SSD1306 128x64 (0.96")',
    1: 'SH1106 128x64 (1.3")',
    2: 'SSD1306 128x32 (0.91")',
}


async def execute_driver(
    conn: transport.Connection, driver_name: str | None = None
) -> None:
    """Get or set active OLED driver type."""
    if driver_name is not None:
        key = driver_name.lower().strip()
        if key not in DRIVER_MAP:
            valid = ", ".join(["ssd1306_64", "sh1106_64", "ssd1306_32"])
            raise UsageError(f"unknown driver {driver_name!r}. valid options: {valid}")
        driver_id = DRIVER_MAP[key]
        try:
            await conn.write(OLED_CHAR_UUID, bytes([OP_OLED_DRIVER, driver_id]))
            raw = await conn.read(OLED_CHAR_UUID)
        except GattError as exc:
            raise GattError(f"oled driver: {exc.message}") from exc
        name = DRIVER_NAMES.get(driver_id, f"driver {driver_id}")
        present = raw[1] == 1 if len(raw) >= 2 else True
        if present:
            ui.ok(f"OLED driver switched to {name}")
        else:
            ui.warn(f"OLED driver configured to {name} (display not detected)")
    else:
        try:
            await conn.write(OLED_CHAR_UUID, bytes([OP_OLED_DRIVER]))
            raw = await conn.read(OLED_CHAR_UUID)
        except GattError as exc:
            raise GattError(f"oled driver: {exc.message}") from exc
        driver_id = raw[0] if raw else 0
        present = raw[1] == 1 if len(raw) >= 2 else False
        name = DRIVER_NAMES.get(driver_id, f"driver {driver_id}")
        st_str = "PRESENT" if present else "NOT DETECTED"
        ui.ok(f"OLED active driver: {name} [{st_str}]")


async def execute_neopixel(conn: transport.Connection, r: int, g: int, b: int) -> None:
    """Set Neopixel RGB color via 0xC00B or 0xC00A [0x10, r, g, b]."""
    for val, name in [(r, "r"), (g, "g"), (b, "b")]:
        if not (0 <= val <= 255):
            raise UsageError(f"{name} must be 0-255")
    try:
        await conn.write(chars._u16(0xC00B), bytes([r, g, b]))
    except GattError:
        await conn.write(OLED_CHAR_UUID, bytes([0x10, r, g, b]))
    ui.ok(f"neopixel: RGB({r},{g},{b})")


async def run(args: argparse.Namespace) -> int:
    from . import resolve_target

    target = await resolve_target(args)
    async with transport.Connection(target) as conn:
        oled_cmd = args.oled_cmd

        if oled_cmd == "restore":
            await execute_restore(conn)

        elif oled_cmd == "status":
            page_id_str = args.page_id.lower()
            if page_id_str in STATUS_PAGES:
                page_id = STATUS_PAGES[page_id_str]
            else:
                try:
                    page_id = int(page_id_str)
                except ValueError:
                    raise UsageError(
                        f"unknown page_id {args.page_id!r}. "
                        f"use: {', '.join(STATUS_PAGES.keys())} or 0-4"
                    )
            if not (0 <= page_id <= 4):
                raise UsageError("page_id must be 0-4")
            if not (0 <= args.value <= 255):
                raise UsageError("value must be 0-255")
            await execute_status(conn, page_id, args.value)

        elif oled_cmd == "ping":
            await execute_ping(conn)

        elif oled_cmd == "driver":
            await execute_driver(conn, args.driver_name)

    return 0
