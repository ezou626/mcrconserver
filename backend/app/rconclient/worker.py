"""Worker pool that processes RCON commands from a shared queue."""

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
    stopping: asyncio.Event,
) -> None:
    """
    Main loop for a worker task.

    Args:
        worker_id: Unique identifier for this worker
        stopping: connection_event: Event to signal when connection is established
    """
    LOGGER.info(f"Worker {worker_id}: Starting")

    while not stopping.is_set():
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

    await client.disconnect()
    # empty queue, marking all results with errors
    while True:
        try:
            command = queue.get_nowait()
            command.set_command_error(ConnectionError("Processing pool shut down"))
        except asyncio.QueueEmpty:
            break

    LOGGER.info(f"Worker {worker_id}: Shutdown complete")


class RCONWorkerPool:
    """
    Docstring for RCONWorkerPool

    :var:
    """

    def __init__(
        self,
        password: str,
        port: int = 25575,
        timeout: int | None = None,
        worker_count: int = 1,
        reconnect_pause: int = 5,
    ) -> None:
        self._password = password
        self._port = port
        self._timeout = timeout
        self._worker_count = worker_count
        self._reconnect_pause = reconnect_pause

        self._queue: asyncio.Queue[RCONCommand] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()

    async def __aenter__(self) -> RCONWorkerPool:
        """Start the worker pool and wait for all workers to connect."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Shutdown the worker pool gracefully."""
        LOGGER.info("Shutting down RCON worker pool")

        self._stopping.set()
        await self._queue.join()
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
                _worker(i, client, self._queue, self._stopping)
            )
            self._workers.append(worker_task)

        LOGGER.info("All RCON workers connected successfully")

    async def queue_command(self, command: RCONCommand) -> str | None:
        """
        Docstring for queue_command

        :param self: Description
        :param command: Description
        :type command: RCONCommand
        :return: Description
        :rtype: str | None
        """
        if self._stopping.is_set():
            raise RuntimeError("Worker pool is shutting down")

        self._queue.put_nowait(command)
