"""
This is the core api router, separated from setup of server
"""

from fastapi import APIRouter, Depends

from .auth import validate_api_key, validate_jwt_token, User, Role

from .rconclient import queue_command, RCONCommand

router = APIRouter()


@router.post("/session/command")
async def command(
    command: str,
    user: User = Depends(validate_jwt_token),
    require_result: bool = True,
):
    # Check if user has required permissions
    if not user.role.check_permission(Role.ADMIN):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Forbidden")

    rcon_command = RCONCommand(
        command=command, user=user, require_result=require_result
    )

    result = queue_command(rcon_command)

    if not result.queued:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Failed to queue command")

    if require_result:
        command_result = await rcon_command.get_command_result()
        return command_result

    return "Command queued successfully"


@router.post("/key/command")
async def command_with_api_key(
    command: str, user: User = Depends(validate_api_key), require_result: bool = True
):
    rcon_command = RCONCommand(
        command=command, user=user, require_result=require_result
    )

    result = queue_command(rcon_command)

    if not result.queued:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Failed to queue command")

    if require_result:
        command_result = await rcon_command.get_command_result()
        return command_result

    return "Command queued successfully"
