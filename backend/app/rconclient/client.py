"""
RCON client for Minecraft server

Since all modules are singletons, we get a natural shared client across the app.
"""

import asyncio
from asyncio.queues import QueueShutDown
import logging

from .worker import queue
from .command import RCONCommand
from .types import QueueCommandResult
from ..auth.user import User

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


async def queue_command(command: str, user: User) -> QueueCommandResult:
    """
    Queues a command to be sent to the RCON server.

    Args:
        command: The command string to send.
        user: The User sending the command.

    Returns:
        A QueueCommandResult object for that command.
    """

    LOG.debug("Queueing command: %s by %s", command, user.username)
    future = asyncio.get_running_loop().create_future()
    task = RCONCommand(command, user, future)

    try:
        queue.put_nowait(task)
        return QueueCommandResult(
            command=task,
            queued=True,
        )
    except QueueShutDown:
        LOG.error("Queue terminated unexpectedly")
        return QueueCommandResult(
            command=task,
            queued=False,
            error="Queue terminated unexpectedly",
        )
    except Exception as e:
        LOG.error("Failed to queue command: %s", e)
        return QueueCommandResult(
            command=task,
            queued=False,
            error=str(e),
        )
