import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Form, HTTPException, status
from app.common.user import User, Role

from .queries import AuthQueries
from .utils import create_access_token
from .validators import validate_jwt_token, validate_role, validate_api_key
from .models import (
    PaginationInfo,
    ApiKeyInfo,
    ApiKeyWithUser,
    LoginResponse,
    AccountInfo,
    MessageResponse,
)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    user = AuthQueries.authenticate_user(username, password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(user)

    return LoginResponse(
        access_token=access_token, username=user.username, role=int(user.role)
    )


@router.post("/logout", response_model=MessageResponse)
def logout():
    """
    Logout endpoint. With JWT, logout is handled client-side by discarding the token.
    """
    return MessageResponse(message="Logout successful")


@router.get("/account", response_model=AccountInfo)
def get_account_info(user: User = Depends(validate_jwt_token)):
    return AccountInfo(username=user.username, role=int(user.role))


@router.put("/account")
def create_account_route(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    role: Annotated[int, Form()],
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
    new_user = User(username, role=Role(role))
    error = AuthQueries.create_account(new_user, password)
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    return AccountInfo(username=new_user.username, role=int(new_user.role))


@router.delete("/account", response_model=MessageResponse)
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
    if not AuthQueries.delete_account(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete account",
        )
    return MessageResponse(message="Account deleted successfully")


@router.patch("/account/password", response_model=MessageResponse)
def change_password_route(
    new_password: Annotated[str, Form(...)],
    user: User = Depends(validate_jwt_token),
):
    result = AuthQueries.change_password(user.username, new_password)

    if result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )
    return MessageResponse(message="Password changed successfully")


@router.put("/api-key")
def create_api_key_route(user=Depends(validate_role(Role.ADMIN))):
    api_key = AuthQueries.generate_api_key(user)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create API key",
        )
    return {"api_key": api_key}


@router.get("/api-key")
def list_api_keys_route(
    page: int = 1, limit: int = 10, user=Depends(validate_role(Role.ADMIN))
):
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be greater than 0",
        )
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100",
        )

    api_keys, total_count = AuthQueries.list_api_keys(
        username=user.username, page=page, limit=limit
    )
    pagination = PaginationInfo.from_query_params(page, limit, total_count)

    data = [
        ApiKeyInfo(api_key=key, created_at=created_at) for key, created_at in api_keys
    ]

    return {"api_keys": data, "pagination": pagination}


@router.get("/api-key/all")
def list_all_api_keys_route(
    page: int = 1, limit: int = 10, user=Depends(validate_role(Role.OWNER))
):
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be greater than 0",
        )
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100",
        )

    api_keys, total_count = AuthQueries.list_api_keys(page=page, limit=limit)
    pagination = PaginationInfo.from_query_params(page, limit, total_count)

    data = [
        ApiKeyWithUser(api_key=key, username=username, created_at=created_at)
        for key, username, created_at in api_keys
    ]

    return {"api_keys": data, "pagination": pagination}


@router.delete("/api-key", response_model=MessageResponse)
def revoke_api_key_route(
    api_key: str = Body(...),
    user=Depends(validate_role(Role.ADMIN)),
):
    if not AuthQueries.revoke_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to revoke API key",
        )
    return MessageResponse(message="API key revoked successfully")


@router.post("/api-key/validate", response_model=MessageResponse)
def validate_api_key_route(
    api_key: str = Depends(validate_api_key),
    user=Depends(validate_role(Role.ADMIN)),
):
    if not validate_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key",
        )
    return MessageResponse(message="API key is valid")
