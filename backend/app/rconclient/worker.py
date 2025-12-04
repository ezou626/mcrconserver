"""Worker that processes RCON commands from a shared queue.

Usage:
# startup
task = asyncio.create_task(
    worker(rcon_password=password, timeout=timeout)
)
# wait for worker to connect
await get_connection_event().wait()
# queue commands (see client.py)
# cleanup
shutdown_worker()
await task
"""

import asyncio
import logging

from .types import RCONCommand
from .packet import connect, send_command, disconnect
from .errors import (
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
    _queue.shutdown()


def get_connection_event() -> asyncio.Event:
    """Get the connection event that signals when the worker is connected."""
    return _connection_event


async def _establish_connection(rcon_password: str, timeout: int | None) -> bool:
    """Establish RCON connection with retries.

    Returns:
        True if connection successful, False if authentication failed.
    """
    while _running:
        try:
            connect(password=rcon_password, timeout=timeout)
            _connection_event.set()
            LOGGER.info("RCON client connected and authenticated")
            return True
        except ConnectionRefusedError:  # maybe we haven't started the server yet
            LOGGER.warning("Connection refused, retrying in 5 seconds...")
            await asyncio.sleep(5)
        except TimeoutError:
            LOGGER.warning("Connection timed out, retrying in 5 seconds...")
            await asyncio.sleep(5)
        except RCONClientAuthenticationFailed:
            LOGGER.error("RCON authentication failed, password is incorrect")
            return False
    return False


async def _process_command(command: RCONCommand) -> None:
    """Process a single RCON command.

    Raises:
        asyncio.QueueShutDown: If the queue is shut down while waiting for a command.
        TimeoutError: If a timeout occurs during command processing.
        RCONClientNotAuthenticated: If the password check fails
        RCONClientNotConnected: If the client is not connected
    """

    try:
        next_command: RCONCommand = await _queue.get()
    except asyncio.QueueShutDown:
        raise

    LOGGER.debug("Worker got command: %s", next_command)

    try:
        response = await asyncio.to_thread(send_command, command.command)
        LOGGER.debug("Worker got response: %s", response)
        command.set_command_result(response)
    except (
        TimeoutError,
        RCONClientNotAuthenticated,
        RCONClientNotConnected,
    ) as error:  # only catch our known RCON client errors
        LOGGER.error("RCON client error: %s", error)
        command.set_command_error(error)
        raise
    finally:
        _queue.task_done()


async def worker(rcon_password: str, timeout: int | None) -> None:
    """
    Asynchronous worker that processes RCON commands from a queue using our RCON client

    This function runs until the app exits, processing commands as they are added to the queue.

    No retries are performed for failed commands; errors are set on the command's Future.

    Args:
        rcon_password: The RCON password to authenticate with.
        timeout: Optional timeout for RCON operations.
    """

    while _running:
        if not await _establish_connection(rcon_password, timeout):
            LOGGER.debug("Worker shutting down")
            _queue.shutdown()
            disconnect()
            return

        try:
            await _process_command(await _queue.get())
        except asyncio.QueueShutDown:
            break
        except Exception:
            # disconnect before attempting to reconnect
            disconnect()
            continue

    LOGGER.debug("Worker shutting down")
    _queue.shutdown()
    disconnect()
