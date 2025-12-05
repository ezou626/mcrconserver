"""Custom exceptions for the RCON client module."""


class RCONClientMissingPassword(Exception):
    """Raised when the RCON password is missing from environment variables."""

    pass


class RCONClientIncorrectPassword(Exception):
    """Raised when the RCON password is incorrect"""

    pass
