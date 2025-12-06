"""
RCON communication client.

Intended for use within an asyncio task worker for delivering commands
and receiving results asynchronously. The philosophy is to bubble up
socket exceptions for handling reconnects/retries, and return null results
for authentication failures. Because we consider mainly long-lived connections,
we don't support the async context manager pattern here, but instead in the
wrapping resource Worker.

Packet format reference: https://minecraft.wiki/w/RCON#Packet_format
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct

from .rcon_exceptions import RCONClientIncorrectPassword

from .types import RCONPacketType

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

# request id (4) + packet type (4) + 2 null bytes (2)
_PACKET_METADATA_SIZE = 10


class SocketClient:
    """
    Client that manages an RCON connection to a server.

    Supports single-threaded && single-coroutine access only.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        password: str,
        port: int,
        timeout: int | None,
        reconnect_pause: int | None,
    ) -> None:
        """
        Initializes the SocketClient with packet ID starting at 1.

        :param reader: The StreamReader for the socket
        :type reader: asyncio.StreamReader
        :param writer: The StreamWriter for the socket
        :type writer: asyncio.StreamWriter
        :param password: The RCON password for reconnect attempts
        :type password: str
        :param port: The RCON port for reconnect attempts
        :type port: int
        :param timeout: The timeout for the socket connection
        :type timeout: int | None
        """
        self._reader = reader
        self._writer = writer
        self._request_id: int = 1
        self._password = password
        self._port = port
        self._timeout = timeout
        self._reconnect_pause = reconnect_pause

    @staticmethod
    def _format_packet(
        payload: str, packet_type: RCONPacketType, request_id: int
    ) -> bytes:
        """
        Formats a packet to be sent to the RCON server

        :param payload: The body of the packet
        :type payload: str
        :param packet_type: The type of the packet (RCONPacketType)
        :type packet_type: RCONPacketType
        :param request_id: The request ID for the packet
        :type request_id: int
        :return: The formatted packet as bytes
        :rtype: bytes
        """
        body_bytes = payload.encode("utf-8")

        packet_bytes = (
            struct.pack("<i", len(body_bytes) + _PACKET_METADATA_SIZE)
            + struct.pack("<i", request_id)
            + struct.pack("<i", packet_type.value)
            + body_bytes
            + b"\x00\x00"
        )

        return packet_bytes

    @staticmethod
    async def _read_response(reader: asyncio.StreamReader) -> tuple[int, str]:
        """
        Reads a response packet from the RCON server.

        :param reader: The StreamReader for the RCON socket
        :type reader: asyncio.StreamReader
        :return: A tuple of (response_id, response_body)
        :rtype: tuple[int, str]

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
        """
        Sends a packet through the given socket and reads the response.

        Handles multi-packet responses by sending a dummy command with type 200
        and collecting all packets until the "Unknown request c8" response.

        :param payload: The body of the packet
        :type payload: str
        :param packet_type: The type of the packet (RCONPacketType)
        :type packet_type: RCONPacketType
        :param request_id: The request ID for the packet local to this client
        :type request_id: int
        :param reader: The StreamReader for the RCON socket
        :type reader: asyncio.StreamReader
        :param writer: The StreamWriter for the RCON socket
        :type writer: asyncio.StreamWriter
        :return: The response from the server, or None if auth fails
        :rtype: str | None

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
            struct.pack("<i", len(body_bytes) + _PACKET_METADATA_SIZE)
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
        """
        Sends a command to the RCON server and returns the response.

        :param command: The RCON command to send
        :type command: str
        :return: The response from the RCON server, or None if auth fails
        :rtype: str | None

        :raises TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        """
        if self._request_id == -1:
            raise ConnectionError("Client is disconnected")
        self._request_id += 1
        return await SocketClient._send_packet(
            command,
            RCONPacketType.COMMAND_PACKET,
            self._request_id,
            self._reader,
            self._writer,
        )

    async def disconnect(self) -> None:
        """
        Disconnects from the RCON server and closes the socket (best effort).
        """
        try:
            self._writer.close()
            await self._writer.wait_closed()
            self._reader.feed_eof()
        except Exception:
            pass  # Ignore errors when closing the socket
        self._request_id = -1

    async def reconnect(self) -> str | None:
        """
        Destroy old connection and reconnect

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
            self._password, RCONPacketType.AUTH_PACKET, 0, reader, writer
        )

        if auth_success is not None:
            self._reader, self._writer = reader, writer
            self._request_id = 1

        return auth_success

    @classmethod
    async def get_new_client(
        cls,
        password: str,
        port: int = 25575,
        timeout: int | None = None,
        reconnect_pause: int | None = None,
    ) -> SocketClient:
        """
        Connects to the RCON server and authenticates, returning a client if successful

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
        rcon_socket.connect(("localhost", port))
        rcon_socket.settimeout(timeout)

        reader, writer = await asyncio.open_connection(sock=rcon_socket)

        auth_success = None
        try:
            auth_success = await SocketClient._send_packet(
                password, RCONPacketType.AUTH_PACKET, 0, reader, writer
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
            raise RCONClientIncorrectPassword("Incorrect RCON password")

        return cls(reader, writer, password, port, timeout, reconnect_pause)
