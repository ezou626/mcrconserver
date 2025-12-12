"""Unit tests for the RCON worker pool module.

This module contains comprehensive tests for the RCONWorkerPool class,
testing worker management, connection pooling, command processing,
graceful shutdown, and error handling scenarios.
"""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.common.user import Role, User
from backend.app.rconclient.command import RCONCommand
from backend.app.rconclient.rcon_exceptions import RCONClientIncorrectPasswordError
from backend.app.rconclient.worker import (
    RCONWorkerPool,
    RCONWorkerPoolConfig,
    _fail_remaining_commands,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

DEFAULT_PORT = 25575
TEST_TIMEOUT = 30
DEFUALT_PAUSE = 5


@pytest.fixture
def test_user() -> User:
    """Create a test user with admin role."""
    return User("testuser", role=Role.ADMIN)


@pytest.fixture
def worker_config() -> RCONWorkerPoolConfig:
    """Create a test worker pool configuration."""
    return RCONWorkerPoolConfig(
        password="test_password",  # noqa: S106
        port=25575,
        socket_timeout=10,
        worker_count=1,  # if we chose wrong, deadlock
        reconnect_pause=1,
        grace_period=1,
        queue_clear_period=1,
        await_shutdown_period=1,
    )


@pytest.fixture
def mock_socket_client() -> AsyncMock:
    """Create a mock SocketClient for testing."""
    mock_client = AsyncMock()
    mock_client.send_command.return_value = "test response"
    mock_client.disconnect.return_value = None
    return mock_client


class TestRCONWorkerPoolConfig:
    """Test suite for RCONWorkerPoolConfig functionality."""

    def test_config_creation_creates_socket_config(self) -> None:
        """Test that config can be created with required parameters."""
        config = RCONWorkerPoolConfig(
            password="test_pass",  # noqa: S106
            port=DEFAULT_PORT,
            socket_timeout=30,
            worker_count=1,
            reconnect_pause=5,
        )

        assert config.socket_client_config.password == "test_pass"  # noqa: S105
        assert config.socket_client_config.port == DEFAULT_PORT
        assert config.socket_client_config.socket_timeout == TEST_TIMEOUT
        assert config.worker_count == 1
        assert config.socket_client_config.reconnect_pause == DEFUALT_PAUSE

    def test_valid_shutdown_phase_timeout_validation(self) -> None:
        """Test the validation logic for shutdown phase timeouts."""
        assert RCONWorkerPoolConfig.valid_shutdown_phase_timeout(None)
        assert RCONWorkerPoolConfig.valid_shutdown_phase_timeout(0)
        assert RCONWorkerPoolConfig.valid_shutdown_phase_timeout(10)

        assert not RCONWorkerPoolConfig.valid_shutdown_phase_timeout(-1)
        assert not RCONWorkerPoolConfig.valid_shutdown_phase_timeout(-5)


@pytest.mark.asyncio
class TestFailRemainingCommands:
    """Test suite for the _fail_remaining_commands utility function."""

    async def test_fail_remaining_commands_with_items(self, test_user: User) -> None:
        """Test that remaining commands in queue are failed with error."""
        queue = asyncio.Queue()

        # Add some commands to the queue with futures
        future1 = asyncio.get_event_loop().create_future()
        future2 = asyncio.get_event_loop().create_future()
        command1 = RCONCommand(
            command="list",
            user=test_user,
            command_id=1,
            result=future1,
        )
        command2 = RCONCommand(
            command="say hello",
            user=test_user,
            command_id=2,
            result=future2,
        )

        queue.put_nowait(command1)
        queue.put_nowait(command2)

        _fail_remaining_commands(queue)

        with pytest.raises(ConnectionError, match="pool shut down"):
            await future1

        with pytest.raises(ConnectionError, match="pool shut down"):
            await future2

        assert queue.empty()

    async def test_fail_remaining_commands_with_empty_queue(self) -> None:
        """Test that function handles empty queue gracefully."""
        queue = asyncio.Queue()

        _fail_remaining_commands(queue)

        assert queue.empty()


@pytest.mark.asyncio
class TestRCONWorkerPool:
    """Test suite for RCONWorkerPool functionality."""

    @patch("backend.app.rconclient.worker.SocketClient.get_new_client")
    async def test_worker_pool_connect_auth_failure(
        self,
        mock_get_client: MagicMock,
        worker_config: RCONWorkerPoolConfig,
    ) -> None:
        """Test worker pool connection with authentication failure."""
        mock_get_client.side_effect = RCONClientIncorrectPasswordError(
            "Invalid password",
        )

        pool = RCONWorkerPool(worker_config)

        with pytest.raises(
            RCONClientIncorrectPasswordError,
        ):
            await pool.connect()

    @patch("backend.app.rconclient.worker.SocketClient.get_new_client")
    async def test_worker_pool_connect_connection_failure(
        self,
        mock_get_client: MagicMock,
        worker_config: RCONWorkerPoolConfig,
    ) -> None:
        """Test worker pool connection with connection failure."""
        mock_get_client.side_effect = ConnectionError("Connection failed")

        pool = RCONWorkerPool(worker_config)

        with pytest.raises(ConnectionError):
            await pool.connect()

    @patch("backend.app.rconclient.worker.SocketClient.get_new_client")
    async def test_context_manager_usage(
        self,
        mock_get_client: MagicMock,
        worker_config: RCONWorkerPoolConfig,
        mock_socket_client: AsyncMock,
    ) -> None:
        """Test using worker pool as context manager."""
        mock_get_client.return_value = mock_socket_client

        async with RCONWorkerPool(worker_config) as pool:
            assert len(pool._workers) == worker_config.worker_count  # noqa: SLF001

    @patch("backend.app.rconclient.worker.SocketClient.get_new_client")
    async def test_queue_single_command(
        self,
        mock_get_client: MagicMock,
        worker_config: RCONWorkerPoolConfig,
        mock_socket_client: AsyncMock,
        test_user: User,
    ) -> None:
        """Test queueing a single command for processing."""
        mock_get_client.return_value = mock_socket_client

        async with RCONWorkerPool(worker_config) as pool:
            future = asyncio.get_event_loop().create_future()
            command = RCONCommand(
                command="list",
                user=test_user,
                command_id=1,
                result=future,
            )

            await pool.queue_command(command)

            result = await asyncio.wait_for(future, timeout=2.0)
            assert result == "test response"

    @patch("backend.app.rconclient.worker.SocketClient.get_new_client")
    async def test_queue_command_during_shutdown(
        self,
        mock_get_client: MagicMock,
        worker_config: RCONWorkerPoolConfig,
        mock_socket_client: AsyncMock,
        test_user: User,
    ) -> None:
        """Test that queueing commands during shutdown raises error."""
        mock_get_client.return_value = mock_socket_client

        pool = RCONWorkerPool(worker_config)
        await pool.connect()

        await pool.shutdown()

        command = RCONCommand(command="list", user=test_user, command_id=1)

        with pytest.raises(RuntimeError, match="pool is shutting down"):
            await pool.queue_command(command)

        commands = [RCONCommand(command="list", user=test_user, command_id=1)]

        with pytest.raises(RuntimeError, match="pool is shutting down"):
            await pool.queue_job(commands)

    @patch("backend.app.rconclient.worker.SocketClient.get_new_client")
    async def test_queue_job_with_dependencies(
        self,
        mock_get_client: MagicMock,
        worker_config: RCONWorkerPoolConfig,
        mock_socket_client: AsyncMock,
        test_user: User,
    ) -> None:
        """Test queueing multiple commands with dependencies."""
        mock_get_client.return_value = mock_socket_client

        async with RCONWorkerPool(worker_config) as pool:
            future1 = asyncio.get_event_loop().create_future()
            future2 = asyncio.get_event_loop().create_future()
            command1 = RCONCommand(
                command="list",
                user=test_user,
                command_id=1,
                result=future1,
            )
            command2 = RCONCommand(
                command="say hello",
                user=test_user,
                command_id=2,
                result=future2,
            )
            command2.add_dependency(command1)

            commands = [command1, command2]
            await pool.queue_job(commands)

            results = await asyncio.gather(
                *[cmd.get_command_result() for cmd in commands],
            )
            assert all(result == "test response" for result in results)

    @patch("backend.app.rconclient.worker.SocketClient.get_new_client")
    async def test_queue_job_with_invalid_dependencies(
        self,
        mock_get_client: MagicMock,
        worker_config: RCONWorkerPoolConfig,
        mock_socket_client: AsyncMock,
        test_user: User,
    ) -> None:
        """Test that queueing bad jobs raises error."""
        mock_get_client.return_value = mock_socket_client

        async with RCONWorkerPool(worker_config) as pool:
            command1 = RCONCommand(command="list", user=test_user, command_id=1)
            command2 = RCONCommand(command="say hello", user=test_user, command_id=2)
            command1.add_dependency(command2)
            command2.add_dependency(command1)

            commands = [command1, command2]

            with pytest.raises(ValueError, match="cycle"):
                await pool.queue_job(commands)

            command1 = RCONCommand(command="list", user=test_user, command_id=1)
            command2 = RCONCommand(command="say hello", user=test_user, command_id=1)
            command1.add_dependency(command2)
            command2.add_dependency(command1)

            commands = [command1, command2]

            with pytest.raises(ValueError, match="duplicate"):
                await pool.queue_job(commands)

    @patch("backend.app.rconclient.worker.SocketClient.get_new_client")
    async def test_worker_handles_connection_error(
        self,
        mock_get_client: MagicMock,
        worker_config: RCONWorkerPoolConfig,
        test_user: User,
    ) -> None:
        """Test that workers handle connection errors gracefully."""
        mock_client = AsyncMock()
        mock_client.send_command.side_effect = ConnectionError("Connection lost")
        mock_client.reconnect.return_value = "reconnected"
        mock_client.disconnect.return_value = None

        mock_get_client.return_value = mock_client

        async with RCONWorkerPool(worker_config) as pool:
            command = RCONCommand(
                command="list",
                user=test_user,
                command_id=1,
            )

            await pool.queue_command(command)

            await asyncio.sleep(0.5)

            mock_client.send_command.assert_called_once_with("list")
