"""Defines users, RCON packet types, and RCON command structures."""

import asyncio
from asyncio import Future
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.common import User


class RCONPacketType(IntEnum):
    """Types for an RCON TCP packet.

    Defined in the `Minecraft Wiki RCON documentation <https://minecraft.wiki/w/RCON#Packets>`_.

    :cvar ERROR_PACKET: Indicates an error occurred
    :cvar MULTI_PACKET: Used for multi-packet responses
    :cvar COMMAND_PACKET: Standard command packet
    :cvar AUTH_PACKET: Authentication packet
    :cvar DUMMY_PACKET: Dummy packet used for multi-packet responses
    """

    ERROR_PACKET = -1
    MULTI_PACKET = 0
    COMMAND_PACKET = 2
    AUTH_PACKET = 3
    DUMMY_PACKET = 200


class RCONCommandSpecification(BaseModel):
    """Pydantic model for specifying RCON command configuration.

    This model allows clean specification of commands with dependencies
    for job creation, integrating well with FastAPI and JSON serialization.
    """

    id: int = Field(..., description="Unique command identifier within the job")
    cmd: str = Field(..., description="The RCON command string")
    dependencies: list[int] = Field(
        default_factory=list,
        description="List of command IDs that must complete before this command",
    )
    require_result: bool = Field(
        default=True,
        description="Whether a Future for the result is needed",
    )


@dataclass(frozen=True)
class RCONCommand:
    """Represents a command for the RCON server.

    If result is None, the command is treated as "fire and forget".
    It is the caller's responsibility to not await get_command_result in
    that case, and exception propagation is undefined behavior, though
    this implementation will not propagate exceptions in that scenario.

    :param command: The command string to be sent to the RCON server
    :param user: The user who issued the command, if applicable
    :param command_id: Generally unused except for batch processing, in which case
        ids must be unique
    :param completion: Signals when the command has completed
    :param result: Holds the result of the command, if required
    :param dependencies: RCONCommands that must complete before this one
    """

    command: str
    user: User | None
    command_id: int = 0
    completion: asyncio.Event = field(default_factory=asyncio.Event)
    result: Future | None = field(default=None, repr=False)
    dependencies: list[RCONCommand] = field(default_factory=list)

    def add_dependency(self, dependency: RCONCommand) -> None:
        """Add a dependency a worker will wait for before executing this command.

        :param dependency: The command that must complete before this one
        """
        self.dependencies.append(dependency)

    def set_command_result(self, result: str) -> None:
        """Set the result on the associated Future if one is present.

        :param result: The result of the command from the Minecraft server
        """
        if self.result is not None and not self.result.done():
            self.result.set_result(result)
            self.completion.set()

    def set_command_error(self, error: Exception) -> None:
        """Set an error on the associated Future if one is present.

        :param error: The exception that occurred while processing the command.
        """
        if self.result is not None and not self.result.done():
            self.result.set_exception(error)
            self.completion.set()

    async def get_command_result(self) -> str | None:
        """Await and get the result from the associated Future if one is present.

        :return: The result string if a Future exists, else None

        :raises Exception: If the command resulted in an error.
        """
        if self.result is not None:
            return await self.result
        return None

    @staticmethod
    def topological_sort(commands: Iterable[RCONCommand]) -> list[RCONCommand]:
        """Sorts commands using topological ordering, with sources first.

        .. note::
            Command IDs must be unique for proper sorting.

        :param commands: The list of RCONCommands to sort
        :return: The sorted list of RCONCommands or None if a cycle is detected
        :raises ValueError: If a cycle is detected in command
            dependencies or duplicate IDs exist.
        """
        # Check for duplicates first
        command_ids = [cmd.command_id for cmd in commands]
        if len(set(command_ids)) != len(command_ids):
            msg = "Duplicate command IDs detected"
            raise ValueError(msg)

        sorted_commands = []
        finished = set()
        visiting = set()

        def depth_first_search(command: RCONCommand) -> None:
            if command.command_id in finished:
                return

            if command.command_id in visiting:
                msg = "Cycle detected in command dependencies"
                raise ValueError(msg)

            visiting.add(command.command_id)

            for dependency in command.dependencies:
                depth_first_search(dependency)

            visiting.remove(command.command_id)
            finished.add(command.command_id)
            sorted_commands.append(command)

        for command in commands:
            if command.command_id not in finished:
                depth_first_search(command)

        return sorted_commands

    @classmethod
    def create_command_from_specification(
        cls,
        specification: RCONCommandSpecification,
        user: User | None,
    ) -> RCONCommand:
        """Create a command from a command specification.

        :param specification: The command specification
        :param user: The user who issued the command, if applicable
        :return: The created RCONCommand
        """
        result = (
            asyncio.get_running_loop().create_future()
            if specification.require_result
            else None
        )
        return RCONCommand(
            command=specification.cmd,
            user=user,
            command_id=specification.id,
            result=result,
        )

    @classmethod
    def create_job_from_specification(
        cls,
        job_specification: Iterable[RCONCommandSpecification],
        user: User | None,
    ) -> Iterable[RCONCommand]:
        """Create commands from a list of command specifications.

        .. note:: Does not validate the job specification for cycles,
        or order the commands. Use :meth:`topological_sort` to sort the commands
        after creation.

        :param job_specification: Defines commands and dependencies
        :param user: The user who issued the command, if applicable

        :return: The created RCONCommand instances
        """
        rcon_commands: dict[int, RCONCommand] = {}

        for cmd_spec in job_specification:
            rcon_command = RCONCommand.create_command_from_specification(cmd_spec, user)
            if cmd_spec.id in rcon_commands:
                msg = f"Duplicate command ID {cmd_spec.id} found"
                raise ValueError(msg)
            rcon_commands[cmd_spec.id] = rcon_command

        for cmd_spec in job_specification:
            depender = rcon_commands.get(cmd_spec.id)
            if not depender:
                msg = f"Command ID {cmd_spec.id} not found"
                raise ValueError(msg)

            for dependee_id in cmd_spec.dependencies:
                dependee = rcon_commands.get(dependee_id)
                if not dependee:
                    msg = f"Dependency command ID {dependee_id} not found"
                    raise ValueError(msg)
                depender.add_dependency(dependee)

        return rcon_commands.values()
