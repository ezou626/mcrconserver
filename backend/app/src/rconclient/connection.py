"""RCON communication client.

Intended for use within an asyncio task worker for delivering commands
and receiving results asynchronously. The philosophy is to bubble up
socket exceptions for handling reconnects/retries, and return null results
for authentication failures. Because we consider mainly long-lived connections,
we don't support the async context manager pattern here, but instead in the
wrapping resource RCONWorkerPool.

Packet format reference: https://minecraft.wiki/w/RCON#Packet_format
"""

import asyncio
import logging
import socket
import struct
from dataclasses import dataclass

from backend.app.src.rconclient.rcon_exceptions import RCONClientIncorrectPasswordError

from .types import RCONPacketType

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


@dataclass
class SocketClientConfig:
    """Configuration for the RCON SocketClient.

    :param password: The RCON password
    :param port: The RCON port (default: 25575)
    :param socket_timeout: The socket timeout in seconds (default: None)
    :param reconnect_pause: Pause duration in seconds before
        reconnecting (default: None)
    """

    password: str
    port: int = 25575
    socket_timeout: int | None = None
    reconnect_pause: int | None = None


class SocketClient:
    """Client that manages an RCON connection to a server.

    Supports single-threaded && single-coroutine access only.
    """

    # request id (4) + packet type (4) + 2 null bytes (2)
    _PACKET_METADATA_SIZE = 10

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        config: SocketClientConfig,
    ) -> None:
        """Initialize the SocketClient with packet ID starting at 1.

        :param reader: The StreamReader for the socket
        :param writer: The StreamWriter for the socket
        :param config: The SocketClientConfig instance
        """
        self._reader = reader
        self._writer = writer
        self._request_id: int = 1
        self._password = config.password
        self._port = config.port
        self._timeout = config.socket_timeout
        self._reconnect_pause = config.reconnect_pause

    @staticmethod
    def _format_packet(
        payload: str,
        packet_type: RCONPacketType,
        request_id: int,
    ) -> bytes:
        """Format a packet to be sent to the RCON server.

        :param payload: The body of the packet
        :param packet_type: The type of the packet (RCONPacketType)
        :param request_id: The request ID for the packet
        :return: The formatted packet as bytes
        """
        body_bytes = payload.encode("utf-8")

        return (
            struct.pack("<i", len(body_bytes) + SocketClient._PACKET_METADATA_SIZE)
            + struct.pack("<i", request_id)
            + struct.pack("<i", packet_type.value)
            + body_bytes
            + b"\x00\x00"
        )

    @staticmethod
    async def _read_response(reader: asyncio.StreamReader) -> tuple[int, str]:
        """Read a valid and full command response from the RCON server.

        :param reader: The StreamReader for the RCON socket
        :return: A tuple of (response_id, response_body)

        :raises TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        """
        # get the length
        response_bytes = await reader.readexactly(4)
        response_length: int = struct.unpack("<i", response_bytes)[0]

        # rest of response
        response_bytes = await reader.readexactly(response_length)
        response_id: int = struct.unpack("<i", response_bytes[0:4])[0]
        response_body = response_bytes[8:-2].decode("utf-8")

        return response_id, response_body

    @staticmethod
    async def _send_packet(
        payload: str,
        packet_type: RCONPacketType,
        request_id: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> str | None:
        """Send a packet through the given socket and reads the response.

        Handles multi-packet responses by sending a dummy command with type 200
        and collecting all packets until the "Unknown request c8" response.

        :param payload: The body of the packet
        :param packet_type: The type of the packet (RCONPacketType)
        :param request_id: The request ID for the packet local to this client
        :param reader: The StreamReader for the RCON socket
        :param writer: The StreamWriter for the RCON socket
        :return: The response from the server, or None if auth fails

        :raises TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        """
        # Send the original command
        writer.write(SocketClient._format_packet(payload, packet_type, request_id))
        await writer.drain()

        if packet_type != RCONPacketType.COMMAND_PACKET:
            response_id, response_body = await SocketClient._read_response(reader)

            if response_id == -1:
                return None

            return response_body

        dummy_request_id = request_id + 1000
        body_bytes = b""
        dummy_packet = (
            struct.pack("<i", len(body_bytes) + SocketClient._PACKET_METADATA_SIZE)
            + struct.pack("<i", dummy_request_id)
            + struct.pack("<i", RCONPacketType.DUMMY_PACKET)
            + body_bytes
            + b"\x00\x00"
        )
        writer.write(dummy_packet)
        await writer.drain()

        response_parts = []
        while True:
            response_id, response_body = await SocketClient._read_response(reader)

            if response_id == -1:
                return None

            if response_id == dummy_request_id:
                break

            if response_id == request_id:
                response_parts.append(response_body)

        return "".join(response_parts)

    async def send_command(self, command: str) -> str | None:
        """Send a command to the RCON server and returns the response.

        :param command: The RCON command to send
        :type command: str
        :return: The response from the RCON server, or None if auth fails
        :rtype: str | None

        :raises TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        """
        if self._request_id == -1:
            msg = "Client disconnected"
            raise ConnectionError(msg)
        self._request_id += 1
        return await SocketClient._send_packet(
            command,
            RCONPacketType.COMMAND_PACKET,
            self._request_id,
            self._reader,
            self._writer,
        )

    async def disconnect(self) -> None:
        """Disconnects from the RCON server and closes the socket (best effort)."""
        try:
            self._writer.close()
            await self._writer.wait_closed()
            self._reader.feed_eof()
        except Exception:
            # Ignore errors when closing the socket
            LOGGER.exception("Error while closing RCON socket")
        self._request_id = -1

    async def reconnect(self) -> str | None:
        """Destroy old connection and reconnect.

        :raises TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        """
        await self.disconnect()

        if self._reconnect_pause:
            await asyncio.sleep(self._reconnect_pause)

        rcon_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rcon_socket.connect(("localhost", self._port))
        rcon_socket.settimeout(self._timeout)

        reader, writer = await asyncio.open_connection(sock=rcon_socket)

        auth_success = await SocketClient._send_packet(
            self._password,
            RCONPacketType.AUTH_PACKET,
            0,
            reader,
            writer,
        )

        if auth_success is not None:
            self._reader, self._writer = reader, writer
            self._request_id = 1

        return auth_success

    @classmethod
    async def get_new_client(
        cls,
        config: SocketClientConfig,
    ) -> SocketClient:
        """Connect to the RCON server and get a new client.

        This should be the go-to way to create an instance of this class to identify
        password errors early on.

        :param password: The RCON password
        :type password: str
        :param port: The RCON port (default: 25575)
        :type port: int
        :param timeout: The socket timeout in seconds (default: None)
        :type timeout: int | None
        :return: A SocketClient if auth is successful, None otherwise
        :rtype: SocketClient | None

        :raises TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        :raises RCONClientIncorrectPassword: if the password is incorrect
        """
        # only designed for localhost connections for security
        rcon_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rcon_socket.connect(("localhost", config.port))
        rcon_socket.settimeout(config.socket_timeout)

        reader, writer = await asyncio.open_connection(sock=rcon_socket)

        auth_success = None
        try:
            auth_success = await SocketClient._send_packet(
                config.password,
                RCONPacketType.AUTH_PACKET,
                0,
                reader,
                writer,
            )
        except (TimeoutError, ConnectionError):
            reader.feed_eof()
            writer.close()
            await writer.wait_closed()
            raise

        if auth_success is None:
            reader.feed_eof()
            writer.close()
            await writer.wait_closed()
            msg = "Incorrect RCON password"
            raise RCONClientIncorrectPasswordError(msg)

        return cls(reader, writer, config)
