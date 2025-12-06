"""
This is the core api router, separated from setup of server
"""

from fastapi import APIRouter, Depends, HTTPException

from app.auth import validate_api_key, validate_jwt_token

from app.common.user import User, Role

from app.rconclient import RCONCommand, RCONWorkerPool

router = APIRouter()
pool = RCONWorkerPool()  # to be initialized in main


@router.post("/session/command")
async def command(
    command: str,
    user: User = Depends(validate_jwt_token),
    require_result: bool = True,
):
    if not user.role.check_permission(Role.ADMIN):
        raise HTTPException(status_code=403, detail="Forbidden")

    rcon_command = RCONCommand.create(
        command=command, user=user, require_result=require_result
    )

    try:
        await pool.queue_command(rcon_command)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Error queuing command: {e}")

    if not require_result:
        return "Command queued successfully"

    try:
        command_result = await rcon_command.get_command_result()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing command: {e}")

    return command_result


@router.post("/key/command")
async def command_with_api_key(
    command: str, user: User = Depends(validate_api_key), require_result: bool = True
):
    rcon_command = RCONCommand.create(
        command=command, user=user, require_result=require_result
    )

    try:
        await pool.queue_command(rcon_command)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Error queuing command: {e}")

    if not require_result:
        return "Command queued successfully"

    try:
        command_result = await rcon_command.get_command_result()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing command: {e}")

    return command_result
