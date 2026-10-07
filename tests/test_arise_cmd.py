"""Unit tests for arise_cmd module."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from pwnpet_cli.commands import arise_cmd
from pwnpet_cli.errors import GattError, UsageError


class DummyConnection:
    def __init__(self, state_byte: int = 4):
        self.state_byte = state_byte
        self.written: list[tuple[str, bytes]] = []

    async def read(self, uuid: str) -> bytes:
        if uuid == "0000fe05-0000-1000-8000-00805f9b34fb":  # state
            return bytes([self.state_byte])
        if uuid == "0000fe04-0000-1000-8000-00805f9b34fb":  # species_id
            return bytes([0x04, 0x00])  # Cloud
        return b""

    async def write(self, uuid: str, data: bytes) -> None:
        self.written.append((uuid, data))


@pytest.mark.anyio
async def test_arise_raises_usage_error_when_creature_alive():
    conn = DummyConnection(state_byte=0)  # temeroso (alive)
    with pytest.raises(UsageError, match="command only available when the creature is dead"):
        await arise_cmd.execute(conn)


@pytest.mark.anyio
async def test_arise_aborted_when_user_does_not_type_yes():
    conn = DummyConnection(state_byte=4)  # muerto (salud)
    with patch("pwnpet_cli.ui.console.input", return_value="no"):
        result = await arise_cmd.execute(conn)
        assert result is False
        assert len(conn.written) == 0


@pytest.mark.anyio
async def test_arise_successful_resurrection():
    conn = DummyConnection(state_byte=4)  # muerto (salud)
    with patch("pwnpet_cli.ui.console.input", return_value="yes"):
        result = await arise_cmd.execute(conn, addon_connected=True, species="cloud")
        assert result is True
        assert len(conn.written) == 1
        assert conn.written[0][0] == "0000c007-0000-1000-8000-00805f9b34fb"  # factory_reset
        assert conn.written[0][1] == bytes([0x01])


@pytest.mark.anyio
async def test_arise_blocked_by_gatt_error():
    conn = DummyConnection(state_byte=5)  # muerto (gordito)
    with patch("pwnpet_cli.ui.console.input", return_value="yes"), patch.object(
        conn, "write", side_effect=GattError("Death too recent")
    ):
        result = await arise_cmd.execute(conn, addon_connected=True, species="cloud")
        assert result is False
