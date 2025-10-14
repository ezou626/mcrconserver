from datetime import datetime
import logging
import getpass

from bcrypt import checkpw, gensalt, hashpw

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
            role TEXT
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
        if not is_password_valid(owner_password):
            owner_password = None
            continue
    owner_password_confirm = getpass.getpass("Please re-enter the owner password: ")
    if owner_password != owner_password_confirm:
        return None
    create_account(username, owner_password, "owner")
    db.commit()


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


def is_password_valid(owner_password: str) -> bool:
    """
    Password requirements logic.
    """
    if len(owner_password) < 8:
        print("Owner password must be at least 8 characters long")
        return False
    if not any(c.isupper() for c in owner_password):
        print("Owner password must contain at least one uppercase letter")
        return False
    if not any(c.islower() for c in owner_password):
        print("Owner password must contain at least one lowercase letter")
        return False
    if not any(c.isdigit() for c in owner_password):
        print("Owner password must contain at least one digit")
        return False
    if not any(c in SPECIAL_CHARACTERS for c in owner_password):
        print(
            "Owner password must contain at least one special character in "
            + SPECIAL_CHARACTERS
        )
        return False
    return True


def check_password(username: str, password: str) -> str | None:
    """
    Check the password for the given username.

    Args:
        username (str): The username to check.
        password (str): The password to check.

    Returns:
        str | None: The role of the user if the password is correct, None otherwise.
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
        return role
    return None


def is_token_expired(unix_timestamp: int) -> bool:
    if unix_timestamp:
        datetime_from_unix = datetime.fromtimestamp(unix_timestamp)
        current_time = datetime.now()
        difference_in_minutes = (datetime_from_unix - current_time).total_seconds() / 60
        return difference_in_minutes <= 0

    return True


def create_account(username: str, password: str, role: str) -> bool:
    """
    Create a new user account with the given username, password, and role.
    """
    if not is_password_valid(password):
        print(
            "Password must be at least 8 characters long and contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character"
        )
        return False

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
    if cursor.fetchone()[0] > 0:
        print("Username already exists")
        return False

    salt = gensalt()
    hashed_password = hashpw(password.encode(), salt)
    cursor.execute(
        "INSERT INTO users (username, hashed_password, salt, role) VALUES (?, ?, ?, ?)",
        (username, hashed_password, salt, role),
    )
    db.commit()
    return True


def delete_account(username: str) -> bool:
    """
    Delete the user account with the given username.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    db.commit()
    return cursor.rowcount > 0


def change_password(username: str, new_password: str) -> str | None:
    """
    Change the password for the given username.
    """
    if not is_password_valid(new_password):
        return (
            "Password must be at least 8 characters long and contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character"
        )

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
