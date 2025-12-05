"""
RCON communication client.

Intended for use within an asyncio task worker for delivering commands
and receiving results asynchronously. The philosophy is to bubble up
socket exceptions for handling reconnects/retries, and return null results
for authentication failures.

Packet format reference: https://minecraft.wiki/w/RCON#Packet_format

"""

import asyncio
import logging
import socket
import struct

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
    ) -> None:
        """
        Initializes the SocketClient with packet ID starting at 1.

        :param reader: The StreamReader for the socket
        :type reader: asyncio.StreamReader
        :param writer: The StreamWriter for the socket
        :type writer: asyncio.StreamWriter
        """
        self._reader = reader
        self._writer = writer
        self._request_id: int = 1

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
        all_bytes = bytearray()
        while len(all_bytes) < 4:
            all_bytes += await reader.read(4 - len(all_bytes))
        response_bytes = bytes(all_bytes)
        response_length: int = struct.unpack("<i", response_bytes)[0]

        # rest of response
        all_bytes = bytearray()
        while len(all_bytes) < response_length:
            all_bytes += await reader.read(response_length - len(all_bytes))
        response_bytes = bytes(all_bytes)

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
        # synchronous send and receive
        writer.write(SocketClient._format_packet(payload, packet_type, request_id))
        await writer.drain()
        response_id, response_body = await SocketClient._read_response(reader)

        if response_id == -1:
            return None

        return response_body

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
        if self.request_id == -1:
            raise
        self.request_id += 1
        return await SocketClient._send_packet(
            command,
            RCONPacketType.COMMAND_PACKET,
            self.request_id,
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

    @classmethod
    async def get_new_client(
        cls,
        password: str,
        port: int = 25575,
        timeout: int | None = None,
    ) -> "SocketClient | None":
        """
        Connects to the RCON server and authenticates, returning a client if successful

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
        """

        # only designed for localhost connections for security
        rcon_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rcon_socket.connect(("localhost", port))
        rcon_socket.settimeout(timeout)

        reader, writer = await asyncio.open_connection(sock=rcon_socket)

        auth_success = await SocketClient._send_packet(
            password, RCONPacketType.AUTH_PACKET, 0, reader, writer
        )

        if not auth_success:
            return None

        return cls(reader, writer)
