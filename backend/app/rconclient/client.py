"""
RCON client for Minecraft server

Since all modules are singletons, we get a natural shared client across the app.
"""

import asyncio
import logging

from .worker import queue
from .command import RCONCommand
from ..auth.user import User

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


async def queue_command(command: str | None, user: User) -> dict:
    """
    Queues a command to be sent to the RCON server.

    Args:
        command: The command string to send.

    Returns:
        A dictionary with the result of the command execution, good for HTTP response.
    """

    if not command:
        return {"processed": False, "message": "No command provided"}

    LOG.debug("Queueing command: %s by %s", command, user.username)
    future = asyncio.get_running_loop().create_future()
    task = RCONCommand(command, user, future)

    if queue.full():
        return {
            "processed": False,
            "message": "Server is busy. Please try again later.",
        }

    try:
        queue.put_nowait(task)
        result = await future
        return {"processed": True, "message": result}
    except Exception as e:
        LOG.error("Failed to queue command: %s", e)
        return {"processed": False, "message": str(e)}
