from __future__ import annotations
from pydantic import BaseModel


class PaginationInfo(BaseModel):
    page: int
    limit: int
    total_count: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def from_query_params(
        cls, page: int, limit: int, total_count: int
    ) -> PaginationInfo:
        """Helper function to create pagination info from query parameters

        Args:
            page: Current page number
            limit: Number of items per page
            total_count: Total number of items

        Returns:
            PaginationInfo instance
        """
        total_pages = (total_count + limit - 1) // limit
        return cls(
            page=page,
            limit=limit,
            total_count=total_count,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class ApiKeyInfo(BaseModel):
    api_key: str
    created_at: str


class ApiKeyWithUser(ApiKeyInfo):
    username: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: int


class AccountInfo(BaseModel):
    username: str
    role: int


class MessageResponse(BaseModel):
    message: str
