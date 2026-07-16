import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pwnpet_cli import chars
from pwnpet_cli.commands import owner_cmd
from pwnpet_cli.errors import UsageError


def run(coro):
    return asyncio.run(coro)


def _fake_conn(read_value: bytes = b""):
    conn = MagicMock()
    conn.read = AsyncMock(return_value=read_value)
    conn.write = AsyncMock()
    return conn


class TestOwnerLengthValidation:
    def test_name_over_20_bytes_raises(self):
        # 21 ASCII bytes.
        conn = _fake_conn()
        with pytest.raises(UsageError):
            run(owner_cmd.execute(conn, "a" * 21))
        conn.write.assert_not_called()

    def test_accented_name_over_20_bytes_raises(self):
        # "María José Rodríguez" — 20 chars but 23 UTF-8 bytes (3 accents).
        name = "Mar\xeda Jos\xe9 Rodr\xedguez"
        assert len(name.encode("utf-8")) == 23
        conn = _fake_conn()
        with pytest.raises(UsageError):
            run(owner_cmd.execute(conn, name))
        conn.write.assert_not_called()

    def test_20_byte_name_is_accepted(self):
        conn = _fake_conn(read_value=b"12345678901234567890")
        run(owner_cmd.execute(conn, "12345678901234567890"))
        conn.write.assert_awaited_once()
        uuid, payload = conn.write.await_args.args
        assert uuid == chars.NAME_TO_UUID["set_owner"]
        assert payload == b"12345678901234567890"


class TestOwnerReadWrite:
    def test_read_mode_reads_owner_name(self):
        conn = _fake_conn(read_value=b"Ada\x00\x00")
        run(owner_cmd.execute(conn, None))
        conn.write.assert_not_called()
        conn.read.assert_awaited_with(chars.NAME_TO_UUID["owner_name"])

    def test_write_encodes_utf8(self):
        conn = _fake_conn(read_value="Jos\xe9".encode("utf-8"))
        run(owner_cmd.execute(conn, "Jos\xe9"))
        uuid, payload = conn.write.await_args.args
        assert uuid == chars.NAME_TO_UUID["set_owner"]
        assert payload == "Jos\xe9".encode("utf-8")
