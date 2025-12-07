"""Custom exceptions for the RCON client module."""


class RCONClientMissingPasswordError(Exception):
    """Raised when the RCON password is missing from environment variables."""


class RCONClientIncorrectPasswordError(Exception):
    """Raised when the RCON password is incorrect."""
