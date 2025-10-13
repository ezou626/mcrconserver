"""
RCON client for Minecraft server

Since all modules are singletons, we get a natural shared client across the app.
"""

import logging
from .worker import queue

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


def queue_command(command: str) -> bool:
    """
    Queues a command to be sent to the RCON server.

    Args:
        command: The command string to send.

    Returns:
        True if the command was successfully queued, False otherwise.
    """

    LOG.debug("Queueing command: %s", command)
    try:
        queue.put_nowait(command)
        return True
    except Exception as e:
        LOG.error("Failed to queue command: %s", e)
        return False


def get_queue_size() -> int:
    """
    Returns the current size of the command queue.

    Returns:
        The number of commands currently in the queue.
    """
    return queue.qsize()
