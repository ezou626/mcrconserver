from pydantic import BaseModel


class PaginationInfo(BaseModel):
    page: int
    limit: int
    total_count: int
    total_pages: int
    has_next: bool
    has_prev: bool


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
