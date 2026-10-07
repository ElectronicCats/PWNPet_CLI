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
    def test_cat_llama_and_cloud_render_distinct_sprites(self):
        cat_sprite = bitmaps.get_sprite("curious", species="cat")
        llama_sprite = bitmaps.get_sprite("curious", species="llama")
        cloud_sprite = bitmaps.get_sprite("curious", species="cloud", addon_connected=True)

        assert cat_sprite != "", "Cat species should render Cat ASCII sprite"
        assert llama_sprite != "", "Llama species should render Llama ASCII sprite"
        assert cloud_sprite != "", "Cloud species should render Cloud ASCII sprite"

        assert cat_sprite != llama_sprite, "Cat sprite must not equal Llama sprite"
        assert cat_sprite != cloud_sprite, "Cat sprite must not equal Cloud sprite"
        assert llama_sprite != cloud_sprite, "Llama sprite must not equal Cloud sprite"

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
        legacy_sprite = cloud_bitmaps.get_sprite("curious")
        cloud_sprite = bitmaps.get_sprite("curious", species="cloud")
        assert legacy_sprite == cloud_sprite



class TestUIPrintStatusSpeciesIntegration:
    def test_print_status_with_llama(self, capsys):
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
        }
        ui.print_status(values)
        captured = capsys.readouterr().out
        llama_sprite = bitmaps.get_sprite("curioso", species="llama")
        cloud_sprite = bitmaps.get_sprite("curioso", species="cloud")

        assert "LlamaTest" in captured
        assert "0x0003 (Pwn Llama)" in captured

    def test_print_status_dead_states(self, capsys):
        for state_name in ["muerto_salud", "muerto (salud)", "muerto_gordito", "muerto (gordito)"]:
            values = {
                "species_id": "0x0004 (Pwn Cloud)",
                "name": "CloudDead",
                "happiness": "0",
                "hungry": "0",
                "health": "0",
                "state": state_name,
                "xp": "0",
                "sensor_value": "0",
                "all_missions_done": "false",
                "owner_name": "Test",
            }
            ui.print_status(values)
            captured = capsys.readouterr().out
            expected_key = "muerto1" if "gordito" in state_name else "muerto0"
            expected_sprite = bitmaps.EMBEDDED_CLOUD_SPRITES[expected_key]
            temeroso_sprite = bitmaps.EMBEDDED_CLOUD_SPRITES["temeroso"]
            assert expected_sprite in captured, f"Dead status for {state_name} must render {expected_key}"
            assert temeroso_sprite not in captured, f"Dead status for {state_name} must NOT render temeroso"

    def test_print_status_overfed_state(self, capsys):
        values = {
            "species_id": "0x0004 (Pwn Cloud)",
            "name": "CloudFat",
            "happiness": "1000",
            "hungry": "950",
            "health": "1000",
            "state": "temeroso",
            "xp": "0",
            "sensor_value": "0",
            "all_missions_done": "false",
            "owner_name": "Test",
        }
        ui.print_status(values)
        captured = capsys.readouterr().out
        gordito3_sprite = bitmaps.EMBEDDED_CLOUD_SPRITES["gordito3"]
        assert gordito3_sprite in captured, "Overfed status (hungry>=900) must render gordito3 sprite"

