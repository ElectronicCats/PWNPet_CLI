"""Output renderers — pure functions, no I/O.

Per spec §7, all formatting is plain ASCII. No colors, no Unicode
tables, no deps beyond stdlib.
"""

from __future__ import annotations

import re

_STATE_NAMES: dict[int, str] = {
    0: "temeroso",
    1: "curioso",
    2: "leal",
    3: "paranoia",
    4: "muerto (salud)",
    5: "muerto (gordito)",
    6: "hambriento",
}

# Capture: 20 bytes total, starts "PWNPET{", 12 lowercase hex chars, "}".
_FLAG_RE = re.compile(rb"^PWNPET\{[0-9a-f]{12}\}$")


def render_state(byte: int) -> str:
    return _STATE_NAMES.get(byte, f"unknown({byte})")


def render_u16_le(b: bytes) -> int:
    return int.from_bytes(b, "little")


def render_utf8(b: bytes) -> str:
    """UTF-8 with trailing NULs stripped (badge name field convention)."""
    return b.rstrip(b"\x00").decode("utf-8", errors="replace")


def render_bool(b: bytes) -> str:
    return "true" if b and b[0] else "false"


def render_bytes_smart(b: bytes) -> str:
    """If b is a PWNPET flag string, return its ASCII; else lowercase hex."""
    if len(b) == 20 and _FLAG_RE.match(b):
        return b.decode("ascii")
    return b.hex(" ")


def parse_mission_list(raw: bytes) -> list[tuple[int, bool]]:
    """Decode 0xFE08 wire format → [(mission_id, is_completed), ...]."""
    if not raw:
        return []
    n = raw[0]
    missions: list[tuple[int, bool]] = []
    for i in range(n):
        base = 1 + i * 2
        if base + 1 >= len(raw):
            break
        missions.append((raw[base], raw[base + 1] != 0))
    return missions


# Field display order + label formatting for `status` (spec §7).
# Public so ui.py can iterate without duplicating the list.
STATUS_FIELDS: list[tuple[str, str]] = [
    ("owner_name", "owner"),
    ("species_id", "species"),
    ("name", "name"),
    ("happiness", "happiness"),
    ("hungry", "hungry"),
    ("health", "health"),
    ("state", "state"),
    ("xp", "xp"),
    ("sensor_value", "sensor_value"),
    ("all_missions_done", "all_missions_done"),
]

RANGED_FIELDS: frozenset[str] = frozenset({"happiness", "hungry", "health"})
