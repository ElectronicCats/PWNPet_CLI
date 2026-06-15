"""Input encoders. Per spec §6, parsing rules differ by command form:

  - verbs (feed, passkey)        : decimal
  - play <hex>                   : hex u32, 0x optional
  - write <char> <hex> payload   : hex bytes, 0x forbidden, even-length

ValueError raised on any malformed input. cli.py turns that into
UsageError (exit 1) with a human message.
"""

from __future__ import annotations

import re

_PLAY_HEX_RE = re.compile(r"^(0x)?[0-9a-fA-F]{8}$")
_PAYLOAD_HEX_RE = re.compile(r"^([0-9a-f]{2})*$")
_PASSKEY_RE = re.compile(r"^[0-9]{3}$")


def parse_passkey(s: str) -> bytes:
    """Three ASCII digits → three BCD bytes.

    "123" → b"\\x01\\x02\\x03".
    """
    if not _PASSKEY_RE.fullmatch(s):
        raise ValueError(f"passkey must be exactly 3 ASCII digits, got {s!r}")
    return bytes(int(c) for c in s)


def parse_play_hex(s: str) -> bytes:
    """u32 hex string → 4 bytes little-endian.

    Accepts `0xDEADBEEF`, `deadbeef`, mixed case. Rejects colons,
    `0X` (uppercase prefix), wrong length, non-hex chars.
    """
    if not _PLAY_HEX_RE.fullmatch(s):
        raise ValueError(f"play hex must be 8 hex chars (0x optional), got {s!r}")
    if s.startswith("0x"):
        s = s[2:]
    value = int(s, 16)
    return value.to_bytes(4, "little")


def parse_write_payload(s: str) -> bytes:
    """Hex bytes string → bytes. Empty string → b''.

    Even-length hex, case-insensitive. `0x` prefix forbidden so
    `write 0xFE03 32` parses unambiguously.
    """
    if not _PAYLOAD_HEX_RE.fullmatch(s.lower()):
        raise ValueError(
            f"write payload must be even-length hex bytes (no 0x prefix), got {s!r}"
        )
    return bytes.fromhex(s)
