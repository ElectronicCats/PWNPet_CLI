import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from pwnpet_cli import chars
from pwnpet_cli.commands import addon_cmd
from pwnpet_cli.errors import UsageError, GattError


def run(coro):
    return asyncio.run(coro)


def _fake_conn(read_value: bytes = b""):
    conn = MagicMock()
    conn.read = AsyncMock(return_value=read_value)
    conn.write = AsyncMock()
    conn.is_connected = True
    return conn


class TestAddonMaskParsing:
    def test_individual_leds(self):
        assert addon_cmd._parse_mask("eyes") == 0x01
        assert addon_cmd._parse_mask("ojos") == 0x01
        assert addon_cmd._parse_mask("blush") == 0x02
        assert addon_cmd._parse_mask("mejillas") == 0x02
        assert addon_cmd._parse_mask("sauce") == 0x04
        assert addon_cmd._parse_mask("salsa") == 0x04

    def test_all_leds(self):
        assert addon_cmd._parse_mask("all") == 0x07
        assert addon_cmd._parse_mask("todos") == 0x07

    def test_numeric_mask(self):
        assert addon_cmd._parse_mask("0x03") == 0x03
        assert addon_cmd._parse_mask("5") == 0x05

    def test_invalid_mask(self):
        with pytest.raises(UsageError):
            addon_cmd._parse_mask("invalid_led_name")


class TestAddonCommands:
    def test_addon_ping_success(self):
        conn = _fake_conn(read_value=bytes([0xAD]))
        run(addon_cmd.execute_ping(conn))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID, bytes([addon_cmd.OP_ADDON_PING])
        )
        conn.read.assert_called_once_with(addon_cmd.OLED_CHAR_UUID)

    def test_addon_anim_modes(self):
        for mode in range(8):
            conn = _fake_conn()
            run(addon_cmd.execute_anim(conn, mode))
            conn.write.assert_called_once_with(
                addon_cmd.OLED_CHAR_UUID,
                bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_ANIM_MODE, mode]),
            )

    def test_addon_anim_invalid(self):
        conn = _fake_conn()
        with pytest.raises(UsageError):
            run(addon_cmd.execute_anim(conn, 8))
        with pytest.raises(UsageError):
            run(addon_cmd.execute_anim(conn, -1))

    def test_addon_set_led(self):
        conn = _fake_conn()
        run(addon_cmd.execute_set(conn, "eyes", 1))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_LED_SET, 0x01, 0x01]),
        )

        conn = _fake_conn()
        run(addon_cmd.execute_set(conn, "sauce", 0))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_LED_SET, 0x04, 0x00]),
        )

    def test_addon_blink(self):
        conn = _fake_conn()
        run(addon_cmd.execute_blink(conn, "all", 2))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_LED_BLINK, 0x07, 0x02]),
        )

    def test_addon_blink_invalid_period(self):
        conn = _fake_conn()
        with pytest.raises(UsageError):
            run(addon_cmd.execute_blink(conn, "all", 0))
        with pytest.raises(UsageError):
            run(addon_cmd.execute_blink(conn, "all", 256))

    def test_addon_off(self):
        conn = _fake_conn()
        run(addon_cmd.execute_off(conn))
        conn.write.assert_called_once_with(
            addon_cmd.OLED_CHAR_UUID,
            bytes([addon_cmd.OP_ADDON_WRITE, addon_cmd.REG_LED_ALL_OFF]),
        )
