import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from app.common.user import User, Role

from .db_connection import get_db_connection
from .jwt_auth import jwt_auth

from .queries import AuthQueries

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("Auth router is being imported")

router = APIRouter()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)
bearer_scheme = HTTPBearer(auto_error=True)


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


def validate_jwt_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> User:
    """
    Validate JWT token and return the associated User.

    Raises:
        HTTPException with 401 status if the token is invalid.
    """
    return jwt_auth.verify_token(credentials.credentials)


def validate_role(required_role: Role):
    def validate_role_inner(user: User = Depends(validate_jwt_token)) -> User:
        if not user.role.check_permission(required_role):
            # Use 403 for forbidden access instead of 404
            raise HTTPException(status_code=403, detail="Forbidden")

        return user

    return validate_role_inner


@router.post("/login")
def login(
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
):
    user = AuthQueries.authenticate_user(username, password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Generate JWT token
    access_token = jwt_auth.create_access_token(user)

    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": int(user.role),
    }


@router.post("/refresh")
def refresh_token(user: User = Depends(validate_jwt_token)):
    """
    Refresh the JWT token for authenticated user.
    """
    access_token = jwt_auth.create_access_token(user)
    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout():
    """
    Logout endpoint. With JWT, logout is handled client-side by discarding the token.
    """
    return {"success": True, "message": "Logout successful"}


@router.get("/account")
def get_account_info(user: User = Depends(validate_jwt_token)):
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
    new_user = User(username, role=role)
    error = AuthQueries.create_account(new_user, password)
    if error:
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
    if not AuthQueries.delete_account(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete account",
        )
    return {"success": True, "message": "Account deleted successfully"}


@router.patch("/account/password")
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
    return {"success": True, "message": "Password changed successfully"}


@router.put("/api-key")
def create_api_key_route(user=Depends(validate_role(Role.ADMIN))):
    api_key = AuthQueries.generate_api_key(user)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create API key",
        )
    return {"success": True, "api_key": api_key}


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

    api_keys, total_count = AuthQueries.list_api_keys(user, page, limit)
    total_pages = (total_count + limit - 1) // limit  # Ceiling division

    return {
        "success": True,
        "api_keys": [
            {"api_key": key, "created_at": created_at} for key, created_at in api_keys
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


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

    api_keys, total_count = AuthQueries.list_all_api_keys(page, limit)
    total_pages = (total_count + limit - 1) // limit  # Ceiling division

    return {
        "success": True,
        "api_keys": [
            {"api_key": key, "username": username, "created_at": created_at}
            for key, username, created_at in api_keys
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


@router.delete("/api-key")
def revoke_api_key_route(
    api_key: Annotated[str, Form(...)],
    user=Depends(validate_role(Role.ADMIN)),
):
    if not AuthQueries.revoke_api_key(api_key):
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
