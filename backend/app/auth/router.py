import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from .user import User

from .db_connection import get_db_connection

from .roles import Role

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
)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("Auth router is being imported")

router = APIRouter()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def validate_api_key(api_key: str = Security(api_key_header)) -> User | None:
    """
    Validate the given API key and return the associated User. Allows us to act as an authenticated user.

    Raises:
        HTTPException with 401 status if the API key is invalid.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT username FROM api_keys WHERE api_key = ?",
        (api_key,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    cursor.execute(
        "SELECT role FROM users WHERE username = ?",
        (row[0],),
    )
    role_row = cursor.fetchone()
    if not role_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    return User(row[0], role=Role(int(role_row[0])))


def validate_session(request: Request) -> User:
    if not request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = request.session.get("user")
    if not data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return User(username=data["username"], role=Role(int(data["role"])))


def validate_role(required_role: Role):
    def validate_role_inner(request: Request) -> User:
        user = validate_session(request)

        if not user.role.check_permission(required_role):
            # Use 403 for forbidden access instead of 404
            raise HTTPException(status_code=403, detail="Forbidden")

        return user

    return validate_role_inner


@router.post("/login")
def login(
    request: Request,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
):
    if request.session and request.session.get("user"):
        return {"success": True, "message": "Already logged in"}

    user = check_password(username, password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Store only JSON-serializable session data
    request.session["user"] = {"username": user.username, "role": int(user.role)}
    return {
        "success": True,
        "message": "Login successful",
        "username": user.username,
        "role": user.role,
    }


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"success": True, "message": "Logout successful"}


@router.get("/account")
def get_account_info(user: User = Depends(validate_session)):
    return {"success": True, "username": user.username, "role": int(user.role)}


@router.put("/account")
def create_account_route(
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    role: Annotated[Role, Form(...)],
    owner: User = Depends(validate_role(Role.OWNER)),
):
    """
    For creating accounts of arbitrary users.
    Only 'owner' can create new accounts.
    """
    if username == owner.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create account with same name as own",
        )
    new_user = create_account(username, password, role)
    if not new_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account",
        )
    return {
        "success": True,
        "message": "Account created successfully",
        "username": new_user.username,
        "role": new_user.role,
    }


@router.delete("/account")
def delete_account_route(
    username: Annotated[str, Form(...)],
    owner=Depends(validate_role(Role.OWNER)),
):
    """
    For deleting accounts of arbitrary users by the owner, not self-deletion.
    """
    if username == owner.username:
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
    user: User = Depends(validate_session),
):
    result = change_password(user.username, new_password)

    if result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )
    return {"success": True, "message": "Password changed successfully"}


@router.put("/api-key")
def create_api_key_route(user=Depends(validate_role(Role.ADMIN))):
    api_key = generate_api_key(user.username)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create API key",
        )
    return {"success": True, "api_key": api_key}


@router.get("/api-key")
def list_api_keys_route(user=Depends(validate_role(Role.ADMIN))):
    api_keys = list_api_keys(user.username)
    return {"success": True, "api_keys": api_keys}


@router.get("/api-key/all")
def list_all_api_keys_route(user=Depends(validate_role(Role.OWNER))):
    api_keys = list_all_api_keys()
    return {"success": True, "api_keys": api_keys}


@router.delete("/api-key")
def revoke_api_key_route(
    api_key: Annotated[str, Form(...)],
    user=Depends(validate_role(Role.ADMIN)),
):
    if not revoke_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to revoke API key",
        )
    return {"success": True, "message": "API key revoked successfully"}


@router.post("/api-key/validate")
def validate_api_key_route(
    api_key: str = Depends(validate_api_key),
    user=Depends(validate_role(Role.ADMIN)),
):
    if not validate_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key",
        )
    return {"success": True, "message": "API key is valid"}
