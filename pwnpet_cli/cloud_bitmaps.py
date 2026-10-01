"""Backward compatibility wrapper for bitmaps.py."""

from __future__ import annotations

from . import bitmaps
from .bitmaps import (
    EMBEDDED_CLOUD_SPRITES as EMBEDDED_SPRITES,
)

__all__ = [
    "EMBEDDED_SPRITES",
    "get_sprite",
]


def get_sprite(name: str, width: int = 80, addon_connected: bool = True) -> str:
    """Legacy get_sprite signature defaulting to cloud species."""
    return bitmaps.get_sprite(
        name, species="cloud", width=width, addon_connected=addon_connected
    )
