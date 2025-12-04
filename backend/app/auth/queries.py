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
        try:
            db.execute(AuthQueries.CREATE_USERS_TABLE)
            db.execute(AuthQueries.CREATE_API_KEYS_TABLE)
            db.commit()
        except Exception as e:
            db.rollback()
            LOGGER.error(f"Error initializing tables: {e}")
            raise

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
        try:
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
        except Exception as e:
            db.rollback()
            LOGGER.error(f"Error creating account for {user.username}: {e}")
            return "Failed to create account"

    @staticmethod
    def delete_account(username: str) -> int:
        """
        Delete the user account with the given username.

        Args:
            username (str): The username of the account to delete.
        """
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute(AuthQueries.DELETE_USER, (username,))
            db.commit()
            return cursor.rowcount
        except Exception as e:
            db.rollback()
            LOGGER.error(f"Error deleting account {username}: {e}")
            return 0

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
        try:
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
        except Exception as e:
            db.rollback()
            LOGGER.error(f"Error changing password for {username}: {e}")
            return "Failed to change password"

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

        db = get_db_connection()
        try:
            db.execute(
                "INSERT INTO api_keys (api_key, username) VALUES (?, ?)",
                (api_key, username),
            )
            db.commit()
            return api_key
        except Exception as e:
            db.rollback()
            LOGGER.error(f"Error generating API key for {username}: {e}")
            return None

    @staticmethod
    def revoke_api_key(api_key: str):
        """
        Revoke the given API key.
        """
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute("DELETE FROM api_keys WHERE api_key = ?", (api_key,))
            db.commit()
            return cursor.rowcount
        except Exception as e:
            db.rollback()
            LOGGER.error(f"Error revoking API key: {e}")
            return 0

    @staticmethod
    def list_api_keys(
        username: str | None = None,
        page: int = 1,
        limit: int = 10,
        order_by: str = "created_at",
        order_desc: bool = True,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> tuple[list[tuple], int]:
        """
        List API keys with optional filtering and pagination.

        Args:
            username (str, optional): Filter by specific username. If None, returns all API keys.
            page (int): Page number for pagination (1-based).
            limit (int): Number of results per page.
            order_by (str): Field to order by ('created_at', 'username', 'api_key').
            order_desc (bool): Whether to order in descending order.
            created_after (str, optional): Filter API keys created after this date (ISO format).
            created_before (str, optional): Filter API keys created before this date (ISO format).

        Returns:
            tuple: (api_keys, total_count) where api_keys is list of tuples.
                  If username is provided: [(api_key, created_at), ...]
                  If username is None: [(api_key, username, created_at), ...]
        """
        db = get_db_connection()
        cursor = db.cursor()

        # Build WHERE clause
        where_conditions = []
        params = []

        if username is not None:
            where_conditions.append("username = ?")
            params.append(username)

        if created_after is not None:
            where_conditions.append("created_at > ?")
            params.append(created_after)

        if created_before is not None:
            where_conditions.append("created_at < ?")
            params.append(created_before)

        where_clause = (
            " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        )

        # Validate order_by field
        valid_order_fields = {"created_at", "username", "api_key"}
        if order_by not in valid_order_fields:
            order_by = "created_at"

        order_direction = "DESC" if order_desc else "ASC"

        # Get total count
        count_query = f"SELECT COUNT(*) FROM api_keys{where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Get paginated results
        offset = (page - 1) * limit

        if username is not None:
            # Return format: (api_key, created_at)
            select_fields = "api_key, created_at"
        else:
            # Return format: (api_key, username, created_at)
            select_fields = "api_key, username, created_at"

        query = f"SELECT {select_fields} FROM api_keys{where_clause} ORDER BY {order_by} {order_direction} LIMIT ? OFFSET ?"
        cursor.execute(query, params + [limit, offset])
        rows = cursor.fetchall()

        return [tuple(row) for row in rows], total_count

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
