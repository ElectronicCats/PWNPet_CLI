"""`pwnpet clock` -- control 12-LED Charlieplexing countdown ring on Villa Cloud badge.

The Badge exposes characteristic 0xC00A (oled_control / peripheral bridge)
which accepts opcode 0x40 for Clock / Countdown ring manipulation.

Usage:
  pwnpet clock countdown <sec>     Start proportional countdown timer (contador inverso)
  pwnpet clock reverse             Start continuous reverse ticking (12 -> 11 -> ... -> 1)
  pwnpet clock spin                Start fast counter-clockwise spin animation
  pwnpet clock forward             Start fast clockwise spin animation
  pwnpet clock sweep               Start pendulum radar sweep
  pwnpet clock pulse               Flash all 12 LEDs 3 times
  pwnpet clock hour <1-12>         Light single hour LED
  pwnpet clock mask <mask>         Set custom 12-bit LED mask (hex or int)
  pwnpet clock off                 Turn off all 12 dial LEDs
  pwnpet clock status              Query active mode and remaining countdown seconds
"""

from __future__ import annotations

import argparse

from .. import chars, transport, ui
from ..errors import GattError, UsageError

OLED_CHAR_UUID = chars._u16(0xC00A)

# Opcode for Clock Dial control
OP_CLOCK_CONTROL = 0x40

SUB_OFF = 0x00
SUB_COUNTDOWN = 0x01
SUB_REVERSE_TICK = 0x02
SUB_REVERSE_SPIN = 0x03
SUB_FORWARD_SPIN = 0x04
SUB_SWEEP = 0x05
SUB_PULSE = 0x06
SUB_SET_HOUR = 0x07
SUB_SET_MASK = 0x08
SUB_REFLEX = 0x09
SUB_HIT = 0x0A
SUB_SECRET = 0x0B
SUB_AMBIENT = 0x0C
SUB_STATUS = 0xFF

MODE_NAMES = {
    0: "OFF",
    1: "COUNTDOWN_DRAIN",
    2: "REVERSE_TICK",
    3: "REVERSE_SPIN",
    4: "FORWARD_SPIN",
    5: "SWEEP",
    6: "PULSE",
    7: "ATTACH",
    8: "STATIC_HOUR",
    9: "STATIC_MASK",
    10: "CREATURE_AMBIENT",
    11: "REACTION_FEED",
    12: "REACTION_PET",
    13: "REACTION_PLAY",
    14: "REACTION_CELEBRATE",
    15: "REACTION_ILUMINADO",
    16: "REACTION_SECRET",
    17: "GAME_REFLEX",
}


def _parse_mask(val: str) -> int:
    try:
        m = int(val, 0)
    except ValueError:
        raise UsageError(
            f"invalid mask '{val}', expected hex (0xFFF) or decimal integer"
        )
    if not (0 <= m <= 0xFFF):
        raise UsageError(f"mask 0x{m:X} out of range (max 12 bits: 0x000..0xFFF)")
    return m


async def execute_status(conn: transport.Connection) -> tuple[int, int]:
    try:
        await conn.write(OLED_CHAR_UUID, bytes([OP_CLOCK_CONTROL, SUB_STATUS]))
        resp = await conn.read(OLED_CHAR_UUID)
        if resp and len(resp) >= 3:
            mode = resp[0]
            rem_sec = resp[1] | (resp[2] << 8)
            mode_str = MODE_NAMES.get(mode, f"UNKNOWN({mode})")
            ui.ok(f"CLOCK: mode={mode_str} ({mode}), remaining={rem_sec}s")
            return (mode, rem_sec)
        ui.warn("CLOCK: empty or incomplete status response")
        return (0, 0)
    except GattError as exc:
        raise GattError(f"clock status: {exc.message}") from exc


async def execute_countdown(conn: transport.Connection, seconds: int) -> None:
    if seconds <= 0 or seconds > 65535:
        raise UsageError("countdown seconds must be between 1 and 65535")
    payload = bytes(
        [OP_CLOCK_CONTROL, SUB_COUNTDOWN, seconds & 0xFF, (seconds >> 8) & 0xFF]
    )
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok(f"CLOCK: countdown timer started ({seconds}s)")
    except GattError as exc:
        raise GattError(f"clock countdown: {exc.message}") from exc


async def execute_reverse(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_REVERSE_TICK])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("CLOCK: reverse ticking active (12 -> 11 -> ... -> 1)")
    except GattError as exc:
        raise GattError(f"clock reverse: {exc.message}") from exc


async def execute_spin(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_REVERSE_SPIN])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("CLOCK: reverse spin active")
    except GattError as exc:
        raise GattError(f"clock spin: {exc.message}") from exc


async def execute_forward(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_FORWARD_SPIN])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("CLOCK: forward spin active")
    except GattError as exc:
        raise GattError(f"clock forward: {exc.message}") from exc


