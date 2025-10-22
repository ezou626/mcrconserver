import asyncio
import logging

from .packet import connect, reconnect, send_command

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

queue: asyncio.Queue = asyncio.Queue(maxsize=100)


async def worker() -> None:
    """
    Asynchronous worker that processes RCON commands from a queue.

    Dotenv is already loaded to ensure environment variables are available.

    This function runs indefinitely, processing commands as they are added to the queue.

    Commands have at-most-once delivery semantics; if a command fails due to a timeout, it is not retried.
    """
    connect()

    while True:
        next_command = await queue.get()
        LOG.debug("Worker got command: %s", next_command)

        try:
            # send_command is synchronous; consider offloading to a thread if it blocks
            response = await asyncio.to_thread(send_command, next_command.command)
            LOG.debug("Worker got response: %s", response)
            next_command.set_command_result(response)
        except Exception as e:
            LOG.error("Worker encountered an error: %s", e)
            # Propagate the error to the awaiting caller
            try:
                next_command.future.set_exception(e)
            except Exception:
                pass
            try:
                reconnect()
            except Exception as re:
                LOG.error("Worker failed to reconnect: %s", re)
        finally:
            queue.task_done()
