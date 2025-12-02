import asyncio
import logging

from .command import RCONCommand
from .packet import connect, send_command, disconnect
from .errors import (
    RCONClientTimeout,
    RCONClientNotConnected,
    RCONClientNotAuthenticated,
    RCONClientAuthenticationFailed,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

_queue: asyncio.Queue = asyncio.Queue()
_running = True


def get_queue() -> asyncio.Queue:
    return _queue


def shutdown_worker() -> None:
    global _running
    _running = False
    _queue.put_nowait(None)


async def worker(rcon_password: str, timeout: int | None) -> None:
    """
    Asynchronous worker that processes RCON commands from a queue using our RCON client

    This function runs until the app exits, processing commands as they are added to the queue.

    No retries are performed for failed commands; errors are set on the command's Future.
    """
    connect(password=rcon_password, timeout=timeout)

    while _running:
        next_command: RCONCommand = await _queue.get()

        if next_command is None:
            LOGGER.debug("Worker received shutdown signal")
            break

        LOGGER.debug("Worker got command: %s", next_command)

        try:
            # send_command is synchronous, run in thread for interactivity
            response = await asyncio.to_thread(send_command, next_command.command)
            LOGGER.debug("Worker got response: %s", response)
            next_command.set_command_result(response)
        except (
            RCONClientTimeout,
            RCONClientNotAuthenticated,
            RCONClientNotConnected,
        ) as e:  # only catch our known RCON client errors
            LOGGER.error("RCON client error: %s", e)
            next_command.set_command_error(e)
            try:
                disconnect()
                connect(password=rcon_password, timeout=timeout)
            except (RCONClientAuthenticationFailed, RCONClientTimeout) as re:
                LOGGER.error("Worker failed to reauthenticate after error: %s", re)
        finally:
            _queue.task_done()

    disconnect()
