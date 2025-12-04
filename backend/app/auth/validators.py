from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from app.common.user import User, Role
from .db_connection import get_db_connection

from .utils import verify_token

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
    user = verify_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def validate_role(required_role: Role):
    def validate_role_inner(user: User = Depends(validate_jwt_token)) -> User:
        if not user.role.check_permission(required_role):
            raise HTTPException(status_code=403, detail="Forbidden")

        return user

    return validate_role_inner
