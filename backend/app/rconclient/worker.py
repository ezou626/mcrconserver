import asyncio
import logging

from .command import RCONCommand
from .packet import connect, reconnect, send_command, disconnect

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


async def worker() -> None:
    """
    Asynchronous worker that processes RCON commands from a queue.

    Dotenv is already loaded to ensure environment variables are available.

    This function runs indefinitely, processing commands as they are added to the queue.

    Commands have at-most-once delivery semantics; if a command fails due to a timeout, it is not retried.
    """
    connect()

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
        except Exception as e:
            LOGGER.error("Worker encountered an error: %s", e)
            next_command.set_command_error(e)
            try:
                reconnect()
            except Exception as re:
                LOGGER.error("Worker failed to reconnect: %s", re)
        finally:
            _queue.task_done()

    disconnect()
