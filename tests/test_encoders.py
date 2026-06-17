import pytest

from pwnpet_cli import encoders


class TestParsePasskey:
    def test_valid_digits(self):
        assert encoders.parse_passkey("123") == bytes([1, 2, 3])

    def test_leading_zero(self):
        assert encoders.parse_passkey("007") == bytes([0, 0, 7])

    @pytest.mark.parametrize("bad", ["12", "1234", "12a", "", "abc", " 12"])
    def test_invalid_raises(self, bad):
        with pytest.raises(ValueError):
            encoders.parse_passkey(bad)


class TestParsePlayHex:
    def test_no_prefix(self):
        assert encoders.parse_play_hex("deadbeef") == b"\xef\xbe\xad\xde"

    def test_with_0x_prefix(self):
        assert encoders.parse_play_hex("0xdeadbeef") == b"\xef\xbe\xad\xde"

    def test_mixed_case(self):
        assert encoders.parse_play_hex("DeAdBeEf") == b"\xef\xbe\xad\xde"

    @pytest.mark.parametrize(
        "bad",
        [
            "0XDEADBEEF",  # uppercase prefix rejected
            "dead:beef",  # colons rejected
            "deadbee",  # too short
            "deadbeefa",  # too long
            "deadbeeg",  # non-hex char
            "",
        ],
    )
    def test_invalid_raises(self, bad):
        with pytest.raises(ValueError):
            encoders.parse_play_hex(bad)


class TestParseWritePayload:
    def test_empty_string(self):
        assert encoders.parse_write_payload("") == b""

    def test_even_length_hex(self):
        assert encoders.parse_write_payload("fe03") == b"\xfe\x03"

    def test_case_insensitive(self):
        assert encoders.parse_write_payload("FE03") == b"\xfe\x03"

    @pytest.mark.parametrize(
        "bad",
        [
            "0xfe03",  # 0x prefix forbidden
            "fe0",  # odd length
            "fg03",  # non-hex char
        ],
    )
    def test_invalid_raises(self, bad):
        with pytest.raises(ValueError):
            encoders.parse_write_payload(bad)
