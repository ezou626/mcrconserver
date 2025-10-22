from datetime import datetime
import logging
import getpass

from bcrypt import checkpw, gensalt, hashpw

from .user import User
from .roles import Role

from .db_connection import get_db_connection

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("Auth helpers are being imported")

SPECIAL_CHARACTERS = "!@#$%^&*()-_=+[{]}"


def initialize_user_table():
    db = get_db_connection()

    # check if users table exists, if not create it
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT NOT NULL,
            salt TEXT NOT NULL,
            role INTEGER NOT NULL DEFAULT 2, -- 0: owner, 1: admin, 2: user
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    db.commit()

    # if no users exist, prompt to create an owner user

    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

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
    owner_user = create_account(username, owner_password, Role.OWNER)
    if not owner_user:
        print("Failed to create owner account. Exiting.")
        return
    print(f"Owner account '{owner_user.username}' created successfully.")


def initialize_keys_table():
    db = get_db_connection()
    # create api_keys table if it doesn't exist
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            api_key TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
        );
        """
    )
    db.commit()


def password_requirements(password: str) -> str | None:
    """
    Password requirements logic.
    """
    if len(password) < 8:
        return "Owner password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return "Owner password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return "Owner password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Owner password must contain at least one digit"
    if not any(c in SPECIAL_CHARACTERS for c in password):
        return (
            "Owner password must contain at least one special character in "
            + SPECIAL_CHARACTERS
        )
    return None


def check_password(username: str, password: str) -> User | None:
    """
    Check the password for the given username.

    Args:
        username (str): The username to check.
        password (str): The password to check.

    Returns:
        User | None: The User if the password is correct, None otherwise.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT hashed_password, role FROM users WHERE username = ?", (username,)
    )
    row = cursor.fetchone()
    if row is None:
        return None
    stored_hashed_password, role = row
    if checkpw(password.encode(), stored_hashed_password):
        return User(username, role=Role(int(role)))
    return None


def is_token_expired(unix_timestamp: int) -> bool:
    if unix_timestamp:
        datetime_from_unix = datetime.fromtimestamp(unix_timestamp)
        current_time = datetime.now()
        difference_in_minutes = (datetime_from_unix - current_time).total_seconds() / 60
        return difference_in_minutes <= 0

    return True


def create_account(username: str, password: str, role: Role) -> User | None:
    """
    Create a new user account with the given username, password, and role.
    """
    error = password_requirements(password)
    if error:
        print(error)
        return None

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
    if cursor.fetchone()[0] > 0:
        print("Username already exists")
        return None

    salt = gensalt()
    hashed_password = hashpw(password.encode(), salt)
    cursor.execute(
        "INSERT INTO users (username, hashed_password, salt, role) VALUES (?, ?, ?, ?)",
        (username, hashed_password, salt, role),
    )
    db.commit()
    return User(username, role)


def delete_account(username: str) -> int:
    """
    Delete the user account with the given username.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    db.commit()
    return cursor.rowcount


def change_password(username: str, new_password: str) -> str | None:
    """
    Change the password for the given username.

    Args:
        username (str): The username to change the password for.
        new_password (str): The new password.

    Returns:
        str | None: An error message if the password change failed, None otherwise.
    """
    error = password_requirements(new_password)
    if error:
        return error
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
    if cursor.fetchone()[0] == 0:
        return "Username does not exist"

    salt = gensalt()
    hashed_password = hashpw(new_password.encode(), salt)
    cursor.execute(
        "UPDATE users SET hashed_password = ?, salt = ? WHERE username = ?",
        (hashed_password, salt, username),
    )
    db.commit()
    return None
