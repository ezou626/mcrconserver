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
_connection_event = asyncio.Event()


def get_queue() -> asyncio.Queue:
    """Get the shared RCON command queue.

    Returns:
        The shared asyncio.Queue instance for RCON commands.
    """
    return _queue


def shutdown_worker() -> None:
    """Signal the worker to shut down."""
    global _running
    _running = False
    _queue.put_nowait(None)  # sentinel


def get_connection_event() -> asyncio.Event:
    """Get the connection event that signals when the worker is connected."""
    return _connection_event


async def worker(rcon_password: str, timeout: int | None) -> None:
    """
    Asynchronous worker that processes RCON commands from a queue using our RCON client

    This function runs until the app exits, processing commands as they are added to the queue.

    No retries are performed for failed commands; errors are set on the command's Future.

    Args:
        rcon_password: The RCON password to authenticate with.
        timeout: Optional timeout for RCON operations.

    Returns:
        None
    """
    while _running:
        try:
            connect(password=rcon_password, timeout=timeout)
            _connection_event.set()
            LOGGER.info("RCON client connected and authenticated")
            break
        except ConnectionRefusedError:  # maybe we haven't started the server yet
            LOGGER.warning("Connection refused, retrying in 5 seconds...")
            await asyncio.sleep(5)

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
