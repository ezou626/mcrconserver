from enum import IntEnum


class RCONPacketType(IntEnum):
    ERROR_PACKET = -1
    MULTI_PACKET = 0
    COMMAND_PACKET = 2
    AUTH_PACKET = 3
