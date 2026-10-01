import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from pwnpet_cli import chars
from pwnpet_cli.commands import led_cmd
from pwnpet_cli.errors import UsageError, GattError


def run(coro):
    return asyncio.run(coro)


def _fake_conn(read_value: bytes = b""):
    conn = MagicMock()
    conn.read = AsyncMock(return_value=read_value)
    conn.write = AsyncMock()
    conn.is_connected = True
    return conn


class TestOledExecution:
    def test_execute_restore(self):
        conn = _fake_conn()
        run(led_cmd.execute_restore(conn))
        conn.write.assert_called_once_with(
            led_cmd.OLED_CHAR_UUID, bytes([led_cmd.REG_OLED_RESTORE])
        )

    def test_execute_status(self):
        conn = _fake_conn()
        run(led_cmd.execute_status(conn, page_id=0, value=100))
        conn.write.assert_called_once_with(
            led_cmd.OLED_CHAR_UUID, bytes([led_cmd.REG_OLED_STATUS, 0, 100])
        )

    def test_execute_ping(self):
        conn = _fake_conn()
        run(led_cmd.execute_ping(conn))
        conn.write.assert_called_once_with(
            led_cmd.OLED_CHAR_UUID, bytes([led_cmd.REG_OLED_PING])
        )

    def test_execute_neopixel(self):
        conn = _fake_conn()
        run(led_cmd.execute_neopixel(conn, 255, 128, 0))
        conn.write.assert_called_once_with(chars._u16(0xC00B), bytes([255, 128, 0]))
