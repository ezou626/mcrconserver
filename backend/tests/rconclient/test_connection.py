"""
Unit tests for the RCON client connection module.

This module contains comprehensive tests for the SocketClient class,
including connection management, authentication, command sending, multi-packet responses,
and various failure scenarios that can occur with Minecraft servers.
"""

import unittest
import asyncio
import struct
from unittest.mock import patch
from io import BytesIO

from app.rconclient.connection import SocketClient, _PACKET_METADATA_SIZE
from app.rconclient.types import RCONPacketType


class MockStreamReader(asyncio.StreamReader):
    """Mock StreamReader for testing RCON packet handling."""

    def __init__(self, data: bytes = b""):
        self._data = BytesIO(data)

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes from the mock data."""
        data = self._data.read(n)
        if len(data) < n:
            raise ConnectionError("Mock connection closed")
        return data

    def feed_eof(self):
        """Mock feed_eof method."""
        pass


class MockStreamWriter:
    """Mock StreamWriter for testing RCON packet sending."""

    def __init__(self):
        self.data = BytesIO()
        self.closed = False

    def write(self, data: bytes):
        """Write data to the mock buffer."""
        if not self.closed:
            self.data.write(data)

    async def drain(self):
        """Mock drain method."""
        pass

    def close(self):
        """Mark the writer as closed."""
        self.closed = True

    async def wait_closed(self):
        """Mock wait_closed method."""
        pass


class TestSocketClient(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for the SocketClient class.

    This test class validates all functionality of SocketClient including:
    - Connection establishment and authentication
    - Command sending and response handling
    - Multi-packet response processing
    - Reconnection and error handling
    - Various Minecraft server failure modes
    """

    def setUp(self):
        """Set up test fixtures and environment."""
        self.password = "test_password"
        self.port = 25575
        self.timeout = 10
        self.reconnect_pause = 5

    def _create_response_data(
        self, responses: list[tuple[str, RCONPacketType, int]]
    ) -> bytes:
        """Create mock response data containing multiple packets."""
        data = b""
        for payload, packet_type, request_id in responses:
            data += SocketClient._format_packet(payload, packet_type, request_id)
        return data

    async def test_successful_authentication(self):
        """Test successful RCON authentication."""
        # Mock successful auth response
        auth_response = self._create_response_data(
            [("", RCONPacketType.AUTH_PACKET, 0)]
        )

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(auth_response)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(
                self.password, self.port, self.timeout, self.reconnect_pause
            )

            # raw assert for Ruff
            assert client is not None
            self.assertEqual(client._password, self.password)
            self.assertEqual(client._port, self.port)

    async def test_failed_authentication(self):
        """Test failed RCON authentication."""
        auth_response = self._create_response_data(
            [("", RCONPacketType.AUTH_PACKET, -1)]
        )

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(auth_response)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(
                "wrong_password", self.port, self.timeout, self.reconnect_pause
            )

            self.assertIsNone(client)

    async def test_single_packet_command_response(self):
        """Test command sending with single-packet response."""
        # Auth response + command response + dummy response
        responses = self._create_response_data(
            [
                ("", RCONPacketType.AUTH_PACKET, 0),
                (
                    "Player count: 5",
                    RCONPacketType.COMMAND_PACKET,
                    2,
                ),
                (
                    "Unknown request c8",
                    RCONPacketType.COMMAND_PACKET,
                    1002,
                ),
            ]
        )

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(responses)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(
                self.password, self.port, self.timeout, self.reconnect_pause
            )

            # raw assert for Ruff
            assert client is not None

            result = await client.send_command("list")

            self.assertEqual(result, "Player count: 5")

    async def test_multi_packet_command_response(self):
        """Test command sending with multi-packet response."""
        # Auth response + multi-packet command response + dummy response
        responses = self._create_response_data(
            [
                ("", RCONPacketType.AUTH_PACKET, 0),  # Auth success
                ("Part 1: ", RCONPacketType.COMMAND_PACKET, 2),  # First part
                ("Part 2: ", RCONPacketType.COMMAND_PACKET, 2),  # Second part
                ("Part 3", RCONPacketType.COMMAND_PACKET, 2),  # Third part
                (
                    "Unknown request c8",
                    RCONPacketType.COMMAND_PACKET,
                    1002,
                ),
            ]
        )

        with patch("socket.socket"), patch("asyncio.open_connection") as mock_open_conn:
            reader = MockStreamReader(responses)
            writer = MockStreamWriter()
            mock_open_conn.return_value = (reader, writer)

            client = await SocketClient.get_new_client(
                self.password, self.port, self.timeout, self.reconnect_pause
            )

            self.assertIsNotNone(client)

            # raw assert for Ruff
            assert client is not None
            result = await client.send_command("help")

            self.assertEqual(result, "Part 1: Part 2: Part 3")

    async def test_packet_formatting(self):
        """Test internal packet formatting functionality."""
        payload = "test command"
        packet_type = RCONPacketType.COMMAND_PACKET
        request_id = 42

        packet = SocketClient._format_packet(payload, packet_type, request_id)

        expected_body_length = len(payload.encode("utf-8"))
        expected_packet_length = expected_body_length + _PACKET_METADATA_SIZE

        length = struct.unpack("<i", packet[0:4])[0]
        self.assertEqual(length, expected_packet_length)

        req_id = struct.unpack("<i", packet[4:8])[0]
        self.assertEqual(req_id, request_id)

        pkt_type = struct.unpack("<i", packet[8:12])[0]
        self.assertEqual(pkt_type, packet_type.value)

        payload_bytes = packet[12:-2]
        self.assertEqual(payload_bytes.decode("utf-8"), payload)

        self.assertEqual(packet[-2:], b"\x00\x00")

    async def test_read_response_parsing(self):
        """Test response packet parsing functionality."""
        test_payload = "test response"
        test_request_id = 123

        packet_data = SocketClient._format_packet(
            test_payload, RCONPacketType.COMMAND_PACKET, test_request_id
        )

        reader = MockStreamReader(packet_data)

        response_id, response_body = await SocketClient._read_response(reader)

        self.assertEqual(response_id, test_request_id)
        self.assertEqual(response_body, test_payload)
