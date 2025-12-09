"""Unit tests for the RCON client connection module.

This module contains comprehensive tests for the SocketClient class,
testing the public interface contracts including connection management,
authentication, command sending, multi-packet responses, and various
failure scenarios that can occur with Minecraft servers.
"""

import asyncio
from io import BytesIO
from unittest.mock import patch

import pytest

from app.src.rconclient.command import RCONPacketType
from app.src.rconclient.connection import SocketClient, SocketClientConfig
from app.src.rconclient.rcon_exceptions import RCONClientIncorrectPasswordError


class MockStreamReader(asyncio.StreamReader):
    """Mock StreamReader for testing RCON packet handling."""

    def __init__(self, data: bytes = b"") -> None:
        """Initialize the mock StreamReader with predefined data."""
        self._data = BytesIO(data)

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes from the mock data."""
        data = self._data.read(n)
        if len(data) < n:
            msg = "Mock connection closed"
            raise ConnectionError(msg)
        return data

    def feed_eof(self) -> None:
        """Mock feed_eof method."""


class MockStreamWriter:
    """Mock StreamWriter for testing RCON packet sending."""

    def __init__(self) -> None:
        """Initialize the mock StreamWriter."""
        self.data = BytesIO()
        self.closed = False

    def write(self, data: bytes) -> None:
        """Write data to the mock buffer."""
        if not self.closed:
            self.data.write(data)

    async def drain(self) -> None:
        """Mock drain method."""

    def close(self) -> None:
        """Mark the writer as closed."""
        self.closed = True

    async def wait_closed(self) -> None:
        """Mock wait_closed method."""


@pytest.fixture
def socket_config() -> SocketClientConfig:
    """Provide a standard SocketClientConfig for testing."""
    return SocketClientConfig(
        password="test_password",  # noqa: S106
        port=25575,
        socket_timeout=10,
        reconnect_pause=5,
    )


def create_response_data(responses: list[tuple[str, RCONPacketType, int]]) -> bytes:
    """Create mock response data containing multiple packets."""
    data = b""
    for payload, packet_type, request_id in responses:
        data += SocketClient._format_packet(payload, packet_type, request_id)  # noqa: SLF001
    return data


@pytest.mark.asyncio
class TestSocketClientAuthentication:
    """Test suite for RCON client authentication behavior."""

    async def test_successful_client_creation_with_valid_credentials(
        self,
        socket_config: SocketClientConfig,
    ) -> None:
        """Test that a client can be created with valid RCON credentials."""
        auth_response = create_response_data([("", RCONPacketType.AUTH_PACKET, 0)])

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(auth_response)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(socket_config)

            assert client is not None

    async def test_client_creation_fails_with_invalid_credentials(
        self,
        socket_config: SocketClientConfig,
    ) -> None:
        """Test that client creation fails with invalid RCON credentials."""
        auth_response = create_response_data([("", RCONPacketType.AUTH_PACKET, -1)])

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(auth_response)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            with pytest.raises(RCONClientIncorrectPasswordError):
                await SocketClient.get_new_client(socket_config)


@pytest.mark.asyncio
class TestSocketClientCommandExecution:
    """Test suite for RCON client command execution functionality."""

    async def test_send_command_returns_single_packet_response(
        self,
        socket_config: SocketClientConfig,
    ) -> None:
        """Test that commands with single-packet responses are handled correctly."""
        responses = create_response_data(
            [
                ("", RCONPacketType.AUTH_PACKET, 0),
                (
                    "Player count: 5",
                    RCONPacketType.COMMAND_PACKET,
                    2,
                ),  # Command response
                (
                    "Unknown request c8",
                    RCONPacketType.COMMAND_PACKET,
                    1002,
                ),  # Dummy terminator
            ],
        )

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(responses)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(socket_config)

            result = await client.send_command("list")

            assert result == "Player count: 5"

    async def test_send_command_handles_multi_packet_response(
        self,
        socket_config: SocketClientConfig,
    ) -> None:
        """Test that commands with multi-packet responses are properly concatenated."""
        responses = create_response_data(
            [
                ("", RCONPacketType.AUTH_PACKET, 0),
                ("Part 1: ", RCONPacketType.COMMAND_PACKET, 2),
                ("Part 2: ", RCONPacketType.COMMAND_PACKET, 2),
                ("Part 3", RCONPacketType.COMMAND_PACKET, 2),
                (
                    "Unknown request c8",
                    RCONPacketType.COMMAND_PACKET,
                    1002,
                ),  # Dummy terminator
            ],
        )

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(responses)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(socket_config)

            result = await client.send_command("help")

            assert result == "Part 1: Part 2: Part 3"

    async def test_send_command_handles_empty_response(
        self,
        socket_config: SocketClientConfig,
    ) -> None:
        """Test that commands with empty responses are handled correctly."""
        responses = create_response_data(
            [
                ("", RCONPacketType.AUTH_PACKET, 0),
                ("", RCONPacketType.COMMAND_PACKET, 2),
                (
                    "Unknown request c8",
                    RCONPacketType.COMMAND_PACKET,
                    1002,
                ),  # Dummy terminator
            ],
        )

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(responses)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(socket_config)

            result = await client.send_command("some_silent_command")

            assert result == ""


@pytest.mark.asyncio
class TestSocketClientConnectionManagement:
    """Test suite for RCON client connection management functionality."""

    async def test_disconnect_closes_connection_gracefully(
        self,
        socket_config: SocketClientConfig,
    ) -> None:
        """Test that disconnect properly closes the connection."""
        auth_response = create_response_data([("", RCONPacketType.AUTH_PACKET, 0)])

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(auth_response)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(socket_config)

            await client.disconnect()

            assert writer.closed is True

    async def test_reconnect_establishes_new_connection(
        self,
        socket_config: SocketClientConfig,
    ) -> None:
        """Test that reconnect successfully establishes a new authed connection."""
        auth_response = create_response_data([("", RCONPacketType.AUTH_PACKET, 0)])

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader1 = MockStreamReader(auth_response)
            writer1 = MockStreamWriter()
            reader2 = MockStreamReader(auth_response)
            writer2 = MockStreamWriter()
            mock_open_conn.side_effect = [(reader1, writer1), (reader2, writer2)]

            client = await SocketClient.get_new_client(socket_config)

            auth_result = await client.reconnect()
            assert auth_result is not None

    async def test_reconnect_handles_authentication_failure(
        self,
        socket_config: SocketClientConfig,
    ) -> None:
        """Test that reconnect properly handles auth failure on new connection."""
        initial_auth = create_response_data([("", RCONPacketType.AUTH_PACKET, 0)])
        failed_auth = create_response_data([("", RCONPacketType.AUTH_PACKET, -1)])

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader1 = MockStreamReader(initial_auth)
            writer1 = MockStreamWriter()
            reader2 = MockStreamReader(failed_auth)
            writer2 = MockStreamWriter()
            mock_open_conn.side_effect = [(reader1, writer1), (reader2, writer2)]

            client = await SocketClient.get_new_client(socket_config)

            auth_result = await client.reconnect()

            assert auth_result is None
            assert writer2.closed is True
