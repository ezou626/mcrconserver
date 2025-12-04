"""Password and JWT utility functions.

Includes password requirement checks, JWT token creation and verification.
"""

import logging
import getpass
import os
import jwt

from datetime import timezone, datetime, timedelta

from app.common.user import Role, User

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

SPECIAL_CHARACTERS = "!@#$%^&*()-_=+[{]}"

RULES = [
    (
        lambda x: not any(c.isupper() for c in x),
        "at least one uppercase letter",
    ),
    (
        lambda x: not any(c.islower() for c in x),
        "at least one lowercase letter",
    ),
    (lambda x: not any(c.isdigit() for c in x), "at least one digit"),
    (
        lambda x: not any(c in SPECIAL_CHARACTERS for c in x),
        f"at least one special character in {SPECIAL_CHARACTERS}",
    ),
]

JWT_SECRET_KEY = os.urandom(64).hex()
ALGORITHM = "HS512"
EXPIRE_TIME = 60 * 24


def initialize_owner_account() -> tuple[str, str] | None:
    """
    Prompt the user to create the owner account if it does not exist.

    Returns:
        A tuple of (username, password) if the account was created, None otherwise.
    """
    username = input("Please enter the owner username: ")
    owner_password = None
    while not owner_password:
        owner_password = getpass.getpass("Please enter the owner password: ")
        error = password_requirements(owner_password)
        if error:
            print(error)
            owner_password = None
            continue
        owner_password_confirm = getpass.getpass("Please re-enter the owner password: ")
        if owner_password != owner_password_confirm:
            print("Passwords do not match. Please try again.")
            owner_password = None
            continue
    return username, owner_password


def password_requirements(password: str) -> str | None:
    """
    Password requirements logic.

    Either the password is a passphrase (longer than 20 characters) or it meets the following criteria:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character from SPECIAL_CHARACTERS

    Args:
        password: The password to validate.

    Returns:
        An error message if the password does not meet the requirements, None otherwise.
    """
    if len(password) > 20:  # passphrases are allowed
        return None

    for rule, error_message in RULES:
        if rule(password):
            return f"Owner password must be 20+ characters or contain {error_message}"

    return None


def create_access_token(user: User) -> str:
    """Create a new JWT access token for the user.

    Args:
        user: The User object for whom to create the token.

    Returns:
        A JWT access token as a string."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_TIME)

    payload = {
        "sub": user.username,
        "role": int(user.role),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access_token",
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> User | None:
    """Verify and decode a JWT token, returning the user.

    Args:
        token: The JWT token string to verify.

    Returns:
        The User object if the token is valid, None otherwise."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])

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


def refresh_token(self, token: str) -> str | None:
    """Create a new token from an existing valid token.

    Args:
        token: The existing valid JWT token string.

    Returns:
        A new JWT access token as a string."""
    user = verify_token(token)
    if user is None:
        return None
    return create_access_token(user)
