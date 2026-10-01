"""Unit tests for species-filtered bitmap rendering and sprite isolation."""

from __future__ import annotations

import pytest
from pwnpet_cli import bitmaps, cloud_bitmaps, ui


class TestSpeciesNormalization:
    def test_cat_species(self):
        assert bitmaps.normalize_species(0x0002) == "cat"
        assert bitmaps.normalize_species("0x0002") == "cat"
        assert bitmaps.normalize_species("0x0002 (Pwn Cat)") == "cat"
        assert bitmaps.normalize_species("cat") == "cat"
        assert bitmaps.normalize_species("Pwn Cat") == "cat"

    def test_llama_species(self):
        assert bitmaps.normalize_species(0x0003) == "llama"
        assert bitmaps.normalize_species("0x0003") == "llama"
        assert bitmaps.normalize_species("0x0003 (Pwn Llama)") == "llama"
        assert bitmaps.normalize_species("llama") == "llama"
        assert bitmaps.normalize_species("Pwn Llama") == "llama"

    def test_cloud_species(self):
        assert bitmaps.normalize_species(0x0004) == "cloud"
        assert bitmaps.normalize_species("0x0004") == "cloud"
        assert bitmaps.normalize_species("0x0004 (Pwn Cloud)") == "cloud"
        assert bitmaps.normalize_species("cloud") == "cloud"
        assert bitmaps.normalize_species("Pwn Cloud") == "cloud"
        assert bitmaps.normalize_species(None) == "cloud"

    def test_unknown_species(self):
        assert bitmaps.normalize_species(0x9999) == "unknown"
        assert bitmaps.normalize_species("unknown") == "unknown"
        assert bitmaps.normalize_species("dragon") == "unknown"


class TestSpriteIsolation:
    def test_cat_and_llama_do_not_render_terminal_sprites(self):
        # Badges with physical screens (Cat, Llama) do NOT render terminal sprites in CLI.
        cat_sprite = bitmaps.get_sprite("curious", species="cat")
        llama_sprite = bitmaps.get_sprite("curious", species="llama")

        assert cat_sprite == "", "Cat has a physical screen; CLI sprite must be empty"
        assert (
            llama_sprite == ""
        ), "Llama has a physical screen; CLI sprite must be empty"

    def test_cloud_renders_sprite_only_when_addon_connected(self):
        cloud_addon_off = bitmaps.get_sprite(
            "curious", species="cloud", addon_connected=False
        )
        cloud_addon_on = bitmaps.get_sprite(
            "curious", species="cloud", addon_connected=True
        )

        assert (
            cloud_addon_off == ""
        ), "Cloud sprite must be locked when Add-On is not connected"
        assert cloud_addon_on != "", "Cloud sprite must render when Add-On is connected"

    def test_unknown_species_returns_empty(self):
        assert bitmaps.get_sprite("curious", species=0x9999) == ""
        assert bitmaps.get_sprite("curious", species="unknown") == ""

    def test_cloud_bitmaps_backward_compatibility(self):
        legacy_sprite = cloud_bitmaps.get_sprite("curious", addon_connected=True)
        cloud_sprite = bitmaps.get_sprite(
            "curious", species="cloud", addon_connected=True
        )
        assert legacy_sprite == cloud_sprite


class TestUIPrintStatusSpeciesIntegration:
    def test_print_status_with_llama_no_terminal_sprite(self, capsys):
        values = {
            "species_id": "0x0003 (Pwn Llama)",
            "name": "LlamaTest",
            "happiness": "1000",
            "hungry": "500",
            "health": "1000",
            "state": "curioso",
            "xp": "10",
            "sensor_value": "0",
            "all_missions_done": "false",
            "owner_name": "Omar",
            "addon_connected": False,
        }
        ui.print_status(values)
        captured = capsys.readouterr().out
        assert "LlamaTest" in captured
        assert "0x0003 (Pwn Llama)" in captured

    def test_print_status_with_cloud_addon_connected_shows_sprite(self, capsys):
        values = {
            "species_id": "0x0004 (Pwn Cloud)",
            "name": "Cloudy",
            "happiness": "1000",
            "hungry": "500",
            "health": "1000",
            "state": "curioso",
            "xp": "10",
            "sensor_value": "0",
            "all_missions_done": "false",
            "owner_name": "Omar",
            "addon_connected": True,
        }
        ui.print_status(values)
        captured = capsys.readouterr().out
        cloud_sprite = bitmaps.get_sprite(
            "curioso", species="cloud", addon_connected=True
        )
        assert "Cloudy" in captured
        assert "0x0004 (Pwn Cloud)" in captured
        assert cloud_sprite in captured
