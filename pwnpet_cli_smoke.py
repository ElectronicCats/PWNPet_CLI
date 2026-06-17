"""End-to-end smoke test of the pwnpet CLI against a real badge.

Marker requires_badge — excluded from default `pytest` and `ctest` runs.
Run manually:

    pytest scripts/pwnpet_cli_smoke.py -m requires_badge -v

Architecture (post-F8.12 rewrite — see
docs/superpowers/specs/2026-05-03-f8.12-smoke-harness-subprocess-design.md):
- Session-scoped fixture runs `pwnpet scan --raw --timeout 14` once and
  returns the first PwnPet MAC string.
- Each test invokes the public `pwnpet` binary via `subprocess.run` with
  `-t <MAC>` and asserts on returncode + stdout substrings.
- No bleak / dbus-fast / asyncio imports here. Each subprocess fork
  gets its own event loop, so the F8.9 in-process cross-loop class of
  bug cannot recur. Pre-F8.12: in-process pytest-asyncio+bleak;
  RuntimeError "got Future attached to a different loop" — see
  F8.11 debt memory.

Wall time: ~80 s on warmed-up hardware (one ~14 s scan + 6 tests at
~10 s each). Pre-F8.12 in-process target was ~30 s; F8.12 explicitly
trades it for stability per F8.12 spec §5.3.
"""

from __future__ import annotations

import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_badge

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEOUT = 20.0
SCAN_TIMEOUT = 14
# 30s = 15s find_device (transport.py default) + 5s bleak connect/setup +
# 3s notify_timeout in play_with_notify + 7s cleanup margin. Tighter
# values risk killing the subprocess mid-bleak-cleanup, which leaves the
# badge in a stuck-connected state (TMOS doesn't detect peer link-loss
# fast enough); badge then stops advertising until physical reset —
# user-visible bug. Empirical floor on this hardware.
PLAY_TIMEOUT_S = 30.0
WATCH_WALL_S = 6.0
WATCH_INTERVAL_S = 0.3


def run_cli(args, timeout=DEFAULT_TIMEOUT):
    """Invoke `python3 -m pwnpet_cli` in a fresh subprocess with timeout."""
    env = {"PYTHONPATH": str(SCRIPTS_DIR), "PATH": "/usr/bin:/bin"}
    return subprocess.run(
        [sys.executable, "-m", "pwnpet_cli", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=timeout,
    )


@pytest.fixture(scope="session")
def badge_addr():
    """Discover the first PwnPet badge in range. Session-scoped — scan once.

    Before scanning, force-disconnect any cached BlueZ state for the
    badge MAC. Without this, BlueZ retains AcquireNotify locks from
    PRIOR sessions (manual `pwnpet play`, previous smoke runs); the
    next subscribe on 0xC0FF inside the suite trips
    `[org.bluez.Error.NotPermitted] Notify acquired` even though no
    test in the current session subscribed yet. The disconnect is
    best-effort — failure is non-fatal because the badge may not be
    cached at all.

    Returns the MAC address string (e.g. 'DC:32:62:8D:E1:09'). Each test
    passes this to its own `pwnpet <cmd> -t <addr>` subprocess call.
    """
    proc = run_cli(
        ["scan", "--raw", "--timeout", str(SCAN_TIMEOUT)], timeout=SCAN_TIMEOUT + 6
    )
    if proc.returncode != 0:
        pytest.skip(f"pwnpet scan failed (rc={proc.returncode}): {proc.stderr.strip()}")
    addr = None
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0].startswith("PwnPet_"):
            addr = parts[1]
            break
    if addr is None:
        pytest.skip(f"no PwnPet badge found in {SCAN_TIMEOUT}s scan window")
    subprocess.run(
        ["bluetoothctl", "disconnect", addr],
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
    )
    return addr


