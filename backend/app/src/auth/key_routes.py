"""Authentication and authorization routes for the FastAPI application.

Provides endpoints for login, logout, account management, and API key management.
"""

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.src.common import Role, User

from .models import APIKeyInfo, APIKeyTableDataResponse
from .validation import Validate

if TYPE_CHECKING:
    from .queries import AuthQueries, KeyListOptions
    from .security_manager import SecurityManager

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


async def _list_api_keys(
    user: User,
    options: KeyListOptions,
    auth_queries: AuthQueries,
) -> tuple[list[APIKeyInfo], int]:
    """Perform some checks and list API keys."""
    if options.page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be greater than 0",
        )
    if options.limit < 1 or options.limit > 100:  # noqa: PLR2004
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100",
        )

    if not options.user and user.role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can list all API keys",
        )

    api_keys, total_count = await auth_queries.list_api_keys(options)

    return [
        APIKeyInfo(api_key=key, username=username, created_at=created_at)
        for key, username, created_at in api_keys
    ], total_count


async def _revoke_api_key(
    api_key: str,
    user: User,
    auth_queries: AuthQueries,
) -> str:
    """Perform some checks and revoke an API key."""
    api_user = await auth_queries.get_user_by_api_key(api_key)

    if not api_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if not user.role.has_higher_permission(api_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot revoke this API key",
        )

    if not await auth_queries.revoke_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to delete this API key",
        )
    return "API key revoked successfully"


def configure_key_router(
    router: APIRouter,
    auth_queries: AuthQueries,
    security_manager: SecurityManager,
) -> APIRouter:
    """Configure the authentication router."""
    validate = Validate(auth_queries, security_manager)

    @router.put("/api-key")
    async def create_api_key_route(
        user: Annotated[User, Depends(validate.role(Role.ADMIN))],
    ) -> str:
        api_key = await auth_queries.generate_api_key(user)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create API key",
            )
        return api_key

    @router.get("/api-keys")
    async def list_api_keys_route(
        user: Annotated[User, Depends(validate.role(Role.ADMIN))],
        options: KeyListOptions,
    ) -> APIKeyTableDataResponse:
        items, total_count = await _list_api_keys(user, options, auth_queries)
        return APIKeyTableDataResponse.from_query_params(
            page=options.page,
            limit=options.limit,
            items=items,
            total_count=total_count,
        )

    @router.delete("/api-key")
    async def revoke_api_key_route(
        api_key: Annotated[str, Body()],
        user: Annotated[User, Depends(validate.role(Role.ADMIN))],
    ) -> str:
        return await _revoke_api_key(api_key, user, auth_queries)

    return router
