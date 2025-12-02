from enum import IntEnum
from dataclasses import dataclass
from .command import RCONCommand


class RCONPacketType(IntEnum):
    """Straight from https://minecraft.wiki/w/RCON#Packets"""

    ERROR_PACKET = -1
    MULTI_PACKET = 0
    COMMAND_PACKET = 2
    AUTH_PACKET = 3


@dataclass
class QueueCommandResult:
    """Result of attempting to queue a command to the RCON worker

    Attributes:
        command: The RCONCommand that was queued.
        queued: Whether the command was successfully queued.
        error: An optional error message if queuing failed.
    """

    command: RCONCommand
    queued: bool
    error: str | None = None
