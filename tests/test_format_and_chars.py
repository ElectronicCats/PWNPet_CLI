import pytest
from pwnpet_cli import chars, format as fmt


class TestFormatAndChars:
    def test_u16_resolution(self):
        assert chars.resolve("0xFE01") == "0000fe01-0000-1000-8000-00805f9b34fb"
        assert chars.resolve("species_id") == "0000fe01-0000-1000-8000-00805f9b34fb"
        assert chars.resolve("led_control") == "0000c00a-0000-1000-8000-00805f9b34fb"

    def test_render_u16_le(self):
        assert fmt.render_u16_le(bytes([0x34, 0x12])) == 0x1234
        assert fmt.render_u16_le(bytes([0x00])) == 0

    def test_render_bool(self):
        assert fmt.render_bool(bytes([1])) == "true"
        assert fmt.render_bool(bytes([0])) == "false"
        assert fmt.render_bool(b"") == "false"

    def test_render_state(self):
        assert fmt.render_state(0) == "temeroso"
        assert fmt.render_state(1) == "curioso"
        assert fmt.render_state(2) == "leal"
        assert fmt.render_state(3) == "paranoia"
        assert fmt.render_state(4) == "muerto (salud)"
        assert fmt.render_state(5) == "muerto (gordito)"
        assert fmt.render_state(6) == "hambriento"
        assert fmt.render_state(bytes([2])) == "leal"

    def test_render_utf8(self):
        assert fmt.render_utf8(b"PwnPet_DA44") == "PwnPet_DA44"
