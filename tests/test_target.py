import json

import pytest

from pwnpet_cli import target


@pytest.fixture(autouse=True)
def isolated_target_file(tmp_path, monkeypatch):
    config_dir = tmp_path / "pwnpet"
    target_file = config_dir / "last_target.json"
    monkeypatch.setattr(target, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(target, "TARGET_FILE", target_file)
    return target_file


class TestLoad:
    def test_no_file_returns_none(self):
        assert target.load() is None

    def test_loads_saved_addr_and_name(self, isolated_target_file):
        isolated_target_file.parent.mkdir(parents=True)
        isolated_target_file.write_text(
            json.dumps({"addr": "AA:BB:CC:DD:EE:FF", "name": "PwnPet_1234"})
        )
        assert target.load() == ("AA:BB:CC:DD:EE:FF", "PwnPet_1234")

    def test_loads_addr_with_missing_name(self, isolated_target_file):
        isolated_target_file.parent.mkdir(parents=True)
        isolated_target_file.write_text(json.dumps({"addr": "AA:BB:CC:DD:EE:FF"}))
        assert target.load() == ("AA:BB:CC:DD:EE:FF", None)

    def test_malformed_json_returns_none(self, isolated_target_file):
        isolated_target_file.parent.mkdir(parents=True)
        isolated_target_file.write_text("not json")
        assert target.load() is None

    def test_missing_addr_key_returns_none(self, isolated_target_file):
        isolated_target_file.parent.mkdir(parents=True)
        isolated_target_file.write_text(json.dumps({"name": "PwnPet_1234"}))
        assert target.load() is None


class TestSave:
    def test_creates_parent_dir_and_file(self, isolated_target_file):
        target.save("AA:BB:CC:DD:EE:FF", "PwnPet_1234")
        assert isolated_target_file.exists()
        data = json.loads(isolated_target_file.read_text())
        assert data == {"addr": "AA:BB:CC:DD:EE:FF", "name": "PwnPet_1234"}

    def test_default_name_is_none(self, isolated_target_file):
        target.save("AA:BB:CC:DD:EE:FF")
        data = json.loads(isolated_target_file.read_text())
        assert data == {"addr": "AA:BB:CC:DD:EE:FF", "name": None}

    def test_overwrites_existing_target(self, isolated_target_file):
        target.save("AA:BB:CC:DD:EE:FF", "first")
        target.save("11:22:33:44:55:66", "second")
        assert target.load() == ("11:22:33:44:55:66", "second")


class TestClear:
    def test_noop_when_missing(self):
        target.clear()  # must not raise

    def test_removes_existing_file(self, isolated_target_file):
        target.save("AA:BB:CC:DD:EE:FF")
        assert isolated_target_file.exists()
        target.clear()
        assert not isolated_target_file.exists()
