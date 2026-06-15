"""Public-name whitelist for badge characteristics.

Per spec §4 and the "no hints" decision, only public chars (game
state visible at all times + named interaction inputs) are named
here. Gated flag chars (master_flag, ability_flag, secret_journal,
flag_notify) are intentionally NOT in the whitelist; they are
reachable only by raw UUID via `read 0xDE01` etc.
"""

from __future__ import annotations

# 16-bit BLE UUIDs are expanded into the standard 128-bit base.
_BASE_UUID = "0000{short:04x}-0000-1000-8000-00805f9b34fb"


def _u16(short: int) -> str:
    return _BASE_UUID.format(short=short)


# Public name → 128-bit UUID string (lowercase form expected by bleak).
NAME_TO_UUID: dict[str, str] = {
    # FE0X — Vida (R)
    "species_id":   _u16(0xFE01),
    "name":         _u16(0xFE02),
    "happiness":    _u16(0xFE03),
    "hungry":       _u16(0xFE04),
    "state":        _u16(0xFE05),
    "xp":           _u16(0xFE06),
    "health":       _u16(0xFE07),
    "mission_list": _u16(0xFE08),
    # DE0X — Core (R, public bool only)
    "all_missions_done": _u16(0xDE02),
    # FA0X — Habilidad (R, public sensor only)
    "sensor_value": _u16(0xFA01),
    # 5E0X — Memoria (R, public dream only)
    "dream_log": _u16(0x5E01),
    # C00X — Interacción (W + CTF)
    "feed":         _u16(0xC001),
    "pet":          _u16(0xC002),
    "play":         _u16(0xC003),
    "rename":       _u16(0xC004),
    "mission_flag": _u16(0xC005),
    "mission_hint":    _u16(0xC006),
    "factory_reset":   _u16(0xC007),
    "friendship_cmd":  _u16(0xC008),  # R+W: write FRIENDSHIP_BLE_* opcode, read result
    # Memoria input (W)
    "passkey_input": _u16(0x5E02),
}


# Species id → display name. New species (id >= 0x0003) appended as authored.
SPECIES_TABLE: dict[int, str] = {
    0x0001: "stub",
    0x0002: "Pwn Cat",
    0x0003: "Pwn Llama",
}


def resolve(name_or_uuid: str) -> str:
    """Resolve a public name or 0xNNNN short-UUID to a full 128-bit UUID.

    Accepts:
      - public names from NAME_TO_UUID (e.g. "happiness")
      - 16-bit shorts with 0x prefix, case-insensitive (e.g. "0xFE03", "0xfe03")

    Raises KeyError on unknown names. UUIDs that are not in the whitelist
    are still expanded if the form is well-formed — this is BLE-correct
    (any UUID can be read/written; F8 does not gate by name).
    """
    if name_or_uuid in NAME_TO_UUID:
        return NAME_TO_UUID[name_or_uuid]
    if name_or_uuid.lower().startswith("0x") and len(name_or_uuid) == 6:
        try:
            short = int(name_or_uuid, 16)
        except ValueError as exc:
            raise KeyError(name_or_uuid) from exc
        return _u16(short)
    raise KeyError(name_or_uuid)


def render_species_id(species_id: int) -> str:
    """`0x0002 (Pwn Cat)` or `0x9999 (unknown)`."""
    name = SPECIES_TABLE.get(species_id, "unknown")
    return f"0x{species_id:04x} ({name})"


# Decoder for each readable char name. Chars omitted here fall back to
# render_bytes_smart. Must be kept consistent with NAME_TO_UUID above.
from . import format as fmt  # noqa: E402 — local import avoids circular dep at module level

DECODERS: dict[str, object] = {
    "species_id":        lambda b: render_species_id(fmt.render_u16_le(b)),
    "name":              fmt.render_utf8,
    "happiness":         fmt.render_u16_le,
    "hungry":            fmt.render_u16_le,
    "health":            fmt.render_u16_le,
    "state":             lambda b: fmt.render_state(b[0] if b else 0),
    "xp":                fmt.render_u16_le,
    "sensor_value":      fmt.render_u32_le,
    "dream_log":         fmt.render_utf8,
    "all_missions_done": fmt.render_bool,
}
