from enum import IntEnum
from .command import RCONCommand


class RCONPacketType(IntEnum):
    ERROR_PACKET = -1
    MULTI_PACKET = 0
    COMMAND_PACKET = 2
    AUTH_PACKET = 3


class QueueCommandResult:
    def __init__(
        self, command: RCONCommand | None, processed: bool, queued: bool, message: str
    ):
        self.command = command
        self.processed = processed
        self.queued = queued
        self.message = message
