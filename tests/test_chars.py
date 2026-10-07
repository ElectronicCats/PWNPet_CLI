import pytest

from pwnpet_cli import chars


class TestResolve:
    def test_public_name(self):
        assert chars.resolve("happiness") == "0000fe03-0000-1000-8000-00805f9b34fb"

    def test_short_uuid_lowercase(self):
        assert chars.resolve("0xfe03") == "0000fe03-0000-1000-8000-00805f9b34fb"

    def test_short_uuid_uppercase_prefix_accepted(self):
        # resolve() lowercases for the 0x check, only the prefix case is normalized
        assert chars.resolve("0xFE03") == "0000fe03-0000-1000-8000-00805f9b34fb"

    def test_gated_char_not_in_whitelist_by_name(self):
        with pytest.raises(KeyError):
            chars.resolve("master_flag")

    def test_unknown_garbage_raises(self):
        with pytest.raises(KeyError):
            chars.resolve("not_a_real_name")

    def test_malformed_short_uuid_raises(self):
        with pytest.raises(KeyError):
            chars.resolve("0xzzzz")


class TestRenderSpeciesId:
    def test_known_species(self):
        assert chars.render_species_id(0x0002) == "0x0002 (Pwn Cat)"

    def test_cloud_species(self):
        assert chars.render_species_id(0x0004) == "0x0004 (Pwn Cloud)"

    def test_unknown_species(self):
        assert chars.render_species_id(0x9999) == "0x9999 (unknown)"


class TestOwnerName:
    def test_owner_name_read_uuid(self):
        assert chars.resolve("owner_name") == "0000fe09-0000-1000-8000-00805f9b34fb"

    def test_set_owner_write_uuid(self):
        assert chars.resolve("set_owner") == "0000c009-0000-1000-8000-00805f9b34fb"

    def test_led_control_uuid(self):
        assert chars.resolve("led_control") == "0000c00a-0000-1000-8000-00805f9b34fb"

    def test_owner_name_decoder_is_utf8(self):
        # Accented name round-trips through the UTF-8 decoder.
        decoded = chars.DECODERS["owner_name"]("Jos\xe9".encode("utf-8") + b"\x00\x00")
        assert decoded == "Jos\xe9"


class TestDecodersConsistency:
    def test_decoders_keys_subset_of_name_to_uuid(self):
        assert set(chars.DECODERS.keys()) <= set(chars.NAME_TO_UUID.keys())

    def test_state_decoder_handles_empty_bytes(self):
        assert chars.DECODERS["state"](b"") == "temeroso"

    def test_species_id_decoder_roundtrip(self):
        decoded = chars.DECODERS["species_id"](b"\x02\x00")
        assert decoded == "0x0002 (Pwn Cat)"
