"""
This is the core api router, separated from setup of server
"""

from fastapi import APIRouter, Depends

from .auth import check_if_role_is, validate_api_key

from .rconclient import get_queue_size, queue_command

router = APIRouter()


@router.post("/session/command")
async def command(
    command: str, _user: str = Depends(check_if_role_is(["owner", "admin"]))
):
    if not command:
        return {"success": False, "message": "No command provided"}

    queue_size = get_queue_size()
    if queue_size >= 100:
        return {"success": False, "message": "Server is busy. Please try again later."}

    if queue_command(command):
        return {"success": True}
    return {"success": False, "message": "Failed to process command."}


@router.post("/key/command")
async def command_with_api_key(command: str, api_key: str):
    if not command:
        return {"success": False, "message": "No command provided"}

    if not api_key:
        return {"success": False, "message": "No API key provided"}

    if not validate_api_key(api_key):
        return {"success": False, "message": "Invalid API key"}

    queue_size = get_queue_size()
    if queue_size >= 100:
        return {"success": False, "message": "Server is busy. Please try again later."}

    if queue_command(command):
        return {"success": True}
    return {"success": False, "message": "Failed to queue command."}
