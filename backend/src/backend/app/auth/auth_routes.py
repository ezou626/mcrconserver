"""Authentication and authorization routes for the FastAPI application.

Provides endpoints for login, logout, account management, and API key management.
"""

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, status

from backend.common import Role, User

from .models import LoginResponse, UserResponse

if TYPE_CHECKING:
    from .queries import AuthQueries
    from .security_manager import SecurityManager
    from .validation import Validate

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


async def _login(
    auth_queries: AuthQueries,
    security_manager: SecurityManager,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> LoginResponse:
    user = await auth_queries.authenticate_user(username, password)

    if not user:
        LOGGER.debug("Failed login attempt for username: %s", username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = security_manager.create_access_token(user)
    LOGGER.debug("User %s logged in successfully", username)
    return LoginResponse(
        access_token=access_token,
        user=UserResponse.from_user(user),
    )


async def _create_account(
    auth_queries: AuthQueries,
    username: str,
    password: str,
    role: int,
    owner: User,
) -> UserResponse:
    """For creating accounts of arbitrary users.

    Only 'owner' can create new accounts.
    """
    if username == owner.username:
        LOGGER.debug(
            "Owner %s attempted to create account with same name",
            owner.username,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create account with same name as own",
        )
    new_user = User(username, role=Role(role))
    LOGGER.debug("Creating account for user: %s with role: %s", username, role)
    error = await auth_queries.create_account(new_user, password)
    if error:
        LOGGER.debug(
            "Failed to create account for user: %s, error: %s",
            username,
            error,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    LOGGER.debug("Account created successfully for user: %s", username)
    return UserResponse.from_user(new_user)


async def _delete_account(
    auth_queries: AuthQueries,
    username: str,
    owner: User,
) -> str:
    """For deleting accounts of arbitrary users by the owner, not self-deletion."""
    if username == owner.username:
        LOGGER.debug("Owner %s attempted to delete own account", owner.username)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete own account",
        )
    if not await auth_queries.delete_account(username):
        LOGGER.debug("Failed to delete account for user: %s", username)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete account",
        )
    LOGGER.debug("Account deleted successfully for user: %s", username)
    return "Success"


async def _change_password(
    auth_queries: AuthQueries,
    new_password: str,
    user: User,
) -> str:
    error = await auth_queries.change_password(user.username, new_password)

    if error:
        LOGGER.debug(
            "Failed to change password for user: %s, error: %s",
            user.username,
            error,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    LOGGER.debug("Password changed successfully for user: %s", user.username)
    return "Password changed successfully"


def configure_auth_router(
    router: APIRouter,
    validate: Validate,
) -> APIRouter:
    """Configure the authentication router.

     :param router: The APIRouter to configure
    :param auth_queries: The AuthQueries instance for database operations
    :param security_manager: The SecurityManager instance for JWT operations
    :return: The configured APIRouter
    """
    auth_queries = validate.auth_queries
    security_manager = auth_queries.security_manager

    @router.post("/login", response_model=LoginResponse)
    async def login(
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ) -> LoginResponse:
        return await _login(auth_queries, security_manager, username, password)

    @router.post("/logout")
    def logout(
        user: Annotated[User, Depends(validate.jwt_token)],
    ) -> str:
        """With JWT, logout is handled client-side by discarding the token."""
        LOGGER.debug("User %s logged out", user.username)
        return "Success"

    @router.get("/account", response_model=UserResponse)
    def get_account_info(
        user: Annotated[User, Depends(validate.jwt_token)],
    ) -> UserResponse:
        LOGGER.debug("Retrieved account info for user: %s", user.username)
        return UserResponse.from_user(user)

    @router.put("/account")
    async def create_account_route(
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        role: Annotated[int, Form()],
        owner: Annotated[User, Depends(validate.role(Role.OWNER))],
    ) -> UserResponse:
        return await _create_account(auth_queries, username, password, role, owner)

    @router.delete("/account")
    async def delete_account_route(
        username: Annotated[str, Form(...)],
        owner: Annotated[User, Depends(validate.role(Role.OWNER))],
    ) -> str:
        return await _delete_account(auth_queries, username, owner)

    @router.patch("/account/password")
    async def change_password_route(
        new_password: Annotated[str, Form(...)],
        user: Annotated[User, Depends(validate.jwt_token)],
    ) -> str:
        return await _change_password(auth_queries, new_password, user)

    return router
