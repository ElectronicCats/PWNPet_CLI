"""Bleak wrapper. Thin async helpers for scan/connect/read/write/notify.

Host-tested in tests/test_transport.py with BleakScanner/BleakClient
mocked. pwnpet_cli_smoke.py remains the source of truth for behavior
against real hardware (timing, BlueZ quirks, etc. that mocks can't cover).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData

from .errors import (
    CliError,
    ConnectionFailedError,
    GattError,
    NotifyTimeoutError,
    TargetNotFoundError,
)
from . import ui

# 16-bit BLE service UUID for the umbrella service (spec §1).
PWNPET_SERVICE_UUID = "0000feed-0000-1000-8000-00805f9b34fb"
COMPANY_ID = 0xFFFF
NOTIFY_FLAG_CHAR = "0000c0ff-0000-1000-8000-00805f9b34fb"
PLAY_CHAR = "0000c003-0000-1000-8000-00805f9b34fb"
LOCAL_NAME_PREFIX = "PwnPet_"


@dataclass
class ScanHit:
    addr: str
    name: str | None
    species_id: int | None
    state: int | None
    manuf_data: (
        bytes  # re-assembled wire form: CID LE + manuf payload; b"" if not present
    )
    device: BLEDevice  # bleak handle for direct connect (avoids find_device_by_address roundtrip)


def _parse_manuf_data(adv: AdvertisementData) -> tuple[int | None, int | None, bytes]:
    """Pull (species_id, state, raw_manuf_bytes) out of adv data.

    Manuf data layout (spec frozen): CID(2) | species_id(2) | state(1) | adv_flag(3).
    Bleak gives us a {company_id: bytes} dict already stripped of the CID field.
    """
    manuf = adv.manufacturer_data.get(COMPANY_ID)
    if manuf is None:
        return (None, None, b"")
    if len(manuf) >= 3:
        species_id = int.from_bytes(manuf[0:2], "little")
        state = manuf[2]
    else:
        species_id = None
        state = None
    cid_bytes = COMPANY_ID.to_bytes(2, "little")
    return species_id, state, cid_bytes + manuf


async def scan(timeout: float = 5.0, all_devices: bool = False) -> list[ScanHit]:
    """Discover badges. Default filters to PwnPet (CID 0xFFFF or service 0xFEED
    or local name starting with 'PwnPet_'). The local-name fallback covers BLE
    stacks that report scan response packets to the callback before the main
    adv packet (e.g. some BlueZ versions on Linux)."""
    from bleak import BleakScanner  # noqa: PLC0415

    found: dict[str, ScanHit] = {}

    def cb(device: BLEDevice, adv: AdvertisementData) -> None:
        keep = all_devices
        if not keep:
            if COMPANY_ID in adv.manufacturer_data:
                keep = True
            elif PWNPET_SERVICE_UUID in (adv.service_uuids or []):
                keep = True
            elif adv.local_name and adv.local_name.startswith(LOCAL_NAME_PREFIX):
                keep = True
        if not keep:
            return
        species_id, state, manuf = _parse_manuf_data(adv)
        prev = found.get(device.address)
        # If this packet has manuf data, prefer it over a prior name-only hit.
        if prev is not None and species_id is None and prev.species_id is not None:
            return
        found[device.address] = ScanHit(
            addr=device.address,
            name=adv.local_name or device.name or (prev.name if prev else None),
            species_id=(
                species_id
                if species_id is not None
                else (prev.species_id if prev else None)
            ),
            state=state if state is not None else (prev.state if prev else None),
            manuf_data=manuf if manuf else (prev.manuf_data if prev else b""),
            device=device,
        )

    try:
        async with BleakScanner(detection_callback=cb):
            await asyncio.sleep(timeout)
    except CliError:
        raise
    except Exception as exc:
        raise ConnectionFailedError(f"BLE scan failed: {exc}") from exc
    return list(found.values())


async def resolve_name_to_device(name: str, timeout: float = 5.0) -> BLEDevice:
    """Mini-scan to map a local name to a bleak BLEDevice. Errors if 0 or >1 match.

    Filters to PwnPet badges — name collisions against unrelated BLE devices
    in a crowded event would otherwise cause spurious '>1 match' errors.

    Returns the BLEDevice (not a MAC string) so callers can pass it directly
    to Connection without a second round-trip through find_device_by_address.
    Caller can read .address if a string MAC is needed (e.g. last_target.json
    persistence).
    """
    hits = await scan(timeout=timeout, all_devices=False)
    matches = [h for h in hits if h.name == name]
    if not matches:
        raise TargetNotFoundError(f"no badge with local name {name!r} in {timeout}s")
    if len(matches) > 1:
        macs = ", ".join(h.addr for h in matches)
        raise TargetNotFoundError(f"multiple badges with name {name!r}: {macs}")
    return matches[0].device


async def _find_device(addr: str, timeout: float = 15.0) -> BLEDevice:
    """Resolve a MAC address to a bleak BLEDevice via a short scan.

    bleak's BleakClient(address) on Linux/BlueZ requires the device to have
    been seen by a recent BleakScanner; without it, .connect() raises
    'Device not found'. This helper does the required scan for one-shot
    commands like `pwnpet status` that don't run a user-facing scan first.

    Timeout is 15s — empirically some badges advertise slowly enough that
    5s misses them on cold cache (BlueZ flushed).
    """
    from bleak import BleakScanner  # noqa: PLC0415

    ui.err_console.print(f"Searching for device {addr}...")
    device = await BleakScanner.find_device_by_address(addr, timeout=timeout)
    if device is None:
        raise ConnectionFailedError(
            f"connect to {addr}: device not visible after {timeout}s scan"
        )
    # BlueZ may briefly remove the device's D-Bus object after the scanner
    # stops. A short pause lets the object tree stabilize before connect()
    # tries to use the device path (avoids UNKNOWN_OBJECT race on Linux).
    await asyncio.sleep(0.5)
    return device


class Connection:
    """Async context manager for a one-shot BLE connection."""

    def __init__(
        self,
        target: "str | BLEDevice",
        connect_timeout: float = 20.0,
        scan_timeout: float = 15.0,
    ) -> None:
        if isinstance(target, str):
            self._addr: str = target
            self._device: BLEDevice | None = None
        else:
            self._addr = target.address
            self._device = target
        self._connect_timeout = connect_timeout
        self._scan_timeout = scan_timeout
        self._client: BleakClient | None = None

    async def __aenter__(self) -> "Connection":
        from bleak import BleakClient  # noqa: PLC0415

        if self._device is None:
            try:
                self._device = await _find_device(
                    self._addr, timeout=self._scan_timeout
                )
            except CliError:
                raise
            except Exception as exc:
                raise ConnectionFailedError(f"connect to {self._addr}: {exc}") from exc

        _MAX_ATTEMPTS = 4
        last_exc: Exception = RuntimeError("unreachable")
        for attempt in range(_MAX_ATTEMPTS):
            if attempt > 0:
                # Wait for BlueZ to finish cleaning up the previous failed
                # connection, then re-scan for a fresh D-Bus device handle.
                # The handle from the previous attempt may be stale if BlueZ
                # removed the device object after the prior scan stopped.
                ui.err_console.print(
                    f"Connection lost. Retrying ({attempt}/{_MAX_ATTEMPTS - 1})..."
                )
                await asyncio.sleep(2.0)
                try:
                    self._device = await _find_device(
                        self._addr, timeout=self._scan_timeout
                    )
                except Exception:
                    pass  # keep existing device handle; attempt will likely fail too
            else:
                ui.err_console.print(f"Connecting to {self._addr}...")
            self._client = BleakClient(self._device, timeout=self._connect_timeout)
            try:
                await self._client.connect(dangerous_use_bleak_cache=False)
                ui.err_console.print("Connected.")
                return self
            except CliError:
                raise
            except Exception as exc:
                last_exc = exc
                # Explicitly disconnect to clean up any zombie BlueZ connection
                # state before the next attempt (Bleak 3.x, Linux/BlueZ).
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
        raise ConnectionFailedError(
            f"connect to {self._addr}: {last_exc}"
        ) from last_exc

    async def __aexit__(self, *_: object) -> None:
        if self._client is None:
            return
        try:
            await self._client.disconnect()
        except Exception:
            pass

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def read(self, uuid: str) -> bytes:
        if self._client is None:
            raise GattError(f"read {uuid}: not connected")
        try:
            return bytes(await self._client.read_gatt_char(uuid))
        except CliError:
            raise
        except Exception as exc:
            raise GattError(f"read {uuid}: {exc}") from exc

    async def write(self, uuid: str, payload: bytes) -> None:
        if self._client is None:
            raise GattError(f"write {uuid}: not connected")
        try:
            await self._client.write_gatt_char(uuid, payload, response=True)
        except CliError:
            raise
        except Exception as exc:
            raise GattError(f"write {uuid}: {exc}") from exc

    async def play_read_flag(self, magic: bytes) -> bytes:
        """Write magic to 0xC003, settle 100 ms, read 0xC0FF backing buffer.

        The firmware (ble_services.cpp:373-393) populates 0xC0FF synchronously
        inside the 0xC003 write handler — non-zero response for correct magic,
        zeros otherwise. bleak's AcquireNotify hits NotPermitted on this
        hardware (deferred to v0.2), so write-then-read is the stable path.

        All-zeros result → wrong magic → NotifyTimeoutError (rc=5, spec §8).
        """
        await self.write(PLAY_CHAR, magic)
        await asyncio.sleep(
            0.1
        )  # firmware compute is synchronous; settle bleak round-trip
        raw = await self.read(NOTIFY_FLAG_CHAR)
        if all(b == 0 for b in raw):
            raise NotifyTimeoutError("0xC0FF read returned zeros — wrong magic")
        return bytes(raw)
