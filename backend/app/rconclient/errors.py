class RCONClientMissingPassword(Exception):
    pass  # Password not in OS environment variables


class RCONClientNotConnected(Exception):
    pass  # TCP socket is None


class RCONClientAuthenticationFailed(Exception):
    pass  # Authentication with RCON server failed/incorrect password


class RCONClientTimeout(Exception):
    pass  # Socket operation timed out


class RCONClientNotAuthenticated(Exception):
    pass  # Client is not authenticated with the RCON server
