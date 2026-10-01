"""Dynamic PNG image renderer with embedded fallback — backward compatibility wrapper for bitmaps.py."""

from __future__ import annotations

from . import bitmaps
from .bitmaps import (
    EMBEDDED_CLOUD_SPRITES as EMBEDDED_SPRITES,
    HAS_PIL,
    STATE_TO_PNG,
    render_png_to_unicode,
)

__all__ = [
    "EMBEDDED_SPRITES",
    "HAS_PIL",
    "STATE_TO_PNG",
    "get_sprite",
    "render_png_to_unicode",
]


def get_sprite(name: str, width: int = 80, addon_connected: bool = True) -> str:
    """Legacy get_sprite signature defaulting to cloud species."""
    return bitmaps.get_sprite(
        name, species="cloud", width=width, addon_connected=addon_connected
    )
