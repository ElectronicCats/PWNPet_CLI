import pytest

from pwnpet_cli import format as fmt


class TestRenderState:
    @pytest.mark.parametrize(
        "byte,expected",
        [
            (0, "temeroso"),
            (1, "curioso"),
            (2, "leal"),
            (3, "paranoia"),
            (4, "muerto (salud)"),
            (5, "muerto (gordito)"),
            (6, "hambriento"),
        ],
    )
    def test_known_states(self, byte, expected):
        assert fmt.render_state(byte) == expected

    def test_unknown_state(self):
        assert fmt.render_state(99) == "unknown(99)"


class TestRenderU16Le:
    def test_decodes_little_endian(self):
        assert fmt.render_u16_le(b"\x01\x00") == 1
        assert fmt.render_u16_le(b"\x00\x01") == 256

    def test_empty_bytes(self):
        assert fmt.render_u16_le(b"") == 0


class TestRenderUtf8:
    def test_strips_trailing_nuls(self):
        assert fmt.render_utf8(b"hello\x00\x00") == "hello"

    def test_no_trailing_nuls(self):
        assert fmt.render_utf8(b"hello") == "hello"

    def test_invalid_utf8_is_replaced(self):
        assert fmt.render_utf8(b"\xff\xfe") == "��"


class TestRenderBool:
    def test_true(self):
        assert fmt.render_bool(b"\x01") == "true"

    def test_false_zero_byte(self):
        assert fmt.render_bool(b"\x00") == "false"

    def test_false_empty(self):
        assert fmt.render_bool(b"") == "false"


class TestRenderBytesSmart:
    def test_renders_pwnpet_flag_as_ascii(self):
        flag = b"PWNPET{0123456789ab}"
        assert fmt.render_bytes_smart(flag) == flag.decode("ascii")

    def test_renders_non_flag_as_hex(self):
        assert fmt.render_bytes_smart(b"\xde\xad") == "de ad"

    def test_wrong_length_falls_back_to_hex(self):
        # 19 bytes, not 20, must not match flag regex
        short_flag = b"PWNPET{0123456789a}"
        assert fmt.render_bytes_smart(short_flag) == short_flag.hex(" ")

    def test_uppercase_hex_is_not_a_flag(self):
        flag = b"PWNPET{0123456789AB}"
        assert fmt.render_bytes_smart(flag) == flag.hex(" ")


class TestParseMissionList:
    def test_empty_raw(self):
        assert fmt.parse_mission_list(b"") == []

    def test_single_mission_completed(self):
        raw = bytes([1, 5, 1])
        assert fmt.parse_mission_list(raw) == [(5, True)]

    def test_single_mission_incomplete(self):
        raw = bytes([1, 5, 0])
        assert fmt.parse_mission_list(raw) == [(5, False)]

    def test_multiple_missions(self):
        raw = bytes([2, 1, 1, 2, 0])
        assert fmt.parse_mission_list(raw) == [(1, True), (2, False)]

    def test_truncated_payload_stops_early(self):
        # count says 2 missions but only one full pair is present
        raw = bytes([2, 1, 1])
        assert fmt.parse_mission_list(raw) == [(1, True)]
