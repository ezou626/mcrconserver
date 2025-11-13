"""
This is the core api router, separated from setup of server
"""

from fastapi import APIRouter, Depends

from .auth import validate_role, validate_api_key, User, Role

from .rconclient import queue_command

router = APIRouter()


@router.post("/session/command")
async def command(
    command: str,
    user: User = Depends(validate_role(Role.ADMIN)),
    require_result: bool = True,
):
    return await queue_command(command, user, require_result=require_result)


@router.post("/key/command")
async def command_with_api_key(
    command: str, user: User = Depends(validate_api_key), require_result: bool = True
):
    return await queue_command(command, user, require_result=require_result)
