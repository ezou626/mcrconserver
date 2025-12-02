"""
Dead-simple RCON packet creation, parsing, and socket management.

Single-threaded && single-coroutine access only. Intended for use
within an asyncio worker for sequencing and delivering commands/results.

All functions are synchronous/blocking. Run in a separate thread
executor for better interactivity.

Usage:
password = ...
timeout = ...
connect(password=password, timeout=timeout)
send_command()
disconnect()
"""

import logging
import socket
import struct

from .errors import (
    RCONClientAuthenticationFailed,
    RCONClientNotAuthenticated,
    RCONClientNotConnected,
    RCONClientTimeout,
)
from .types import RCONPacketType

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

PACKET_METADATA_SIZE = 10

rcon_socket = None
authenticated = False
request_id = 1


def _format_packet(payload: str, packet_type: RCONPacketType) -> bytes:
    """
    Formats a packet to be sent to the RCON server following https://minecraft.wiki/w/RCON#Packet_format

    Args:
        payload: The body of the packet to send.
        packet_type: The type of the packet to send (RCONPacketType).

    Returns:
        The formatted packet as bytes.
    """
    body_bytes = payload.encode("utf-8")

    packet = (
        struct.pack("<i", len(body_bytes) + PACKET_METADATA_SIZE)
        + struct.pack("<i", request_id)
        + struct.pack("<i", packet_type.value)
        + body_bytes
        + b"\x00\x00"
    )

    return packet


def _read_response() -> tuple[int, int, str]:
    """Reads a response packet from the RCON server.

    Returns:
        A tuple of (response_id, response_type, response_body).

    Raises:
        RCONClientNotConnected: if the client is not connected.
        RCONClientTimeout: if the socket times out.
    """
    if rcon_socket is None:
        raise RCONClientNotConnected("Not connected")

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

    response_id: int = struct.unpack("<i", response_bytes[0:4])[0]
    response_type: int = struct.unpack("<i", response_bytes[4:8])[0]
    response_body: str = response_bytes[8:-2].decode("utf-8")

    return response_id, response_type, response_body


def _send_packet(payload: str, packet_type: RCONPacketType) -> str:
    """
    Synchronously sends a packet to the RCON server and returns the response body as a string.

    Args:
        payload: The body of the packet to send.
        packet_type: The type of the packet to send (RCONPacketType).

    Returns:
        The body of the response packet as a string.

    Raises:
        RCONClientNotConnected: if the socket does not exist.
        RCONClientNotAuthenticated: if the client is not authenticated and the packet type is not AUTH_PACKET.
        RCONClientTimeout: if the socket times out.
        RCONClientAuthenticationFailed: if authentication fails.
    """
    global rcon_socket
    if rcon_socket is None:
        raise RCONClientNotConnected("Not connected")

    if not authenticated and packet_type != RCONPacketType.AUTH_PACKET:
        raise RCONClientNotAuthenticated("Not authenticated")

    global request_id

    LOGGER.debug("Request ID: %d", request_id)
    LOGGER.debug("Packet type: %s", packet_type.name)
    if packet_type == RCONPacketType.COMMAND_PACKET:
        LOGGER.debug("Payload: %s", payload)

    request_id += 1

    # synchronous send and receive
    rcon_socket.sendall(_format_packet(payload, packet_type))
    response_id, response_type, response_body = _read_response()

    if response_id == -1:
        raise RCONClientAuthenticationFailed("Authentication failed")

    LOGGER.debug(
        "Response: ID=%d, type=%d, body=%s", response_id, response_type, response_body
    )

    return response_body


def connect(
    password: str,
    port: int = 25575,
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
        ConnectionRefusedError: if the connection is refused.
        RCONClientTimeout: if the connection times out.
        RCONClientAuthenticationFailed: if authentication fails.
        OSError: if an OS error occurs during connection.

    Note:
        Should never raise RCONClientNotConnected since it establishes the socket.
    """
    global rcon_socket
    if rcon_socket is not None:
        return

    rcon_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # only designed for localhost connections currently
        rcon_socket.connect(("localhost", port))
        rcon_socket.settimeout(timeout)
    except ConnectionRefusedError:
        rcon_socket = None
        raise
    except TimeoutError as e:
        rcon_socket = None
        LOGGER.error("Connection to RCON server at %s:%d timed out", "localhost", port)
        raise RCONClientTimeout("Connection timed out") from e
    except OSError as e:
        rcon_socket = None
        LOGGER.error(
            "OS error when connecting to RCON server at %s:%d: %s", "localhost", port, e
        )
        raise

    _send_packet(password, RCONPacketType.AUTH_PACKET)
    global authenticated
    authenticated = True
    LOGGER.debug("RCON client authenticated")


def send_command(command: str) -> str:
    """
    Sends a command packet to the RCON server and returns the response body as a string.

    Args:
        command: The command to send to the RCON server.

    Returns:
        The body of the response packet as a string.

    Raises:
        RCONClientNotConnected: if the client is not connected.
        RCONClientNotAuthenticated: if the client is not authenticated.
        RCONClientTimeout: if the socket times out.
    """
    return _send_packet(command, RCONPacketType.COMMAND_PACKET)


def disconnect() -> None:
    """Disconnects from the RCON server and closes the socket (best effort)."""
    global rcon_socket, authenticated, request_id

    if rcon_socket is not None:
        try:
            rcon_socket.close()
        except Exception:
            pass  # Ignore errors when closing the socket

    rcon_socket = None
    authenticated = False
    request_id = 1

    LOGGER.debug("RCON client disconnected")
