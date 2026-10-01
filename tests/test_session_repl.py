import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from pwnpet_cli.commands import session_cmd, addon_cmd
from pwnpet_cli.errors import UsageError


def run(coro):
    return asyncio.run(coro)


def _fake_conn(read_value: bytes = b""):
    conn = MagicMock()
    conn.read = AsyncMock(return_value=read_value)
    conn.write = AsyncMock()
    conn.is_connected = True
    return conn


class TestSessionReplDispatch:
    def test_session_addon_anim_spaced(self):
        conn = _fake_conn()
        run(session_cmd._dispatch(conn, "addon", ["anim", "2"]))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_ANIM_MODE, 2]),
        )

    def test_session_addon_anim_compact(self):
        conn = _fake_conn()
        run(session_cmd._dispatch(conn, "addon", ["anim3"]))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_ANIM_MODE, 3]),
        )

    def test_session_addon_set(self):
        conn = _fake_conn()
        run(session_cmd._dispatch(conn, "addon", ["set", "blush", "1"]))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_LED_SET, 0x02, 0x01]),
        )

    def test_session_addon_blink(self):
        conn = _fake_conn()
        run(session_cmd._dispatch(conn, "addon", ["blink", "sauce", "3"]))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_LED_BLINK, 0x04, 0x03]),
        )

    def test_session_addon_off(self):
        conn = _fake_conn()
        run(session_cmd._dispatch(conn, "addon", ["off"]))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_LED_ALL_OFF]),
        )

    def test_session_feed_and_pet(self):
        conn = _fake_conn()
        run(session_cmd._dispatch(conn, "feed", ["80"]))
        conn.write.assert_called_once()

        conn = _fake_conn()
        run(session_cmd._dispatch(conn, "pet", []))
        conn.write.assert_called_once()

    def test_session_oled_restore(self):
        conn = _fake_conn()
        run(session_cmd._dispatch(conn, "oled", ["restore"]))
        conn.write.assert_called_once()
