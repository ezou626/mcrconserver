"""FastAPI dependency validators for authentication and authorization."""

import logging
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.src.common import Role, User

    from .queries import AuthQueries
    from .security_manager import SecurityManager


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)
bearer_scheme = HTTPBearer(auto_error=True)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class Validate:
    """Holds validator dependencies for FastAPI authentication/authorization."""

    def __init__(
        self,
        auth_queries: AuthQueries,
        security_manager: SecurityManager,
    ) -> None:
        """Create a new validator instance.

        :param auth_queries: Database connector
        :param security_manager: JWT security manager
        """
        self.auth_queries = auth_queries
        self.security_manager = security_manager

    async def api_key(
        self,
        api_key: str = Security(api_key_header),
    ) -> User:
        """Validate an API key using the injected AuthQueries."""
        user = await self.auth_queries.get_user_by_api_key(api_key)
        if not user:
            LOGGER.debug("API key validation failed for key: %s", api_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        LOGGER.debug("API key validated for user: %s", user.username)
        return user

    def jwt_token(
        self,
        credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),  # noqa: B008
    ) -> User:
        """Validate JWT access token using the injected SecurityManager."""
        token = credentials.credentials
        user = self.security_manager.verify_token(token)

        if not user:
            LOGGER.debug("JWT token validation failed for token: %s", token)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        LOGGER.debug("JWT token validated for user: %s", user.username)
        return user

    def role(self, required_role: Role) -> Callable[..., User]:
        """Return a role-based dependency validator."""

        def validator(user: User = Depends(self.jwt_token)) -> User:  # noqa: B008
            if not user.role.check_permission(required_role):
                LOGGER.debug("Role validation failed for user: %s", user.username)
                raise HTTPException(status_code=403, detail="Forbidden")
            LOGGER.debug("Role validated for user: %s", user.username)
            return user

        return validator
