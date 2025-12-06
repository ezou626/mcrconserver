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

    async with RCONWorkerPool(password="my_password") as pool:
        command = RCONCommand("say Hello World", user=None)
        command.result = asyncio.get_event_loop().create_future()
        await pool.queue_command(command)
        result = await command.get_command_result()
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, ClassVar
import logging

from .types import RCONCommand
from .connection import SocketClient

from .rcon_exceptions import RCONClientIncorrectPassword

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


@dataclass
class ShutdownDetails:
    """Configure shutdown options for the RCON worker pool.

    This class controls how the worker pool shuts down when exiting a context
    manager or when shutdown() is called explicitly.

    :cvar NO_TIMEOUT: Constant indicating indefinite waiting for phase completion
    :cvar DISABLE: Constant indicating the phase should be skipped

    :param grace_period: Seconds to wait for remaining queue items to process.
                        Set to DISABLE to skip graceful processing.
                        Set to NO_TIMEOUT for indefinite wait.
    :type grace_period: int | None

    :param queue_clear_period: Seconds to wait while clearing remaining queue items with errors.
                              Set to DISABLE to skip this phase.
                              Set to NO_TIMEOUT for indefinite wait.
    :type queue_clear_period: int | None

    :param await_shutdown_period: Seconds to wait for workers to shut down gracefully.
                                 Set to DISABLE for immediate cancellation.
                                 Set to NO_TIMEOUT for indefinite wait.
    :type await_shutdown_period: int | None
    """

    NO_TIMEOUT: ClassVar[None] = None
    DISABLE: ClassVar[int] = 0

    grace_period: int | None = field(default=DISABLE)
    queue_clear_period: int | None = field(default=NO_TIMEOUT)
    await_shutdown_period: int | None = field(default=NO_TIMEOUT)

    pool_should_shutdown: bool = field(default=False, init=False, repr=False)
    worker_should_shutdown: bool = field(default=False, init=False, repr=False)


