"""Worker pool that processes RCON commands from a shared queue.

The shutdown philosophy is as follows:
We allow phases to occur, with optional timeouts for each phase (or disable the phase)

Phase 1. Disallow new additions to the queue (always)
Phase 2. Process items in the queue and await the queue
Phase 3. Fail items in the queue and await the queue
Phase 4. Shut down the queue and await the workers
Phase 5. Cancel the workers and await the workers
"""

from __future__ import annotations

import asyncio
from typing import Any
import logging

from .types import RCONCommand
from .connection import SocketClient

from .rcon_exceptions import RCONClientIncorrectPassword

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


async def _worker(
    worker_id: int,
    client: SocketClient,
    queue: asyncio.Queue[RCONCommand],
    stopped: asyncio.Event,
) -> None:
    """
    Main loop for a worker task.

    Args:
        worker_id: Unique identifier for this worker
        stopping: connection_event: Event to signal when connection is established
    """
    LOGGER.info(f"Worker {worker_id}: Starting")

    while not stopped.is_set():
        try:
            command = await queue.get()
            response = await client.send_command(command.command)
            queue.task_done()
            if response is None:
                command.set_command_error(ConnectionError("RCON authentication failed"))
            else:
                command.set_command_result(response)

        except (TimeoutError, ConnectionError):
            LOGGER.warning(f"Worker {worker_id}: Connection lost, reconnecting...")
            await client.reconnect()
            continue

        except (asyncio.CancelledError, asyncio.QueueShutDown):
            break

    await client.disconnect()
    # accomodate graceful shutdown
    while True:
        try:
            command = queue.get_nowait()
            command.set_command_error(ConnectionError("Processing pool shut down"))
        except (asyncio.QueueEmpty, asyncio.CancelledError, asyncio.QueueShutDown):
            break

    LOGGER.info(f"Worker {worker_id}: Shutdown complete")


class RCONWorkerPool:
    """
    A resource manager for coroutines processing RCON commands
    """

    def __init__(
        self,
        password: str,
        port: int = 25575,
        timeout: int | None = None,
        worker_count: int = 1,
        reconnect_pause: int = 5,
        shutdown_max_seconds: int = 60,
    ) -> None:
        self._password = password
        self._port = port
        self._timeout = timeout
        self._worker_count = worker_count
        self._reconnect_pause = reconnect_pause
        self._shutdown_max_seonds = shutdown_max_seconds

        self._queue: asyncio.Queue[RCONCommand] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._stopped = asyncio.Event()
        self._stopping = asyncio.Event()

    async def __aenter__(self) -> RCONWorkerPool:
        """Start the worker pool and wait for all workers to connect."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Shutdown the worker pool gracefully."""
        LOGGER.info("Shutting down RCON worker pool")
        self._stopping.set()
        await asyncio.wait_for(self._queue.join(), self._shutdown_max_seonds)
        self._stopped.set()
        await asyncio.gather(*self._workers, return_exceptions=True)

        LOGGER.info("RCON worker pool shutdown complete")

    async def connect(self) -> None:
        """Start the worker pool and wait for all workers to connect."""
        LOGGER.info(f"Starting RCON worker pool with {self._worker_count} workers")

        self.clients = [
            SocketClient.get_new_client(
                self._password, self._port, self._timeout, self._reconnect_pause
            )
            for _ in range(self._worker_count)
        ]

        clients = await asyncio.gather(*self.clients)

        for i in range(self._worker_count):
            client = clients[i]
            if client is None:
                raise RCONClientIncorrectPassword
            worker_task = asyncio.create_task(
                _worker(i, client, self._queue, self._stopped, self._stopping)
            )
            self._workers.append(worker_task)

        LOGGER.info("All RCON workers connected successfully")

    async def queue_command(self, command: RCONCommand) -> None:
        """
        Queues a single command in the system

        :param command: the command to send to the Minecraft server
        :type command: RCONCommand
        :return: Nothing, the client should wait on the command object's result
        :rtype: None
        """
        if self._stopping.is_set():
            raise RuntimeError("Worker pool is shutting down")

        self._queue.put_nowait(command)
