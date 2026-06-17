"""Bleak-mocked tests for transport.py.

Per spec architecture gamma, transport.py was originally exempt from
host testing (verification via pwnpet_cli_smoke.py against real hardware).
These tests deliberately revisit that decision and mock bleak's
BleakScanner/BleakClient so the wrapper logic gets host-level coverage
too; the smoke script remains the source of truth for real-hardware
behavior.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pwnpet_cli import transport
from pwnpet_cli.errors import (
    ConnectionFailedError,
    GattError,
    NotifyTimeoutError,
    TargetNotFoundError,
)


def run(coro):
    return asyncio.run(coro)


def make_adv(local_name=None, manufacturer_data=None, service_uuids=None):
    from bleak.backends.scanner import AdvertisementData

    return AdvertisementData(
        local_name=local_name,
        manufacturer_data=manufacturer_data or {},
        service_data={},
        service_uuids=service_uuids or [],
        tx_power=None,
        rssi=-50,
        platform_data=(),
    )


def make_device(addr="AA:BB:CC:DD:EE:FF", name=None):
    from bleak.backends.device import BLEDevice

    return BLEDevice(addr, name, None)


class FakeScanner:
    """Stand-in for BleakScanner: fires preset (device, adv) pairs on enter."""

    def __init__(self, detection_callback=None, **kwargs):
        self._cb = detection_callback

    async def __aenter__(self):
        for device, adv in FakeScanner.packets:
            self._cb(device, adv)
        return self

    async def __aexit__(self, *exc):
        return None


class TestParseManufData:
    def test_no_company_id_returns_empty(self):
        adv = make_adv(manufacturer_data={})
        assert transport._parse_manuf_data(adv) == (None, None, b"")

    def test_short_payload_keeps_species_state_none(self):
        adv = make_adv(manufacturer_data={transport.COMPANY_ID: b"\x01"})
        species, state, manuf = transport._parse_manuf_data(adv)
        assert species is None
        assert state is None
        assert manuf == transport.COMPANY_ID.to_bytes(2, "little") + b"\x01"

    def test_full_payload_decodes_species_and_state(self):
        payload = (7).to_bytes(2, "little") + bytes([3]) + b"\x00\x00\x00"
        adv = make_adv(manufacturer_data={transport.COMPANY_ID: payload})
        species, state, manuf = transport._parse_manuf_data(adv)
        assert species == 7
        assert state == 3
        assert manuf == transport.COMPANY_ID.to_bytes(2, "little") + payload


class TestScan:
    def _run_scan(self, packets, **kwargs):
        FakeScanner.packets = packets
        with (
            patch("bleak.BleakScanner", FakeScanner),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            return run(transport.scan(**kwargs))

    def test_no_devices_returns_empty_list(self):
        assert self._run_scan([]) == []

    def test_filters_to_pwnpet_by_manufacturer_id(self):
        device = make_device()
        payload = (1).to_bytes(2, "little") + bytes([0]) + b"\x00\x00\x00"
        adv = make_adv(manufacturer_data={transport.COMPANY_ID: payload})
        other_device = make_device(addr="11:22:33:44:55:66")
        other_adv = make_adv(manufacturer_data={0x1234: b"\x00"})

        hits = self._run_scan([(device, adv), (other_device, other_adv)])
        assert len(hits) == 1
        assert hits[0].addr == device.address
        assert hits[0].species_id == 1

    def test_filters_to_pwnpet_by_service_uuid(self):
        device = make_device()
        adv = make_adv(service_uuids=[transport.PWNPET_SERVICE_UUID])
        hits = self._run_scan([(device, adv)])
        assert len(hits) == 1
        assert hits[0].addr == device.address

    def test_filters_to_pwnpet_by_local_name_prefix(self):
        device = make_device(name="PwnPet_42")
        adv = make_adv(local_name="PwnPet_42")
        hits = self._run_scan([(device, adv)])
        assert len(hits) == 1
        assert hits[0].name == "PwnPet_42"

    def test_unrelated_device_is_dropped_without_all_devices(self):
        device = make_device()
        adv = make_adv(local_name="SomeOtherThing")
        assert self._run_scan([(device, adv)]) == []

    def test_all_devices_keeps_unrelated_hits(self):
        device = make_device()
        adv = make_adv(local_name="SomeOtherThing")
        hits = self._run_scan([(device, adv)], all_devices=True)
        assert len(hits) == 1

    def test_name_only_hit_not_overwritten_by_later_name_only_packet(self):
        device = make_device(name="PwnPet_42")
        payload = (1).to_bytes(2, "little") + bytes([2]) + b"\x00\x00\x00"
        adv_with_manuf = make_adv(
            local_name="PwnPet_42", manufacturer_data={transport.COMPANY_ID: payload}
        )
        adv_name_only = make_adv(local_name="PwnPet_42")

        hits = self._run_scan([(device, adv_with_manuf), (device, adv_name_only)])
        assert len(hits) == 1
        assert hits[0].species_id == 1
        assert hits[0].state == 2

    def test_scanner_exception_wrapped_as_connection_failed(self):
        FakeScanner.packets = []

        class BoomScanner(FakeScanner):
            async def __aenter__(self):
                raise RuntimeError("dbus exploded")

        with (
            patch("bleak.BleakScanner", BoomScanner),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            with pytest.raises(ConnectionFailedError):
                run(transport.scan())


class TestResolveNameToDevice:
    def test_single_match_returns_device(self):
        device = make_device(name="PwnPet_42")
        hit = transport.ScanHit(
            addr=device.address,
            name="PwnPet_42",
            species_id=1,
            state=0,
            manuf_data=b"",
            device=device,
        )
        with patch.object(transport, "scan", new=AsyncMock(return_value=[hit])):
            result = run(transport.resolve_name_to_device("PwnPet_42"))
        assert result is device

    def test_no_match_raises_target_not_found(self):
        with patch.object(transport, "scan", new=AsyncMock(return_value=[])):
            with pytest.raises(TargetNotFoundError):
                run(transport.resolve_name_to_device("PwnPet_42"))

    def test_multiple_matches_raises_target_not_found(self):
        hits = [
            transport.ScanHit(
                addr=f"AA:BB:CC:DD:EE:0{i}",
                name="PwnPet_42",
                species_id=1,
                state=0,
                manuf_data=b"",
                device=make_device(addr=f"AA:BB:CC:DD:EE:0{i}", name="PwnPet_42"),
            )
            for i in range(2)
        ]
        with patch.object(transport, "scan", new=AsyncMock(return_value=hits)):
            with pytest.raises(TargetNotFoundError):
                run(transport.resolve_name_to_device("PwnPet_42"))


class TestFindDevice:
    def test_returns_device_when_found(self):
        device = make_device()
        with (
            patch(
                "bleak.BleakScanner.find_device_by_address",
                new=AsyncMock(return_value=device),
            ),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = run(transport._find_device(device.address))
        assert result is device

    def test_raises_connection_failed_when_not_found(self):
        with (
            patch(
                "bleak.BleakScanner.find_device_by_address",
                new=AsyncMock(return_value=None),
            ),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            with pytest.raises(ConnectionFailedError):
                run(transport._find_device("AA:BB:CC:DD:EE:FF"))


def make_fake_client(connect_side_effect=None):
    client = MagicMock()
    client.connect = AsyncMock(side_effect=connect_side_effect)
    client.disconnect = AsyncMock()
    client.read_gatt_char = AsyncMock(return_value=bytearray(b"\x01\x02"))
    client.write_gatt_char = AsyncMock()
    client.is_connected = True
    return client


class TestConnection:
    def test_connects_using_provided_device_without_rescanning(self):
        device = make_device()
        client = make_fake_client()
        with patch("bleak.BleakClient", return_value=client):

            async def go():
                async with transport.Connection(device) as conn:
                    assert conn.is_connected
                    assert conn._client is client

            run(go())
        client.connect.assert_awaited_once()
        client.disconnect.assert_awaited_once()

    def test_resolves_string_address_via_find_device(self):
        device = make_device()
        client = make_fake_client()
        with (
            patch("bleak.BleakClient", return_value=client),
            patch.object(transport, "_find_device", new=AsyncMock(return_value=device)),
        ):

            async def go():
                async with transport.Connection("AA:BB:CC:DD:EE:FF") as conn:
                    assert conn._client is client

            run(go())

    def test_retries_then_succeeds(self):
        device = make_device()
        flaky_client = make_fake_client(connect_side_effect=RuntimeError("nope"))
        good_client = make_fake_client()
        with (
            patch("bleak.BleakClient", side_effect=[flaky_client, good_client]),
            patch.object(transport, "_find_device", new=AsyncMock(return_value=device)),
            patch("asyncio.sleep", new=AsyncMock()),
        ):

            async def go():
                async with transport.Connection(device) as conn:
                    assert conn._client is good_client

            run(go())
        flaky_client.connect.assert_awaited_once()
        flaky_client.disconnect.assert_awaited_once()
        good_client.connect.assert_awaited_once()

    def test_exhausts_retries_raises_connection_failed(self):
        device = make_device()
        with (
            patch(
                "bleak.BleakClient",
                return_value=make_fake_client(connect_side_effect=RuntimeError("nope")),
            ),
            patch("asyncio.sleep", new=AsyncMock()),
        ):

            async def go():
                async with transport.Connection(device):
                    pass

            with pytest.raises(ConnectionFailedError):
                run(go())

    def test_read_without_connection_raises_gatt_error(self):
        conn = transport.Connection(make_device())
        with pytest.raises(GattError):
            run(conn.read("0000c0ff-0000-1000-8000-00805f9b34fb"))

    def test_write_without_connection_raises_gatt_error(self):
        conn = transport.Connection(make_device())
        with pytest.raises(GattError):
            run(conn.write("0000c0ff-0000-1000-8000-00805f9b34fb", b"\x00"))

    def test_read_wraps_bleak_exception_as_gatt_error(self):
        device = make_device()
        client = make_fake_client()
        client.read_gatt_char = AsyncMock(side_effect=RuntimeError("disconnected"))
        with patch("bleak.BleakClient", return_value=client):

            async def go():
                async with transport.Connection(device) as conn:
                    await conn.read("0000c0ff-0000-1000-8000-00805f9b34fb")

            with pytest.raises(GattError):
                run(go())

    def test_write_wraps_bleak_exception_as_gatt_error(self):
        device = make_device()
        client = make_fake_client()
        client.write_gatt_char = AsyncMock(side_effect=RuntimeError("disconnected"))
        with patch("bleak.BleakClient", return_value=client):

            async def go():
                async with transport.Connection(device) as conn:
                    await conn.write("0000c0ff-0000-1000-8000-00805f9b34fb", b"\x00")

            with pytest.raises(GattError):
                run(go())


class TestPlayReadFlag:
    def test_nonzero_response_returned(self):
        device = make_device()
        client = make_fake_client()
        client.read_gatt_char = AsyncMock(return_value=bytearray(b"PWNPET{ok}"))
        with (
            patch("bleak.BleakClient", return_value=client),
            patch("asyncio.sleep", new=AsyncMock()),
        ):

            async def go():
                async with transport.Connection(device) as conn:
                    return await conn.play_read_flag(b"\x01\x02\x03\x04")

            result = run(go())
        assert result == b"PWNPET{ok}"
        client.write_gatt_char.assert_awaited_once_with(
            transport.PLAY_CHAR, b"\x01\x02\x03\x04", response=True
        )

    def test_all_zero_response_raises_notify_timeout(self):
        device = make_device()
        client = make_fake_client()
        client.read_gatt_char = AsyncMock(return_value=bytearray(b"\x00\x00\x00\x00"))
        with (
            patch("bleak.BleakClient", return_value=client),
            patch("asyncio.sleep", new=AsyncMock()),
        ):

            async def go():
                async with transport.Connection(device) as conn:
                    await conn.play_read_flag(b"\x00\x00\x00\x00")

            with pytest.raises(NotifyTimeoutError):
                run(go())
