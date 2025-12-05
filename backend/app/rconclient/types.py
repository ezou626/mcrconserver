"""Data classes used in the RCON client module."""

from __future__ import annotations

import asyncio
from enum import IntEnum
from dataclasses import dataclass, field
from asyncio import Future, get_event_loop

from app.common.user import User


class RCONPacketType(IntEnum):
    """Types for an RCON TCP packet defined in https://minecraft.wiki/w/RCON#Packets"""

    ERROR_PACKET = -1
    MULTI_PACKET = 0
    COMMAND_PACKET = 2
    AUTH_PACKET = 3


@dataclass(frozen=True)
class RCONCommand:
    """
    Represents a command for the RCON server, including the command string, the user
    and an optional Future to hold the result.

    If _result is None, the command is treated as "fire and forget".
    It is the caller's responsibility to not await get_command_result in
    that case, and exception propagation is undefined behavior, though
    this implementation will not propagate exceptions in that scenario.
    """

    command: str
    user: User | None
    completion: asyncio.Event = field(default_factory=asyncio.Event)
    result: Future | None = field(default=None, repr=False)
    dependencies: list[RCONCommand] = field(default_factory=list)

    def add_dependency(self, dependency: RCONCommand):
        """
        Adds a dependency a worker will wait for before executing this command.

        :param dependency: The command that must complete before this one
        :type dependency: RCONCommand
        """
        self.dependencies.append(dependency)

    def set_command_result(self, result: str) -> None:
        """
        Set the result on the associated Future if one is present.

        :param result: The result of the command from the Minecraft server
        :type result: str
        """
        if self.result is not None and not self.result.done():
            self.result.set_result(result)
            self.completion.set()

    def set_command_error(self, error: Exception) -> None:
        """
        Set an error on the associated Future if one is present.

        :param error: The exception that occurred while processing the command.
        :type error: Exception
        """
        if self.result is not None and not self.result.done():
            self.result.set_exception(error)
            self.completion.set()

    async def get_command_result(self) -> str | None:
        """
        Await and get the result from the associated Future if one is present.

        :return: The result string if a Future exists, else None
        :rtype: str | None

        :raises Exception: If the command resulted in an error.
        """
        if self.result is not None:
            return await self.result
        return None

    @classmethod
    def create(
        cls,
        command: str,
        user: User | None,
        dependencies: list[RCONCommand] | None = None,
        require_result: bool = False,
    ) -> RCONCommand:
        """
        Hide future initialization from end-user

        :param command: the command to execute
        :type command: str
        :param user: the app user executing the command
        :type user: User | None
        :param dependencies: RCONCommands that must be executed before this one
        :type dependencies: list[RCONCommand] | None
        :param require_result: Whether the result will be required in the future by the creator
        :type require_result: bool
        :return: the created RCONCommand
        :rtype: RCONCommand
        """
        if dependencies is None:
            dependencies = []
        result = get_event_loop().create_future() if require_result else None
        return cls(command=command, user=user, result=result, dependencies=dependencies)


@dataclass
class QueueCommandResult:
    """
    Result of attempting to queue a command to the RCON worker
    """

    command: RCONCommand
    error: str | None = None
