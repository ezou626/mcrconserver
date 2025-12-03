"""JWT authentication utilities."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from ..common.user import User, Role

# TODO: Move this into the utils file


class JWTAuth:
    def __init__(self):
        # For single-session applications, runtime key generation is simpler
        self.secret_key = os.urandom(128).hex()
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60 * 24 * 7  # 7 days

    def create_access_token(self, user: User) -> str:
        """Create a new JWT access token for the user."""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self.access_token_expire_minutes
        )

        payload = {
            "sub": user.username,
            "role": int(user.role),
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access_token",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> User:
        """Verify and decode a JWT token, returning the user."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check token type
            if payload.get("type") != "access_token":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            username: str = payload.get("sub")
            role_int: int = payload.get("role")

            if username is None or role_int is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return User(username=username, role=Role(role_int))

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # TODO: Refresh token on each use
    def refresh_token(self, token: str) -> str:
        """Create a new token from an existing valid token."""
        user = self.verify_token(token)
        return self.create_access_token(user)


# Global JWT auth instance
jwt_auth = JWTAuth()
