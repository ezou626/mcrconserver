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
import struct
from dataclasses import dataclass, field
from typing import ClassVar

from app.src.rconclient.rcon_exceptions import RCONClientIncorrectPasswordError

from .command import RCONPacketType

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
    :param retry_attempts: Number of additional retry attempts after initial try
        (default: INFINITE for unlimited retries)
    """

    INFINITE: ClassVar[int] = -1

    password: str
    port: int = 25575
    socket_timeout: int | None = None
    reconnect_pause: int | None = None
    retry_attempts: int = field(default=INFINITE)


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
        self._retry_attempts = config.retry_attempts

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
    async def _send_auth(
        password: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        socket_timeout: int | None = None,
    ) -> str | None:
        """Send authentication packet and read response (internal use only).

        :param password: The RCON password
        :param reader: The StreamReader for the RCON socket
        :param writer: The StreamWriter for the RCON socket
        :param socket_timeout: The socket timeout in seconds
        :return: The response from the server, or None if auth fails

        :raises asyncio.TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        """
        # Send the auth packet
        writer.write(
            SocketClient._format_packet(password, RCONPacketType.AUTH_PACKET, 0),
        )
        await asyncio.wait_for(writer.drain(), timeout=socket_timeout)

        # Read the single auth response
        response_id, response_body = await asyncio.wait_for(
            SocketClient._read_response(reader),
            timeout=socket_timeout,
        )

        if response_id == -1:
            return None

        return response_body

    @staticmethod
    async def _try_connection(
        port: int,
        socket_timeout: int | None,
        num_retries: int,
        reconnect_pause: int | None = None,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Try connection establishment with retry logic.

        :param port: The RCON port to connect to
        :param socket_timeout: The socket timeout in seconds
        :param num_retries: Number of additional retries after initial attempt
                            (use SocketClientConfig.INFINITE for unlimited)
        :param reconnect_pause: Optional pause between attempts
        :return: Connected reader and writer streams
        :raises ConnectionError: If all attempts fail (only for finite retries)
        """
        attempt = 0
        last_exception = None

        while True:
            try:
                if attempt > 0 and reconnect_pause:
                    await asyncio.sleep(reconnect_pause)

                return await asyncio.wait_for(
                    asyncio.open_connection("localhost", port),
                    timeout=socket_timeout,
                )
            except (TimeoutError, ConnectionError) as e:
                last_exception = e
                attempt += 1

                # Check if we should stop retrying
                if num_retries != SocketClientConfig.INFINITE and attempt > num_retries:
                    break

        msg = f"Failed to connect after {attempt} attempts"
        raise ConnectionError(msg) from last_exception

    async def send_command(self, command: str) -> str | None:
        """Send a command to the RCON server and returns the response.

        Handles multi-packet responses by sending a dummy command with type 200
        and collecting all packets until the "Unknown request c8" response.

        :param command: The RCON command to send
        :type command: str
        :return: The response from the RCON server, or None if auth fails
        :rtype: str | None

        :raises asyncio.TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        """
        if self._request_id == -1:
            msg = "Client disconnected"
            raise ConnectionError(msg)

        self._request_id += 1
        request_id = self._request_id

        # Send the original command
        self._writer.write(
            SocketClient._format_packet(
                command,
                RCONPacketType.COMMAND_PACKET,
                request_id,
            ),
        )
        await asyncio.wait_for(self._writer.drain(), timeout=self._timeout)

        # Send dummy packet to handle multi-packet responses
        dummy_request_id = request_id + 1000
        body_bytes = b""
        dummy_packet = (
            struct.pack("<i", len(body_bytes) + SocketClient._PACKET_METADATA_SIZE)
            + struct.pack("<i", dummy_request_id)
            + struct.pack("<i", RCONPacketType.DUMMY_PACKET)
            + body_bytes
            + b"\x00\x00"
        )
        self._writer.write(dummy_packet)
        await asyncio.wait_for(self._writer.drain(), timeout=self._timeout)

        # Collect all response parts
        response_parts = []
        while True:
            response_id, response_body = await asyncio.wait_for(
                SocketClient._read_response(self._reader),
                timeout=self._timeout,
            )

            if response_id == -1:
                return None

            if response_id == dummy_request_id:
                break

            if response_id == request_id:
                response_parts.append(response_body)

        return "".join(response_parts)

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
        """Destroy old connection and reconnect with retry logic.

        :raises asyncio.TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        """
        await self.disconnect()

        reader, writer = await SocketClient._try_connection(
            self._port,
            self._timeout,
            self._retry_attempts,
            self._reconnect_pause,
        )

        auth_success = await SocketClient._send_auth(
            self._password,
            reader,
            writer,
            self._timeout,
        )

        if auth_success is not None:
            self._reader, self._writer = reader, writer
            self._request_id = 1
        else:
            # Clean up on auth failure
            reader.feed_eof()
            writer.close()
            await writer.wait_closed()

        return auth_success

    @classmethod
    async def get_new_client(
        cls,
        config: SocketClientConfig,
    ) -> SocketClient:
        """Connect to the RCON server and get a new client.

        This should be the go-to way to create an instance of this class to identify
        password errors early on.

        :param config: The SocketClientConfig with connection parameters
        :return: A SocketClient if auth is successful
        :raises asyncio.TimeoutError: if the socket times out
        :raises ConnectionError: if the socket is no longer connected
        :raises RCONClientIncorrectPasswordError: if the password is incorrect
        """
        # Only designed for localhost connections for security
        reader, writer = await cls._try_connection(
            config.port,
            config.socket_timeout,
            config.retry_attempts,
            config.reconnect_pause,
        )

        try:
            auth_success = await cls._send_auth(
                config.password,
                reader,
                writer,
                config.socket_timeout,
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
