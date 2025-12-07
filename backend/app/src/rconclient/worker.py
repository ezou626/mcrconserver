"""Worker pool that processes RCON commands from a shared queue.

This module implements a configurable worker pool for handling RCON commands
with graceful shutdown capabilities. The pool can be used as a context manager
for automatic resource management.

**Shutdown Philosophy:**

Job failures or incompletes are the responsibility of the user to evaluate.
We want shutdown to be graceful and controlled, but also happen within
timing requirements (when the rest of the app exits, for example).

**Shutdown Phases:**

1. **Queue Lock**: Disallow new additions to the queue (always happens)
2. **Grace Period**: Process remaining items in the queue with timeout
3. **Queue Clear**: Fail remaining items in the queue with timeout
4. **Worker Shutdown**: Shut down the queue and await workers
5. **Force Cancel**: Cancel workers if they don't shut down gracefully

**Example Usage:**

.. code-block:: python

    async with RCONWorkerPool(password="mypassword") as pool:
        command = RCONCommand("say Hello World", user=None)
        command.result = asyncio.get_event_loop().create_future()
        await pool.queue_command(command)
        result = await command.get_command_result()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Self

from .connection import SocketClient, SocketClientConfig
from .rcon_exceptions import RCONClientIncorrectPasswordError

if TYPE_CHECKING:
    from types import TracebackType

    from .types import RCONCommand

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

    :param queue_clear_period: Seconds to wait while clearing remaining queue items
        with errors.
        Set to DISABLE to skip this phase.
        Set to NO_TIMEOUT for indefinite wait.

    :param await_shutdown_period: Seconds to wait for workers to shut down gracefully.
        Set to DISABLE for immediate cancellation.
        Set to NO_TIMEOUT for indefinite wait.
    """

    NO_TIMEOUT: ClassVar[None] = None
    DISABLE: ClassVar[int] = 0

    password: str
    port: int
    socket_timeout: int | None
    worker_count: int
    reconnect_pause: int | None

    grace_period: int | None = field(default=DISABLE)
    queue_clear_period: int | None = field(default=NO_TIMEOUT)
    await_shutdown_period: int | None = field(default=NO_TIMEOUT)

    @property
    def socket_client_config(self) -> SocketClientConfig:
        """Get a SocketClientConfig based on this worker pool configuration.

        :return: Socket client configuration
        """
        return SocketClientConfig(
            password=self.password,
            port=self.port,
            socket_timeout=self.socket_timeout,
            reconnect_pause=self.reconnect_pause,
        )


@dataclass
class RCONWorkerPoolState:
    """Runtime state for the RCON worker pool.

    This class holds mutable state that can be modified during runtime
    to signal changes to workers.
    """

    pool_should_shutdown: bool = field(default=False)
    worker_should_shutdown: bool = field(default=False)


def _fail_remaining_commands(queue: asyncio.Queue[RCONCommand]) -> None:
    """Fail all remaining commands in the queue with a shutdown error.

    :param asyncio.Queue[RCONCommand] queue: The queue to drain of commands
    """
    while True:
        try:
            command = queue.get_nowait()
            command.set_command_error(ConnectionError("Processing pool shut down"))
        except (asyncio.QueueEmpty, asyncio.QueueShutDown):
            break


async def _worker(
    worker_id: int,
    client: SocketClient,
    queue: asyncio.Queue[RCONCommand],
    state: RCONWorkerPoolState,
) -> None:
    """Process items from the RCON command queue.

    Processes commands from the queue until shutdown is requested.
    Handles connection errors gracefully by reconnecting.

    :param worker_id: Unique identifier for this worker
    :type worker_id: int
    :param client: RCON socket client for sending commands
    :type client: SocketClient
    :param queue: Shared queue containing commands to process
    :type queue: asyncio.Queue[RCONCommand]
    :param state: Runtime state object for checking shutdown signals
    :type state: RCONWorkerPoolState
    """
    LOGGER.info("Worker %d: Starting", worker_id)

    while not state.worker_should_shutdown:
        try:
            command = await queue.get()
            response = await client.send_command(command.command)
            queue.task_done()

            # Set result or error based on response
            if response is None:
                command.set_command_error(ConnectionError("RCON authentication failed"))
            else:
                command.set_command_result(response)

        except (TimeoutError, ConnectionError):
            LOGGER.exception(
                "Worker %d: Connection error, reconnecting...",
                worker_id,
            )
            await client.reconnect()
            continue
        except asyncio.QueueShutDown:
            break

    await client.disconnect()

    _fail_remaining_commands(queue)

    LOGGER.info("Worker %d: Shutdown complete", worker_id)


class RCONWorkerPool:
    """A resource manager for coroutines processing RCON commands.

    This class provides a worker pool that can process RCON commands concurrently.
    It's designed to be used as a context manager for automatic resource management.

    **Example Usage:**

    .. code-block:: python

        # Basic usage with defaults
        config = RCONWorkerPoolConfig(
            password="serverpassword",
            port=25575,
            socket_timeout=None,
            worker_count=1,
            reconnect_pause=5
        )
        async with RCONWorkerPool(config) as pool:
            command = RCONCommand("list", user=None)
            command.result = asyncio.get_event_loop().create_future()
            await pool.queue_command(command)
            result = await command.get_command_result()

        # Custom configuration
        config = RCONWorkerPoolConfig(
            password="serverpassword",
            port=25575,
            socket_timeout=30,
            worker_count=3,
            reconnect_pause=5,
            grace_period=10,  # 10 seconds to finish work
            queue_clear_period=5,  # 5 seconds to clear queue
            await_shutdown_period=5  # 5 seconds for clean shutdown
        )
        async with RCONWorkerPool(config) as pool:
            # Use the pool...
    """

    def __init__(
        self,
        config: RCONWorkerPoolConfig | None = None,
    ) -> None:
        """Initialize the RCON worker pool.

        :param config: Configuration for the worker pool
        :type config: RCONWorkerPoolConfig
        """
        self.config = config
        self.state = RCONWorkerPoolState()
        self._queue: asyncio.Queue[RCONCommand] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self.clients: list[SocketClient] = []  # Make this accessible for debugging

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
            self.clients = await asyncio.gather(*socket_clients)
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
            asyncio.create_task(_worker(i, client, self._queue, self.state))
            for i, client in enumerate(self.clients)
        ]

        LOGGER.info("All RCON workers connected successfully")

    async def _cancel_workers(self) -> None:
        """Cancel all worker tasks and wait for them to finish."""
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

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
        if self.config.queue_clear_period != RCONWorkerPoolConfig.DISABLE:
            try:
                await asyncio.wait_for(
                    self._queue.join(),
                    timeout=self.config.queue_clear_period,
                )
            except TimeoutError:
                LOGGER.warning(
                    "Queue clear period expired with %d items remaining in queue",
                    self._queue.qsize(),
                )

        # force shutdown
        self._queue.shutdown(immediate=True)

        # final cleanup - cancel workers if they haven't stopped
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

        The command will be processed by one of the available workers.
        If the command has a result Future, the caller can await
        :meth:`command.get_command_result()` to get the response.

        :param command: The command to send to the Minecraft server
        :type command: RCONCommand
        :raises RuntimeError: If the worker pool is shutting down

        **Example:**

        .. code-block:: python

            command = RCONCommand("say Hello", user=None)
            command.result = asyncio.get_event_loop().create_future()
            await pool.queue_command(command)
            response = await command.get_command_result()
        """
        if self.state.pool_should_shutdown:
            msg = "Worker pool is shutting down"
            raise RuntimeError(msg)

        self._queue.put_nowait(command)