async def execute_sweep(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_SWEEP])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("CLOCK: sweep active")
    except GattError as exc:
        raise GattError(f"clock sweep: {exc.message}") from exc


async def execute_pulse(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_PULSE])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("CLOCK: alert pulse triggered")
    except GattError as exc:
        raise GattError(f"clock pulse: {exc.message}") from exc


async def execute_hour(conn: transport.Connection, hour: int) -> None:
    if hour < 1 or hour > 12:
        raise UsageError("hour must be between 1 and 12")
    payload = bytes([OP_CLOCK_CONTROL, SUB_SET_HOUR, hour])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok(f"CLOCK: hour {hour} set")
    except GattError as exc:
        raise GattError(f"clock hour: {exc.message}") from exc


async def execute_mask(conn: transport.Connection, mask_val: str | int) -> None:
    m = _parse_mask(str(mask_val)) if isinstance(mask_val, str) else mask_val
    payload = bytes([OP_CLOCK_CONTROL, SUB_SET_MASK, m & 0xFF, (m >> 8) & 0xFF])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok(f"CLOCK: mask 0x{m:03X} set")
    except GattError as exc:
        raise GattError(f"clock mask: {exc.message}") from exc


async def execute_off(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_OFF])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("CLOCK: all dial LEDs OFF")
    except GattError as exc:
        raise GattError(f"clock off: {exc.message}") from exc


async def execute_reflex(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_REFLEX])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok(
            "REFLEX: Reflex Wheel minigame started! Hit when LED reaches 12:00 (Top / Azure)"
        )
    except GattError as exc:
        raise GattError(f"reflex start: {exc.message}") from exc


async def execute_hit(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_HIT])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("REFLEX: hit triggered!")
    except GattError as exc:
        raise GattError(f"reflex hit: {exc.message}") from exc


async def execute_secret(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_SECRET])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("SUPERNOVA: secret cosmic celebration reaction triggered!")
    except GattError as exc:
        raise GattError(f"secret supernova: {exc.message}") from exc


async def execute_ambient(conn: transport.Connection) -> None:
    payload = bytes([OP_CLOCK_CONTROL, SUB_AMBIENT])
    try:
        await conn.write(OLED_CHAR_UUID, payload)
        ui.ok("CLOCK: creature visual ambient mode active")
    except GattError as exc:
        raise GattError(f"clock ambient: {exc.message}") from exc


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "clock",
        help="Control 12-LED countdown dial (Villa Cloud Ekoparty 2026).",
    )
    from . import add_target_arg

    add_target_arg(parser)

    sub = parser.add_subparsers(dest="clock_cmd", metavar="<action>")
    sub.required = True

    # 1. STATUS
    sub.add_parser("status", help="Get clock mode & countdown remaining seconds")

    # 2. COUNTDOWN
    p_cd = sub.add_parser("countdown", help="Start proportional countdown timer")
    p_cd.add_argument("seconds", type=int, help="Duration in seconds (e.g. 10, 30, 60)")

    # 3. REVERSE
    sub.add_parser(
        "reverse", help="Start continuous reverse ticking (12 -> 11 -> ... -> 1)"
    )

    # 4. SPIN
    sub.add_parser("spin", help="Start fast reverse spin")

    # 5. FORWARD
    sub.add_parser("forward", help="Start fast forward spin")

    # 6. SWEEP
    sub.add_parser("sweep", help="Start sweep animation")

    # 7. PULSE
    sub.add_parser("pulse", help="Trigger 3-flash alert pulse")

    # 8. HOUR
    p_hr = sub.add_parser("hour", help="Light single hour position (1-12)")
    p_hr.add_argument("hour", type=int, help="Hour index 1..12")

    # 9. MASK
    p_mask = sub.add_parser("mask", help="Set custom 12-bit LED mask")
    p_mask.add_argument("mask", help="Mask in hex (0xFFF) or decimal")

    # 10. OFF
    sub.add_parser("off", help="Turn off all 12 dial LEDs")

    parser.set_defaults(handler=run)


async def run(args: argparse.Namespace) -> int:
    from . import resolve_target

    target = await resolve_target(args)
    async with transport.Connection(target) as conn:
        cmd = args.clock_cmd
        if cmd == "status":
            await execute_status(conn)
        elif cmd == "countdown":
            await execute_countdown(conn, args.seconds)
        elif cmd == "reverse":
            await execute_reverse(conn)
        elif cmd == "spin":
            await execute_spin(conn)
        elif cmd == "forward":
            await execute_forward(conn)
        elif cmd == "sweep":
            await execute_sweep(conn)
        elif cmd == "pulse":
            await execute_pulse(conn)
        elif cmd == "hour":
            await execute_hour(conn, args.hour)
        elif cmd == "mask":
            await execute_mask(conn, args.mask)
        elif cmd == "off":
            await execute_off(conn)
    return 0
