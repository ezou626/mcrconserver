"""All queries related to authentication and API key management.

Using the AuthQueries class as a repository for
authentication-related queries.
"""

import secrets
import logging
from bcrypt import checkpw, gensalt, hashpw

from app.common.user import User, Role
from .db_connection import get_db_connection, set_db_path
from .utils import password_requirements

API_KEY_LENGTH = 128

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class AuthQueries:
    """Repository for authentication-related queries."""

    CREATE_USERS_TABLE = """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT NOT NULL,
            salt TEXT NOT NULL,
            role INTEGER NOT NULL DEFAULT 2, -- 0: owner, 1: admin, 2: user
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

    CREATE_API_KEYS_TABLE = """
        CREATE TABLE IF NOT EXISTS api_keys (
            api_key TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
        );
        """

    COUNT_USERS = """SELECT COUNT(*) FROM users;"""

    GET_USER_AUTH_INFO = """
        SELECT hashed_password, role FROM users WHERE username = ?;
        """

    GET_USER_WITH_USERNAME = """
        SELECT role FROM users WHERE username = ?
        """

    GET_USER_BY_API_KEY = """
        SELECT username FROM api_keys WHERE api_key = ?
        """

    ADD_USER = """
        INSERT INTO users (username, hashed_password, salt, role) VALUES (?, ?, ?, ?)
        """

    UPDATE_USER_PASSWORD = """
        UPDATE users SET hashed_password = ?, salt = ? WHERE username = ?
        """

    DELETE_USER = """
        DELETE FROM users WHERE username = ?;
        """

    @staticmethod
    def initialize_tables(db_path: str) -> None:
        """Create users and api_keys tables if they do not exist.

        Args:
            db_path (str): Path to the SQLite database file.
        """
        set_db_path(db_path)
        db = get_db_connection()
        db.execute(AuthQueries.CREATE_USERS_TABLE)
        db.execute(AuthQueries.CREATE_API_KEYS_TABLE)
        db.commit()

    @staticmethod
    def count_users() -> int:
        """Return the number of users in the users table.

        Returns:
            int: Number of users."""
        db = get_db_connection()
        result = db.execute(AuthQueries.COUNT_USERS).fetchone()
        return result[0] if result else 0

    @staticmethod
    def authenticate_user(username: str, password: str) -> User | None:
        """Retrieve user authentication info by username.

        Args:
            username (str): The username of the user.
            password (str): The plaintext password to verify.

        Returns:
            User | None: The User object if authentication is successful, None otherwise.
        """
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(AuthQueries.GET_USER_AUTH_INFO, (username,))
        row = cursor.fetchone()
        if row is None:
            return None
        stored_hashed_password, role = row
        if checkpw(password.encode(), stored_hashed_password):
            return User(username, role=Role(int(role)))
        return None

    @staticmethod
    def create_account(user: User, password: str) -> str | None:
        """
        Create a new user account with the given username, password, and role.

        Args:
            username (str): The desired username.
            password (str): The desired password.
            role (Role): The role of the user.

        Returns:
            User | None: The created User object, or None if creation failed.
            str | None: An error message if creation failed, None otherwise.
        """
        error = password_requirements(password)
        if error:
            return error

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(AuthQueries.GET_USER_WITH_USERNAME, (user.username,))
        if cursor.fetchone() is not None:
            return "Username already exists"

        salt = gensalt()
        hashed_password = hashpw(password.encode(), salt)
        cursor.execute(
            AuthQueries.ADD_USER,
            (user.username, hashed_password, salt, user.role),
        )
        db.commit()
        return None

    @staticmethod
    def delete_account(username: str) -> int:
        """
        Delete the user account with the given username.

        Args:
            username (str): The username of the account to delete.
        """
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(AuthQueries.DELETE_USER, (username,))
        db.commit()
        return cursor.rowcount

    @staticmethod
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
        cursor.execute(AuthQueries.GET_USER_WITH_USERNAME, (username,))
        if cursor.fetchone() is None:
            return "Username does not exist"

        salt = gensalt()
        hashed_password = hashpw(new_password.encode(), salt)
        cursor.execute(
            AuthQueries.UPDATE_USER_PASSWORD,
            (hashed_password, salt, username),
        )
        db.commit()
        return None

    @staticmethod
    def generate_api_key(user: User) -> str | None:
        """
        Generate a secure API key for the given username.

        Args:
            user (User): The User object to generate the API key for.

        Returns:
            str | None: The generated API key, or None if generation failed.
        """
        username = user.username
        api_key = secrets.token_urlsafe(API_KEY_LENGTH)

        try:
            db = get_db_connection()
            db.execute(
                "INSERT INTO api_keys (api_key, username) VALUES (?, ?)",
                (api_key, username),
            )
            db.commit()
        except Exception as e:
            LOGGER.error(f"Error generating API key: {e}")
            return None

        return api_key

    @staticmethod
    def revoke_api_key(api_key: str):
        """
        Revoke the given API key.
        """
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM api_keys WHERE api_key = ?", (api_key,))
        db.commit()
        return cursor.rowcount

    # TODO: Consider combining list_api_keys and list_all_api_keys into one method with optional username parameter
    # TODO: More ordering and filtering options

    @staticmethod
    def list_api_keys(
        user: User, page: int = 1, limit: int = 10
    ) -> tuple[list[tuple[str, str]], int]:
        """
        List API keys for the given username with pagination.
        Returns tuple of (api_keys, total_count)
        """
        username = user.username

        db = get_db_connection()
        cursor = db.cursor()

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM api_keys WHERE username = ?", (username,))
        total_count = cursor.fetchone()[0]

        # Get paginated results
        offset = (page - 1) * limit
        cursor.execute(
            "SELECT api_key, created_at FROM api_keys WHERE username = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (username, limit, offset),
        )
        rows = cursor.fetchall()
        return [(row[0], row[1]) for row in rows], total_count

    @staticmethod
    def list_all_api_keys(
        page: int = 1, limit: int = 10
    ) -> tuple[list[tuple[str, str, str]], int]:
        """
        List all API keys for all users with pagination.
        Returns tuple of (api_keys, total_count)
        """
        db = get_db_connection()
        cursor = db.cursor()

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM api_keys")
        total_count = cursor.fetchone()[0]

        # Get paginated results
        offset = (page - 1) * limit
        cursor.execute(
            "SELECT api_key, username, created_at FROM api_keys ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [(row[0], row[1], row[2]) for row in rows], total_count

    @staticmethod
    def get_user_by_api_key(api_key: str) -> User | None:
        """
        Get user by API key.

        Args:
            api_key (str): The API key to look up.

        Returns:
            User | None: The User object if API key is valid, None otherwise.
        """
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(AuthQueries.GET_USER_BY_API_KEY, (api_key,))
        row = cursor.fetchone()
        if not row:
            return None

        username = row[0]
        cursor.execute(AuthQueries.GET_USER_WITH_USERNAME, (username,))
        role_row = cursor.fetchone()
        if not role_row:
            return None

        return User(username, role=Role(int(role_row[0])))