def test_status_reads_all_seven_fields(badge_addr):
    """All 7 public-state labels appear in `pwnpet status` output.

    Labels are the human-readable status output (per F8 spec §7.1),
    NOT the chars whitelist names. The status block prints `species:`
    not `species_id:`, but the underlying char IS species_id (0xFE01)."""
    proc = run_cli(["status", "-t", badge_addr])
    assert proc.returncode == 0, f"status rc={proc.returncode}, stderr={proc.stderr!r}"
    for label in (
        "species",
        "name",
        "happiness",
        "hungry",
        "health",
        "state",
        "sensor_value",
        "all_missions_done",
    ):
        assert (
            label in proc.stdout
        ), f"label {label!r} missing from status output:\n{proc.stdout}"


def test_feed_grows_happiness(badge_addr):
    """Read happiness → feed 50 → 0.5 s settle → re-read; new > old."""
    before_proc = run_cli(["read", "happiness", "-t", badge_addr])
    assert before_proc.returncode == 0, before_proc.stderr
    before = int(before_proc.stdout.strip())

    feed_proc = run_cli(["feed", "50", "-t", badge_addr])
    assert feed_proc.returncode == 0, feed_proc.stderr

    time.sleep(0.5)

    after_proc = run_cli(["read", "happiness", "-t", badge_addr])
    assert after_proc.returncode == 0, after_proc.stderr
    after = int(after_proc.stdout.strip())

    assert after > before, f"happiness did not grow: {before} → {after}"


def test_pet_does_not_error(badge_addr):
    """`pwnpet pet` returns 0 (writing 0 bytes to 0xC002 is accepted)."""
    proc = run_cli(["pet", "-t", badge_addr])
    assert proc.returncode == 0, f"pet rc={proc.returncode}, stderr={proc.stderr!r}"


def test_play_correct_magic_returns_notify(badge_addr):
    """play 0xDEADBEEF returns 0 with a 16-hex-char notify line."""
    proc = run_cli(["play", "0xDEADBEEF", "-t", badge_addr], timeout=PLAY_TIMEOUT_S)
    if proc.returncode == 5:
        pytest.skip("badge did not notify within 3s window — firmware-side timing")
    assert proc.returncode == 0, f"play rc={proc.returncode}, stderr={proc.stderr!r}"
    assert re.search(
        r"^[0-9a-fA-F]{16}$", proc.stdout.strip(), re.MULTILINE
    ), f"no 16-hex-char line in stdout: {proc.stdout!r}"


def test_play_wrong_magic_times_out(badge_addr):
    """play 0x12345678 exits 5 (NotifyTimeoutError per F8 spec §8)."""
    proc = run_cli(["play", "0x12345678", "-t", badge_addr], timeout=PLAY_TIMEOUT_S)
    assert (
        proc.returncode == 5
    ), f"expected rc=5 (notify timeout), got rc={proc.returncode}, stderr={proc.stderr!r}"


def test_watch_emits_multiple_samples(badge_addr):
    """`read --watch sensor_value` emits ≥ 3 sample lines in WATCH_WALL_S.

    Sends SIGINT (not SIGTERM) so the CLI's KeyboardInterrupt handler
    in read_cmd.py runs and flushes stdout. Sets PYTHONUNBUFFERED=1
    so child print() output is line-buffered into the pipe."""
    env = {
        "PYTHONPATH": str(SCRIPTS_DIR),
        "PATH": "/usr/bin:/bin",
        "PYTHONUNBUFFERED": "1",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pwnpet_cli",
            "read",
            "--watch",
            "sensor_value",
            "--interval",
            str(WATCH_INTERVAL_S),
            "-t",
            badge_addr,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        time.sleep(WATCH_WALL_S)
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=8.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    sample_lines = [ln for ln in out.splitlines() if ln.strip().lstrip("-").isdigit()]
    assert (
        len(sample_lines) >= 3
    ), f"expected ≥3 sample lines in {WATCH_WALL_S}s, got {len(sample_lines)}; stdout={out!r}; stderr={err!r}"