def _fail_remaining_commands(queue: asyncio.Queue[RCONCommand]) -> None:
    """Fail all remaining commands in the queue with a shutdown error.

    :param queue: The queue to drain of commands
    :type queue: asyncio.Queue[RCONCommand]
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
    shutdown_config: ShutdownDetails,
) -> None:
    """Main loop for a worker task.

    Processes commands from the queue until shutdown is requested.
    Handles connection errors gracefully by reconnecting.

    :param worker_id: Unique identifier for this worker
    :type worker_id: int
    :param client: RCON socket client for sending commands
    :type client: SocketClient
    :param queue: Shared queue containing commands to process
    :type queue: asyncio.Queue[RCONCommand]
    :param shutdown_config: Configuration controlling shutdown behavior
    :type shutdown_config: ShutdownDetails
    """
    LOGGER.info(f"Worker {worker_id}: Starting")

    while not shutdown_config.worker_should_shutdown:
        try:
            command = await queue.get()
            response = await client.send_command(command.command)
            queue.task_done()

            # Set result or error based on response
            if response is None:
                command.set_command_error(ConnectionError("RCON authentication failed"))
            else:
                command.set_command_result(response)

        except (TimeoutError, ConnectionError) as e:
            LOGGER.warning(
                f"Worker {worker_id}: Connection error ({e}), reconnecting..."
            )
            await client.reconnect()
            continue
        except asyncio.QueueShutDown:
            break

    await client.disconnect()

    _fail_remaining_commands(queue)

    LOGGER.info(f"Worker {worker_id}: Shutdown complete")


class RCONWorkerPool:
    """A resource manager for coroutines processing RCON commands.

    This class provides a worker pool that can process RCON commands concurrently.
    It's designed to be used as a context manager for automatic resource management.

    **Example Usage:**

    .. code-block:: python

        # Basic usage with defaults
        async with RCONWorkerPool(password="server_password") as pool:
            command = RCONCommand("list", user=None)
            command.result = asyncio.get_event_loop().create_future()
            await pool.queue_command(command)
            result = await command.get_command_result()

        # Custom configuration
        shutdown_config = ShutdownDetails(
            grace_period=10,  # 10 seconds to finish work
            queue_clear_period=5,  # 5 seconds to clear queue
            await_shutdown_period=5  # 5 seconds for clean shutdown
        )
        async with RCONWorkerPool(
            password="server_password",
            worker_count=3,
            shutdown_config=shutdown_config
        ) as pool:
            # Use the pool...
    """

    def __init__(
        self,
        password: str,
        port: int = 25575,
        socket_timeout: int | None = None,
        worker_count: int = 1,
        reconnect_pause: int = 5,
        shutdown_config: ShutdownDetails | None = None,
    ) -> None:
        """Initialize the RCON worker pool.

        :param password: RCON server password for authentication
        :type password: str
        :param port: RCON server port (default: 25575)
        :type port: int
        :param socket_timeout: Socket timeout in seconds (None for no timeout)
        :type socket_timeout: int | None
        :param worker_count: Number of concurrent workers (default: 1)
        :type worker_count: int
        :param reconnect_pause: Seconds to wait between reconnection attempts (default: 5)
        :type reconnect_pause: int
        :param shutdown_config: Configuration for shutdown behavior
        :type shutdown_config: ShutdownDetails | None
        """
        self._password = password
        self._port = port
        self._socket_timeout = socket_timeout
        self._worker_count = worker_count
        self._reconnect_pause = reconnect_pause
        self._shutdown_details = shutdown_config or ShutdownDetails()

        self._queue: asyncio.Queue[RCONCommand] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self.clients: list[SocketClient] = []  # Make this accessible for debugging

    async def __aenter__(self) -> RCONWorkerPool:
        """Start the worker pool and wait for all workers to connect."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.shutdown()
        return

    async def connect(self) -> None:
        """Start the worker pool and wait for all workers to connect.

        :raises RCONClientIncorrectPassword: If any worker fails to authenticate
        :raises TimeoutError: If any worker times out during connection
        :raises ConnectionError: If any worker fails to connect
        """
        LOGGER.info(f"Starting RCON worker pool with {self._worker_count} workers")

        socket_clients = [
            SocketClient.get_new_client(
                self._password, self._port, self._socket_timeout, self._reconnect_pause
            )
            for _ in range(self._worker_count)
        ]

        try:
            self.clients = await asyncio.gather(*socket_clients)
        except RCONClientIncorrectPassword as e:
            raise RCONClientIncorrectPassword(
                "One or more workers failed to authenticate"
            ) from e
        except (TimeoutError, ConnectionError) as e:
            raise e

        self._workers = [
            asyncio.create_task(_worker(i, client, self._queue, self._shutdown_details))
            for i, client in enumerate(self.clients)
        ]

        LOGGER.info("All RCON workers connected successfully")

    async def _await_workers_shutdown(self) -> bool:
        """Wait for workers to shut down gracefully.

        :return: True if workers shut down within timeout, False otherwise
        :rtype: bool
        """
        timeout = self._shutdown_details.await_shutdown_period

        # Handle DISABLE case
        if timeout == ShutdownDetails.DISABLE:
            return False

        try:
            await asyncio.wait_for(
                asyncio.gather(*self._workers, return_exceptions=True), timeout
            )
            return True
        except asyncio.TimeoutError:
            return False

    async def _cancel_workers(self) -> None:
        """Cancel all worker tasks and wait for them to finish."""
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

    async def _wait_for_queue_with_timeout(
        self, timeout: int | None, phase_name: str
    ) -> bool:
        """Wait for queue to finish with optional timeout.

        :param timeout: Timeout in seconds, or None for no timeout
        :type timeout: int | None
        :param phase_name: Name of the phase for logging
        :type phase_name: str
        :return: True if completed within timeout, False if timed out
        :rtype: bool
        """
        if timeout == ShutdownDetails.DISABLE:
            return False

        try:
            await asyncio.wait_for(self._queue.join(), timeout)
            return True
        except asyncio.TimeoutError:
            LOGGER.debug(f"Timeout during {phase_name} phase")
            return False

    async def shutdown(self) -> None:
        """Shutdown the worker pool gracefully.

        Follows the configured shutdown phases:
        1. Stop accepting new commands
        2. Wait for current work to finish (grace period)
        3. Clear remaining queue items with errors (queue clear period)
        4. Wait for workers to shut down gracefully
        5. Force cancel workers if needed
        """
        LOGGER.info("Shutting down RCON worker pool")
        self._shutdown_details.pool_should_shutdown = True

        # grace period - let current work finish
        if await self._wait_for_queue_with_timeout(
            self._shutdown_details.grace_period, "grace period"
        ):
            if await self._await_workers_shutdown():
                LOGGER.info("RCON worker pool shut down gracefully")
                return

        # queue clear period - fail remaining items
        self._shutdown_details.worker_should_shutdown = True
        if await self._wait_for_queue_with_timeout(
            self._shutdown_details.queue_clear_period, "queue clear"
        ):
            if await self._await_workers_shutdown():
                LOGGER.info("RCON worker pool shut down after clearing queue")
                return

        # force shutdown
        self._queue.shutdown(immediate=True)

        # final cleanup - cancel workers if they haven't stopped
        if not await self._await_workers_shutdown():
            await self._cancel_workers()

        LOGGER.info("RCON worker pool forcibly shut down")

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
        if self._shutdown_details.pool_should_shutdown:
            raise RuntimeError("Worker pool is shutting down")

        self._queue.put_nowait(command)
