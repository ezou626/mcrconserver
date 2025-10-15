import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from .account_helpers import (
    change_password,
    check_password,
    create_account,
    delete_account,
)
from .key_helpers import (
    generate_api_key,
    list_api_keys,
    list_all_api_keys,
    revoke_api_key,
    validate_api_key,
)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("Auth router is being imported")

router = APIRouter()


def validate_session(request: Request) -> dict:
    session = request.session

    # Ensure session exists and has a username
    username = session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {"username": username}


def check_if_role_is(allowed_roles: list[str]):
    def validate_role(request: Request) -> dict:
        session = request.session

        # Ensure session exists and has a username
        username = session.get("username")
        role = session.get("role")
        if not username:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if role not in allowed_roles:
            raise HTTPException(status_code=404, detail="Not found")

        return {"username": username, "role": role}

    return validate_role


@router.post("/login")
def login(
    request: Request,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
):
    if request.session and request.session.get("username"):
        return {"success": True, "message": "Already logged in"}

    role = check_password(username, password)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    request.session["username"] = username
    request.session["role"] = role
    return {
        "success": True,
        "message": "Login successful",
        "username": username,
        "role": role,
    }


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"success": True, "message": "Logout successful"}


@router.get("/account")
def get_account_info(user=Depends(validate_session)):
    return {"success": True, "username": user["username"], "role": user["role"]}


@router.put("/account")
def create_account_route(
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    role: Annotated[str, Form(...)],
    user_role=Depends(check_if_role_is(["owner"])),
):
    """For creating accounts of arbitrary users."""
    if username == user_role["username"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create account with same name as own",
        )
    if not create_account(username, password, role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create account",
        )
    return {"success": True, "message": "Account created successfully"}


@router.delete("/account")
def delete_account_route(
    username: Annotated[str, Form(...)],
    user_role=Depends(check_if_role_is(["owner"])),
):
    """
    For deleting accounts of arbitrary users, not self-deletion.
    """
    if username == user_role["username"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete own account",
        )
    if not delete_account(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete account",
        )
    return {"success": True, "message": "Account deleted successfully"}


@router.patch("/account/password")
def change_password_route(
    new_password: Annotated[str, Form(...)],
    user=Depends(validate_session),
):
    result = change_password(user["username"], new_password)

    if result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )
    return {"success": True, "message": "Password changed successfully"}


@router.put("/api-key")
def create_api_key_route(user=Depends(check_if_role_is(["owner", "admin"]))):
    api_key = generate_api_key(user["username"])
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create API key",
        )
    return {"success": True, "api_key": api_key}


@router.get("/api-key")
def list_api_keys_route(user=Depends(check_if_role_is(["owner", "admin"]))):
    api_keys = list_api_keys(user["username"])
    return {"success": True, "api_keys": api_keys}


@router.get("/api-key/all")
def list_all_api_keys_route(user=Depends(check_if_role_is(["owner"]))):
    api_keys = list_all_api_keys()
    return {"success": True, "api_keys": api_keys}


@router.delete("/api-key")
def revoke_api_key_route(
    api_key: Annotated[str, Form(...)],
    user=Depends(check_if_role_is(["owner", "admin"])),
):
    if not revoke_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to revoke API key",
        )
    return {"success": True, "message": "API key revoked successfully"}


@router.post("/api-key/validate")
def validate_api_key_route(
    api_key: Annotated[str, Form(...)],
    user=Depends(check_if_role_is(["owner", "admin"])),
):
    if not validate_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key",
        )
    return {"success": True, "message": "API key is valid"}
