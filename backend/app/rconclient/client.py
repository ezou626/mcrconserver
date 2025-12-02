"""
RCON client for Minecraft server

Since all modules are singletons, we get a natural shared client across the app.

Usage:

    from app.rconclient import queue_command, RCONCommand

    rcon_command = RCONCommand(command="list", user=current_user, require_result=True)
    result = queue_command(rcon_command)

    if result.queued:
        command_result = await rcon_command.get_command_result()
        print("RCON Command Result:", command_result)
"""

from asyncio.queues import QueueShutDown
import logging

from .worker import get_queue
from .command import RCONCommand
from .types import QueueCommandResult

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def queue_command(command: RCONCommand) -> QueueCommandResult:
    """
    Queues a command to be sent to the RCON server.

    Args:
        command: The command string to send.
        user: The User sending the command.

    Returns:
        A QueueCommandResult object for that command.
    """

    LOGGER.debug("Queueing command: %s", command)
    queue = get_queue()

    result = QueueCommandResult(
        command=command,
        queued=True,
    )

    try:
        queue.put_nowait(command)
        return result
    except QueueShutDown:
        LOGGER.error("Queue terminated unexpectedly")
        result.queued = False
        result.error = "Queue terminated unexpectedly"
        return result
    except Exception as e:
        LOGGER.error("Failed to queue command: %s", e)
        result.queued = False
        result.error = str(e)
        return result
