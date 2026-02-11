"""Router for handling RCON command requests."""

import asyncio
import logging
from asyncio import get_running_loop
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.common import Role, User
from backend.rconclient import RCONCommand, RCONCommandSpecification, RCONWorkerPool

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.app.auth import Validate

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class CommandResult(BaseModel):
    """Model for the result of an RCON command.

    :param id: The ID of the command
    :param result: The result of the command
    """

    id: int
    result: str | None


async def _queue_command(
    command: str,
    user: User,
    pool: RCONWorkerPool,
    *,
    require_result: bool = True,
) -> RCONCommand:
    """Queue an RCON command and optionally wait for the result."""
    future = get_running_loop().create_future() if require_result else None

    rcon_command = RCONCommand(command=command, user=user, result=future)

    try:
        await pool.queue_command(rcon_command)
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail="Error queuing command: worker shutting down",
        ) from e

    return rcon_command


async def _queue_commands(
    commands: list[RCONCommandSpecification],
    user: User,
    pool: RCONWorkerPool,
) -> Iterable[RCONCommand]:
    """Queue multiple RCON commands."""
    rcon_commands = RCONCommand.create_job_from_specification(
        commands,
        user,
    )

    try:
        await pool.queue_job(rcon_commands)
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail="Error queuing commands: worker shutting down",
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        ) from e

    return rcon_commands


async def _await_command_result(
    rcon_command: RCONCommand,
) -> CommandResult:
    """Await the result of an RCON command with exceptions."""
    try:
        command_result = await rcon_command.get_command_result()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Error executing command",
        ) from e
    return CommandResult(id=rcon_command.command_id, result=command_result)


def configure_command_router(
    router: APIRouter,
    pool: RCONWorkerPool,
    validate: Validate,
) -> APIRouter:
    """Configure the command router with necessary dependencies.

    :param router: The FastAPI APIRouter to configure
    :param pool: The RCONWorkerPool for queuing commands
    :param validate: The Validate instance for authentication and authorization
    :return: The configured APIRouter
    """

    @router.post("/session/command")
    async def command(
        command: str,
        user: Annotated[User, Depends(validate.role(Role.ADMIN))],
        *,
        require_result: bool = True,
    ) -> CommandResult | None:
        """Queue a single RCON command and optionally wait for the result.

        :param command: Minecraft command to be executed
        :param user: App user executing the command
        :param require_result: Whether to wait for the command result
        :rtype: CommandResult | None
        """
        rcon_command = await _queue_command(
            command,
            user,
            pool,
            require_result=require_result,
        )

        if not require_result:
            return None

        return await _await_command_result(rcon_command)

    @router.post("/session/commands/batch")
    async def batch_commands(
        commands: list[RCONCommandSpecification],
        user: Annotated[User, Depends(validate.role(Role.ADMIN))],
        *,
        require_result: bool = True,
    ) -> list[CommandResult] | None:
        """Queue multiple RCON commands and optionally wait for the results.

        :param commands: Description
        :param user: The app user executing the commands
        :param require_result: Whether to wait for the command results
        :return: None if not waiting, otherwise the command results
        """
        rcon_commands = await _queue_commands(commands, user, pool)

        if not require_result:
            return None

        return await asyncio.gather(
            *(_await_command_result(rcon_command) for rcon_command in rcon_commands),
        )

    @router.post("/key/command")
    async def command_with_api_key(
        command: str,
        user: Annotated[User, Depends(validate.api_key)],
        *,
        require_result: bool = True,
    ) -> CommandResult | None:
        """Queue a single RCON command using a key and optionally wait for the result.

        :param command: The Minecraft command to be executed
        :param user: The app user executing the command
        :param require_result: Whether to wait for the command result
        :return: None if not waiting, otherwise the command result
        """
        rcon_command = await _queue_command(
            command,
            user,
            pool,
            require_result=require_result,
        )

        if not require_result:
            return None

        return await _await_command_result(rcon_command)

    @router.post("/key/commands/batch")
    async def batch_commands_with_api_key(
        commands: list[RCONCommandSpecification],
        user: Annotated[User, Depends(validate.api_key)],
        *,
        require_result: bool = True,
    ) -> list[CommandResult] | None:
        """Queue multiple RCON commands and optionally wait for the results.

        :param commands: Description
        :param user: The app user executing the commands
        :param require_result: Whether to wait for the command results
        :return: None if not waiting, otherwise the command results
        """
        rcon_commands = await _queue_commands(
            commands,
            user,
            pool,
        )

        if not require_result:
            return None

        return await asyncio.gather(
            *[_await_command_result(rcon_command) for rcon_command in rcon_commands],
        )

    return router
