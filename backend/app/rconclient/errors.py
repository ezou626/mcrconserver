"""Custom exceptions for the RCON client module."""


class RCONClientMissingPassword(Exception):
    """Raised when the RCON password is missing from environment variables."""

    pass


class RCONClientNotConnected(Exception):
    """Raised when the TCP socket is None, indicating no connection."""

    pass


class RCONClientAuthenticationFailed(Exception):
    """Raised when authentication with the RCON server fails due to incorrect password."""

    pass


class RCONClientTimeout(Exception):
    """Raised when a socket operation times out."""

    pass


class RCONClientNotAuthenticated(Exception):
    """Raised when the client is not authenticated with the RCON server."""

    pass
