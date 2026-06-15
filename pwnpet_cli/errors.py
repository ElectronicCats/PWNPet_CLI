"""CLI exception types with stable exit codes (see spec §8)."""


class CliError(Exception):
    """Base for all CLI errors. Exit code 1 unless overridden."""

    exit_code: int = 1
    category: str = "error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UsageError(CliError):
    exit_code = 1
    category = "usage"


class TargetNotFoundError(CliError):
    exit_code = 2
    category = "target not found"


class ConnectionFailedError(CliError):
    exit_code = 3
    category = "connection failed"


class GattError(CliError):
    exit_code = 4
    category = "gatt error"


class NotifyTimeoutError(CliError):
    exit_code = 5
    category = "notify timeout"
