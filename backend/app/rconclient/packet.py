"""
Dead-simple RCON packet creation, parsing, and socket management.

Single-threaded, single-coroutine access only.

Lifecycle: connect() -> _send_packet()

Disconnect is implicit when the program exits.
"""

import logging
import os
import socket
import struct

from .errors import (
    RCONClientAuthenticationFailed,
    RCONClientMissingPassword,
    RCONClientNotAuthenticated,
    RCONClientNotConnected,
    RCONClientTimeout,
)
from .types import RCONPacketType

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

PACKET_METADATA_SIZE = 10

rcon_socket = None
socket_timeout: int | None = None

authenticated = False

request_id = 1


def _send_packet(payload: str, packet_type: RCONPacketType) -> str:
    """
    Synchronously sends a packet to the RCON server and returns the response body as a string.

    Args:
        payload: The body of the packet to send.
        packet_type: The type of the packet to send (RCONPacketType).

    Returns:
        The body of the response packet as a string.

    Raises:
        RCONClientNotConnected: if the client is not connected.
        RCONClientNotAuthenticated: if the client is not authenticated and the packet type is not AUTH_PACKET.
        RCONClientAuthenticationFailed: if authentication fails.
    """
    global rcon_socket
    if rcon_socket is None:
        raise RCONClientNotConnected("Not connected")

    if not authenticated and packet_type != RCONPacketType.AUTH_PACKET:
        raise RCONClientNotAuthenticated("Not authenticated")

    global request_id

    LOG.debug("Request ID: %d", request_id)
    LOG.debug("Packet type: %s", packet_type.name)
    if packet_type == RCONPacketType.COMMAND_PACKET:
        LOG.debug("Payload: %s", payload)

    body_bytes = payload.encode("utf-8")

    packet = (
        struct.pack("<i", len(body_bytes) + PACKET_METADATA_SIZE)  # length
        + struct.pack("<i", request_id)  # request_id
        + struct.pack("<i", packet_type.value)  # type
        + body_bytes  # body
        + b"\x00\x00"  # two null bytes
    )

    request_id += 1

    # synchronous send and receive
    rcon_socket.sendall(packet)

    # get the length
    all_bytes = bytearray()
    while len(all_bytes) < 4:
        try:
            all_bytes += rcon_socket.recv(4 - len(all_bytes))
        except socket.timeout:
            raise RCONClientTimeout("Connection timed out")
    response_bytes = bytes(all_bytes)
    response_length: int = struct.unpack("<i", response_bytes)[0]

    # Get the rest of the response
    all_bytes = bytearray()
    while len(all_bytes) < response_length:
        try:
            all_bytes += rcon_socket.recv(response_length - len(all_bytes))
        except socket.timeout:
            raise RCONClientTimeout("Connection timed out")
    response_bytes = bytes(all_bytes)

    response_request_id: int = struct.unpack("<i", response_bytes[0:4])[0]
    response_type: int = struct.unpack("<i", response_bytes[4:8])[0]
    response_body: str = response_bytes[8:-2].decode(
        "utf-8"
    )  # Exclude the two null bytes at the end

    if response_type == -1:
        raise RCONClientAuthenticationFailed("Authentication failed")

    LOG.debug("Response ID: %d", response_request_id)
    LOG.debug("Response type: %d", response_type)
    LOG.debug("Response body: %s", response_body)

    return response_body


def connect(
    host: str = "localhost",
    port: int = 25575,
    password: str | None = None,
    timeout: int | None = None,
) -> None:
    """
    Initializes and connects to the RCON server socket, and authenticates.

    Args:
        host: Hostname to connect to. Defaults to "localhost".
        port: Port to connect to. Defaults to 25575.
        password: Password for authentication. If None, reads from the RCON_PASSWORD environment variable.
        timeout: Optional timeout in seconds for the socket connection. Defaults to no timeout.

    Raises:
        RCONClientMissingPassword: if the password is not set.
        RCONClientAuthenticationFailed: if authentication fails.
    """
    global rcon_socket
    if rcon_socket is not None:
        return

    # tcp socket to localhost:port with 2 second timeout
    rcon_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rcon_socket.settimeout(timeout)
    rcon_socket.connect((host, port))

    # authenticate
    if password is None:
        password = os.getenv("RCON_PASSWORD")
        if password is None:
            raise RCONClientMissingPassword(
                "RCON_PASSWORD environment variable is not set"
            )

    _send_packet(password, RCONPacketType.AUTH_PACKET)
    global authenticated
    authenticated = True
    LOG.debug("RCON client authenticated")


def set_timeout(timeout: int | None) -> None:
    """
    Sets the timeout for the RCON socket.

    Args:
        timeout: Timeout in seconds. If None, no timeout is set.

    Raises:
        RCONClientNotConnected: if the client is not connected.
    """
    global rcon_socket
    if rcon_socket is None:
        raise RCONClientNotConnected("Not connected")

    rcon_socket.settimeout(timeout)


def reconnect() -> None:
    """
    Reconnects to the RCON server if the connection was lost.

    Useful for recovering from timeouts or connection loss.

    Raises:
        RCONClientMissingPassword: if the password is not set.
        RCONClientAuthenticationFailed: if authentication fails.
    """
    global rcon_socket, authenticated

    # Store current socket timeout before closing
    if rcon_socket is not None:
        try:
            rcon_socket.close()
        except Exception:
            pass  # Ignore errors when closing the socket

    rcon_socket = None
    authenticated = False

    # Reconnect with the same timeout
    connect(timeout=socket_timeout)

    LOG.debug("RCON client reconnected successfully")

    global request_id
    request_id = 1


def send_command(command: str) -> str:
    """
    Sends a command packet to the RCON server and returns the response body as a string.

    Args:
        command: The command to send to the RCON server.

    Returns:
        The body of the response packet as a string.
    """
    return _send_packet(command, RCONPacketType.COMMAND_PACKET)
