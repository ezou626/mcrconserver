"""Router for handling RCON command requests."""

import logging
from asyncio import get_event_loop
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.src.common import Role, User
from app.src.rconclient import RCONCommand, RCONWorkerPool

if TYPE_CHECKING:
    from app.src.auth import Validate

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


async def _queue_command(
    command: str,
    user: User,
    pool: RCONWorkerPool,
    *,
    require_result: bool = True,
) -> RCONCommand:
    """Queue an RCON command and optionally wait for the result."""
    future = get_event_loop().create_future() if require_result else None

    rcon_command = RCONCommand(command=command, user=user, result=future)

    try:
        await pool.queue_command(rcon_command)
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail="Error queuing command: worker shutting down",
        ) from e

    return rcon_command


async def _await_command_result(
    rcon_command: RCONCommand,
) -> str:
    """Await the result of an RCON command."""
    try:
        command_result = await rcon_command.get_command_result()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Error executing command",
        ) from e

    if command_result is None:
        raise HTTPException(
            status_code=500,
            detail="No result returned from command",
        )

    return command_result


def configure_command_router(
    router: APIRouter,
    pool: RCONWorkerPool,
    validate: Validate,
) -> None:
    """Configure the command router with necessary dependencies.

    :param router: The FastAPI APIRouter to configure
    :param pool: The RCONWorkerPool for queuing commands
    :param validate: The Validate instance for authentication and authorization
    """

    @router.post("/session/command")
    async def command(
        command: str,
        user: Annotated[User, Depends(validate.role(Role.ADMIN))],
        *,
        require_result: bool = True,
    ) -> str:
        rcon_command = await _queue_command(
            command,
            user,
            pool,
            require_result=require_result,
        )

        if not require_result:
            return "Command queued successfully"

        return await _await_command_result(rcon_command)

    @router.post("/key/command")
    async def command_with_api_key(
        command: str,
        user: Annotated[User, Depends(validate.api_key)],
        *,
        require_result: bool = True,
    ) -> str:
        rcon_command = await _queue_command(
            command,
            user,
            pool,
            require_result=require_result,
        )

        if not require_result:
            return "Command queued successfully"

        return await _await_command_result(rcon_command)
