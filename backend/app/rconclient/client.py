"""
RCON client for Minecraft server

Since all modules are singletons, we get a natural shared client across the app.
"""

from asyncio.queues import QueueShutDown
import logging

from .worker import get_queue
from .command import RCONCommand
from .types import QueueCommandResult

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


def queue_command(command: RCONCommand) -> QueueCommandResult:
    """
    Queues a command to be sent to the RCON server.

    Args:
        command: The command string to send.
        user: The User sending the command.

    Returns:
        A QueueCommandResult object for that command.
    """

    LOG.debug("Queueing command: %s", command)
    queue = get_queue()

    result = QueueCommandResult(
        command=command,
        queued=True,
    )

    try:
        queue.put_nowait(command)
        return result
    except QueueShutDown:
        LOG.error("Queue terminated unexpectedly")
        result.queued = False
        result.error = "Queue terminated unexpectedly"
        return result
    except Exception as e:
        LOG.error("Failed to queue command: %s", e)
        result.queued = False
        result.error = str(e)
        return result
