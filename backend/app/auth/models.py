"""Models for auth-related responses."""

from pydantic import BaseModel

from app.common import Role, UserBase


class UserResponse(UserBase, BaseModel):
    """Data structure representing a user.

    :param str username: The username of the user
    :param int role: The role of the user
    """

    username: str
    role: Role

    @classmethod
    def from_user(cls, user: UserBase) -> UserResponse:
        """Create UserResponse from UserBase.

        :param user: UserBase instance
        :return: UserResponse instance
        """
        return UserResponse(username=user.username, role=user.role)


class APIKeyTableDataResponse(BaseModel):
    """Metadata for the API keys table paged responses.

    :param page: Current page number
    :param items: List of API keys on the current page
    :param total_count: Total number of items
    :param total_pages: Total number of pages
    """

    page: int
    items: list[APIKeyInfo]
    total_count: int
    total_pages: int

    @classmethod
    def from_query_params(
        cls,
        page: int,
        limit: int,
        items: list[APIKeyInfo],
        total_count: int,
    ) -> APIKeyTableDataResponse:
        """Create pagination info from query parameters.

        :param page: Current page number
        :param limit: Number of items per page
        :param items: List of API keys on the current page
        :param total_count: Total number of items
        :return: APIKeyTableDataResponse instance
        """
        total_pages = (total_count + limit - 1) // limit
        return cls(
            page=page,
            items=items,
            total_count=total_count,
            total_pages=total_pages,
        )


class APIKeyInfo(BaseModel):
    """Individual API key information.

    :param api_key: The API key string
    :param created_at: The creation timestamp of the API key
    :param username: The username of the user who owns the API key
    """

    api_key: str
    created_at: str
    username: str


class LoginResponse(BaseModel):
    """Response model for login requests.

    :param access_token: The JWT access token
    :param user: The authenticated user information
    """

    access_token: str
    user: UserResponse
