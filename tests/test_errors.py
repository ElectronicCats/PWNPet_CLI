import pytest

from pwnpet_cli.errors import (
    CliError,
    ConnectionFailedError,
    GattError,
    NotifyTimeoutError,
    TargetNotFoundError,
    UsageError,
)


class TestCliError:
    def test_message_and_default_exit_code(self):
        err = CliError("boom")
        assert err.message == "boom"
        assert err.exit_code == 1
        assert err.category == "error"
        assert str(err) == "boom"

    def test_is_an_exception(self):
        with pytest.raises(CliError):
            raise CliError("boom")


@pytest.mark.parametrize(
    "exc_cls,expected_code,expected_category",
    [
        (UsageError, 1, "usage"),
        (TargetNotFoundError, 2, "target not found"),
        (ConnectionFailedError, 3, "connection failed"),
        (GattError, 4, "gatt error"),
        (NotifyTimeoutError, 5, "notify timeout"),
    ],
)
class TestSubclassExitCodes:
    def test_exit_code_and_category(self, exc_cls, expected_code, expected_category):
        err = exc_cls("oops")
        assert err.exit_code == expected_code
        assert err.category == expected_category
        assert isinstance(err, CliError)
