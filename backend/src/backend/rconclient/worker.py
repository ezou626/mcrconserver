"""Worker pool that processes RCON commands from a shared queue.

This module implements a configurable worker pool for handling RCON commands
with graceful shutdown capabilities. The pool can be used as a context manager
for automatic resource management.

**Shutdown Philosophy:**

Job failures or incompletes are the responsibility of the user to evaluate.
We want shutdown to be graceful and controlled, but also happen within
timing requirements (when the rest of the app exits, for example).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Self

from .command import RCONCommand
from .connection import SocketClient, SocketClientConfig
from .rcon_exceptions import RCONClientIncorrectPasswordError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import TracebackType


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


@dataclass
class RCONWorkerPoolConfig:
    """Configure the RCON worker pool behavior.

    :cvar NO_TIMEOUT: Constant indicating indefinite waiting for phase completion
    :cvar DISABLE: Constant indicating the phase should be skipped

    :param password: RCON server password for authentication
    :param port: RCON server port
    :param socket_timeout: Socket timeout in seconds
    :param worker_count: Number of concurrent workers
    :param reconnect_pause: Seconds to wait between reconnection attempts

    :param grace_period: Seconds to wait for remaining queue items to process.
        Set to DISABLE to skip graceful processing.
        Set to NO_TIMEOUT for indefinite wait.

    :param await_shutdown_period: Seconds to wait for workers to shut down gracefully.
        Set to DISABLE for immediate cancellation.
        Set to NO_TIMEOUT for indefinite wait.

    :param command_delay: Minimum seconds between consecutive commands on a
        single worker.  Prevents overwhelming the RCON server when commands
        are queued faster than the server can handle them.
        Set to DISABLE (0) to send commands as fast as possible.
    """

    NO_TIMEOUT: ClassVar[None] = None
    DISABLE: ClassVar[int] = 0
    INFINITE: ClassVar[int] = SocketClientConfig.INFINITE

    password: str
    port: int
    socket_timeout: int | None
    worker_count: int
    reconnect_pause: int | None

    grace_period: int | None = field(default=DISABLE)
    await_shutdown_period: int | None = field(default=NO_TIMEOUT)
    retry_client_auth_attempts: int = field(default=INFINITE)
    command_delay: float = field(default=DISABLE)

    def __post_init__(self) -> None:
        """Create a SocketClientConfig based on this worker pool configuration."""
        self.socket_client_config = SocketClientConfig(
            password=self.password,
            port=self.port,
            socket_timeout=self.socket_timeout,
            reconnect_pause=self.reconnect_pause,
            retry_attempts=self.retry_client_auth_attempts,
        )

    @staticmethod
    def valid_shutdown_phase_timeout(value: int | None) -> bool:
        """Validate a timeout value.

        :param value: The timeout value to validate
        :return: True if valid, else False
        """
        if value is None:
            return True
        return value >= RCONWorkerPoolConfig.DISABLE


@dataclass
class RCONWorkerPoolState:
    """Runtime state for the RCON worker pool.

    This class holds mutable state that can be modified during runtime
    to signal changes to workers.
    """

    pool_should_shutdown: bool = field(default=False)
    worker_should_shutdown: bool = field(default=False)


async def _worker(
    worker_id: int,
    client: SocketClient,
    queue: asyncio.Queue[RCONCommand],
    state: RCONWorkerPoolState,
    command_delay: float = 0,
) -> None:
    """Process items from the RCON command queue.

    Processes commands from the queue until shutdown is requested.
    Handles connection errors gracefully by reconnecting.

    :param worker_id: Unique identifier for this worker
    :param client: RCON socket client for sending commands
    :param queue: Shared queue containing commands to process
    :param state: Runtime state object for checking shutdown signals
    :param command_delay: Minimum seconds to wait between consecutive commands
    """
    LOGGER.info("Worker %d: Starting", worker_id)

    while not state.worker_should_shutdown:
        try:
            command = await queue.get()
        except asyncio.QueueShutDown:
            break

        try:
            if command.dependencies:
                await asyncio.gather(
                    *(dep.completion.wait() for dep in command.dependencies),
                )
            response = await client.send_command(command.command)
            queue.task_done()

            if response is None:
                command.set_command_error(ConnectionError("RCON authentication failed"))
            else:
                command.set_command_result(response)

        except (TimeoutError, ConnectionError) as e:
            LOGGER.exception(
                "Worker %d: Connection error, reconnecting...",
                worker_id,
            )
            queue.task_done()
            if command.result is not None:
                command.set_command_error(e)
            await client.reconnect()
            continue

        if command_delay > 0:
            await asyncio.sleep(command_delay)

    await client.disconnect()

    LOGGER.info("Worker %d: Shutdown complete", worker_id)


class RCONWorkerPool:
    """A resource manager for coroutines processing RCON commands.

    This class provides a worker pool that can process RCON commands concurrently.
    It's designed to be used as a context manager for automatic resource management.

    .. code-block:: python
        async with RCONWorkerPool(config) as pool:
            future = asyncio.get_running_loop().create_future()
            command = RCONCommand("list", user=None, result=future)
            await pool.queue_command(command)
            result = await command.get_command_result()
    """

    def __init__(
        self,
        config: RCONWorkerPoolConfig | None = None,
    ) -> None:
        """Initialize the RCON worker pool.

        :param config: Configuration for the worker pool
        """
        self.config = config
        self.state = RCONWorkerPoolState()
        self._queue: asyncio.Queue[RCONCommand] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._clients: list[SocketClient] = []

    async def __aenter__(self) -> Self:
        """Start the worker pool and wait for all workers to connect."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Shutdown the worker pool gracefully.

        :param exc_type: Type of exception if raised within context
        :param exc_val: Exception value if raised within context
        :param exc_tb: Description of traceback if exception raised
        """
        await self.shutdown()

    async def connect(self) -> None:
        """Start the worker pool and wait for all workers to connect.

        :raises RCONClientIncorrectPassword: If any worker fails to authenticate
        :raises TimeoutError: If any worker times out during connection
        :raises ConnectionError: If any worker fails to connect
        """
        if self.config is None:
            msg = "RCONWorkerPool configuration must be provided"
            raise ValueError(msg)

        if self.config.password is None:
            msg = "Password must be provided"
            raise RCONClientIncorrectPasswordError(msg)

        LOGGER.info(
            "Starting RCON worker pool with %s workers",
            self.config.worker_count,
        )

        socket_clients = [
            SocketClient.get_new_client(
                self.config.socket_client_config,
            )
            for _ in range(self.config.worker_count)
        ]

        try:
            self._clients = await asyncio.gather(*socket_clients)
        except RCONClientIncorrectPasswordError as e:
            msg = "One or more workers failed to authenticate"
            LOGGER.exception(msg)
            raise RCONClientIncorrectPasswordError(
                msg,
            ) from e
        except (TimeoutError, ConnectionError):
            LOGGER.exception("One or more workers failed to connect")
            raise

        self._workers = [
            asyncio.create_task(
                _worker(i, client, self._queue, self.state, self.config.command_delay),
            )
            for i, client in enumerate(self._clients)
        ]

        LOGGER.info("All RCON workers connected successfully")

    async def shutdown(self) -> None:
        """Shutdown the worker pool gracefully.

        Follows the configured shutdown phases:
        1. Stop accepting new commands
        2. Wait for current work to finish (grace period)
        3. Clear remaining queue items with errors (queue clear period)
        4. Wait for workers to shut down gracefully
        5. Force cancel workers if needed
        """
        if self.config is None:
            msg = "RCONWorkerPool configuration must be provided"
            raise ValueError(msg)

        LOGGER.info("Shutting down RCON worker pool")
        self.state.pool_should_shutdown = True

        # grace period - let current work finish
        if self.config.grace_period != RCONWorkerPoolConfig.DISABLE:
            try:
                await asyncio.wait_for(
                    self._queue.join(),
                    timeout=self.config.grace_period,
                )
            except TimeoutError:
                LOGGER.warning(
                    "Grace period expired with %d items remaining in queue",
                    self._queue.qsize(),
                )

        # queue clear period - fail remaining items
        self.state.worker_should_shutdown = True
        while self._queue.qsize():
            command = self._queue.get_nowait()
            command.set_command_error(ConnectionError("Processing pool shut down"))
        self._queue.shutdown(immediate=True)

        if self.config.await_shutdown_period != RCONWorkerPoolConfig.DISABLE:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True),
                    timeout=self.config.await_shutdown_period,
                )
            except TimeoutError:
                LOGGER.warning("Worker shutdown period expired, cancelling workers")

        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

        LOGGER.info("RCON worker pool shutdown complete")

    async def queue_command(self, command: RCONCommand) -> None:
        """Queue a single command for processing.

        :param command: The command to send to the Minecraft server
        :raises RuntimeError: If the worker pool is shutting down
        """
        if self.state.pool_should_shutdown:
            msg = "Worker pool is shutting down"
            raise RuntimeError(msg)

        LOGGER.debug("Queueing RCON command: %s", command)
        self._queue.put_nowait(command)

    async def queue_job(
        self,
        commands: Iterable[RCONCommand],
    ) -> None:
        """Queue multiple commands for processing. Sorted to avoid deadlocks.

        :param commands: The list of commands to send to the Minecraft server
        :raises RuntimeError: If the worker pool is shutting down
        :raises ValueError: If a cycle is detected in command dependencies
            or duplicate IDs exist.
        """
        if self.state.pool_should_shutdown:
            msg = "Worker pool is shutting down"
            raise RuntimeError(msg)

        try:
            sorted_commands = RCONCommand.topological_sort(commands)
        except ValueError as e:
            msg = "Failed to sort commands for job due to cycle or duplicate IDs"
            LOGGER.exception(msg)
            raise ValueError(msg) from e
        for command in sorted_commands:
            LOGGER.debug("Queueing RCON command: %s", command)
            self._queue.put_nowait(command)
