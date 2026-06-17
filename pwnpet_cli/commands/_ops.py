"""Reusable async BLE operations shared across command modules."""

from __future__ import annotations

from ..errors import UsageError
from .. import chars, format as fmt, transport


async def fetch_status(conn: transport.Connection) -> dict[str, object]:
    """Read and decode all 9 public status characteristics."""
    species_b = await conn.read(chars.NAME_TO_UUID["species_id"])
    name_b = await conn.read(chars.NAME_TO_UUID["name"])
    happy_b = await conn.read(chars.NAME_TO_UUID["happiness"])
    hungry_b = await conn.read(chars.NAME_TO_UUID["hungry"])
    health_b = await conn.read(chars.NAME_TO_UUID["health"])
    state_b = await conn.read(chars.NAME_TO_UUID["state"])
    xp_b = await conn.read(chars.NAME_TO_UUID["xp"])
    sensor_b = await conn.read(chars.NAME_TO_UUID["sensor_value"])
    done_b = await conn.read(chars.NAME_TO_UUID["all_missions_done"])
    return {
        "species_id": chars.render_species_id(fmt.render_u16_le(species_b)),
        "name": fmt.render_utf8(name_b),
        "happiness": fmt.render_u16_le(happy_b),
        "hungry": fmt.render_u16_le(hungry_b),
        "health": fmt.render_u16_le(health_b),
        "state": fmt.render_state(state_b[0] if state_b else 0),
        "xp": fmt.render_u16_le(xp_b),
        "sensor_value": fmt.render_u16_le(sensor_b),
        "all_missions_done": fmt.render_bool(done_b),
    }


async def fetch_missions(
    conn: transport.Connection,
) -> tuple[str, list[tuple[int, bool]]]:
    """Return (creature_name, missions) from the device."""
    name_b = await conn.read(chars.NAME_TO_UUID["name"])
    list_b = await conn.read(chars.NAME_TO_UUID["mission_list"])
    return fmt.render_utf8(name_b), fmt.parse_mission_list(list_b)


async def fetch_mission_hint(conn: transport.Connection, mid: int) -> str:
    """Request and return the hint for *mid*. Empty string if the firmware has none."""
    await conn.write(chars.NAME_TO_UUID["mission_hint"], bytes([mid]))
    raw = await conn.read(chars.NAME_TO_UUID["mission_hint"])
    return raw.rstrip(b"\x00").decode("utf-8", errors="replace")


async def fetch_flag(conn: transport.Connection, mid: int) -> bytes | None:
    """Validate *mid* and return raw flag bytes, or None if the mission is incomplete.

    Raises UsageError if *mid* is not a known mission on this device.
    """
    list_b = await conn.read(chars.NAME_TO_UUID["mission_list"])
    missions = fmt.parse_mission_list(list_b)
    known_ids = {m[0] for m in missions}
    completed_ids = {m[0] for m in missions if m[1]}

    if mid not in known_ids:
        raise UsageError(f"mission {mid} does not exist on this badge")
    if mid not in completed_ids:
        return None

    await conn.write(chars.NAME_TO_UUID["mission_flag"], bytes([mid]))
    return await conn.read(chars.NAME_TO_UUID["mission_flag"])
