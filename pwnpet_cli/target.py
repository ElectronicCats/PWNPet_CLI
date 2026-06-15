"""Persist the last-used badge target so commands don't need --target every time.

File: ~/.config/pwnpet/last_target.json
Schema: {"addr": "AA:BB:CC:DD:EE:FF", "name": "PwnPet_1234" | null}
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import ui

# Treat empty XDG_CONFIG_HOME as unset, per XDG Base Directory Specification.
_xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
CONFIG_DIR: Path = Path(_xdg) / "pwnpet"
TARGET_FILE: Path = CONFIG_DIR / "last_target.json"


def load() -> tuple[str, str | None] | None:
    """Return (addr, name) or None if no target stored or file is malformed."""
    if not TARGET_FILE.exists():
        return None
    try:
        data = json.loads(TARGET_FILE.read_text())
        addr = data["addr"]
        name = data.get("name")
        return (addr, name)
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        ui.warn(f"malformed last_target.json ignored: {exc}")
        return None


def save(addr: str, name: str | None = None) -> None:
    """Persist (addr, name). Creates parent dir if missing."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"addr": addr, "name": name}
    tmp = TARGET_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(TARGET_FILE)


def clear() -> None:
    """Delete the stored target file. No-op if missing."""
    try:
        TARGET_FILE.unlink()
    except FileNotFoundError:
        pass


def format_for_show() -> str:
    """Render the stored target for `pwnpet target show`."""
    loaded = load()
    if loaded is None:
        return "(none)"
    addr, name = loaded
    if name:
        return f"{name}   {addr}"
    return addr
