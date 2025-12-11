"""Password and JWT utility functions.

Includes password requirement checks, JWT token creation and verification.
"""

import getpass
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.src.common import Role, User

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


@dataclass
class SecurityManager:
    """Manager for security configurations and validations.

    :param str secret_key: Secret key for JWT signing (generated if not provided)
    :param str algorithm: JWT signing algorithm
    :param int expire_minutes: Token expiration time in minutes
    :param int passphrase_min_length: Minimum length for passphrases
    """

    DEFAULT_JWT_ALGORITHM = "HS512"
    DEFAULT_TOKEN_EXPIRE_MINUTES = 60 * 24
    DEFAULT_PASSPHRASE_MIN_LENGTH = 20
    MINIMUM_JWT_SECRET_KEY_LENGTH = 32
    DEFAULT_API_KEY_LENGTH = 64

    secret_key: str | None = None
    algorithm: str = DEFAULT_JWT_ALGORITHM
    expire_minutes: int = DEFAULT_TOKEN_EXPIRE_MINUTES
    passphrase_min_length: int = DEFAULT_PASSPHRASE_MIN_LENGTH
    api_key_length: int = DEFAULT_API_KEY_LENGTH

    def __post_init__(self) -> None:
        """Generate secret key if not provided."""
        if (
            self.secret_key is None
            or len(self.secret_key) < self.MINIMUM_JWT_SECRET_KEY_LENGTH
        ):
            self.secret_key = os.urandom(64).hex()

    def validate_password(self, password: str) -> str | None:
        """Validate password against configured requirements (just length for now).

        :param str password: The password to validate
        :param SecurityConfig config: Password validation configuration
        :return: An error message if the password does not meet requirements,
        None otherwise
        """
        if len(password) >= self.passphrase_min_length:
            return None

        return f"Password must be at least {self.passphrase_min_length} characters long"

    def initialize_owner_account(self) -> tuple[str, str]:
        """Prompt the user to create the owner account if it does not exist in CLI.

        :param password_config: Password validation configuration to use
        :return: A tuple of (username, password) if the account was created,
        None otherwise
        """
        username = input("Please enter the owner username: ")
        owner_password = None
        while not owner_password:
            owner_password = getpass.getpass("Please enter the owner password: ")
            error = self.validate_password(owner_password)
            if error:
                LOGGER.error(error)
                owner_password = None
                continue
            owner_password_confirm = getpass.getpass(
                "Please re-enter the owner password: ",
            )
            if owner_password != owner_password_confirm:
                LOGGER.error("Passwords do not match. Please try again.")
                owner_password = None
                continue
        return username, owner_password

    def create_access_token(self, user: User) -> str:
        """Create a new JWT access token for the user.

        :param User user: The User object for whom to create the token
        :param SecurityConfig jwt_config: JWT configuration to use
        :return: A JWT access token as a string
        """
        expire = datetime.now(UTC) + timedelta(minutes=self.expire_minutes)

        payload = {
            "sub": user.username,
            "role": int(user.role),
            "exp": expire,
            "iat": datetime.now(UTC),
            "type": "access_token",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> User | None:
        """Verify and decode a JWT token, returning the user.

        :param token: The JWT token string to verify
        :param jwt_config: JWT configuration to use
        :return: The User object if the token is valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )

            if payload.get("type") != "access_token":
                return None

            username: str = payload.get("sub")
            role_int: int = payload.get("role")

            if username is None or role_int is None:
                return None

            return User(username=username, role=Role(role_int))

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
