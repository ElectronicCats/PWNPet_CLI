"""Helpers shared across command modules (read_cmd, session_cmd, …)."""

from __future__ import annotations

from .. import chars, format as fmt, ui

DECODERS = chars.DECODERS


def decode(name_or_uuid: str, raw: bytes) -> str:
    if name_or_uuid in DECODERS:
        return str(DECODERS[name_or_uuid](raw))  # type: ignore[operator]
    return fmt.render_bytes_smart(raw)


def print_decoded(value: str) -> None:
    if value.startswith("PWNPET{"):
        ui.console.print(f"[bold bright_yellow]{value}[/]")
    else:
        ui.console.print(value)
