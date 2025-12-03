"""All queries related to authentication and API key management.

Using the AuthQueries class as a repository for
authentication-related queries.
"""

from bcrypt import checkpw, gensalt, hashpw

from app.auth.user import User, Role
from .db_connection import get_db_connection, set_db_path
from .utils import password_requirements


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

    GET_USERS_WITH_USERNAME = """
        SELECT role FROM users WHERE username = ?
        """

    ADD_USER = """
    INSERT INTO users (username, hashed_password, salt, role) VALUES (?, ?, ?, ?)
    """

    @staticmethod
    def initialize_tables(db_path: str) -> None:
        """Create users and api_keys tables if they do not exist."""
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
    def create_account(
        username: str, password: str, role: Role
    ) -> tuple[User | None, str | None]:
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
            return None, error

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(AuthQueries.GET_USERS_WITH_USERNAME, (username,))
        if cursor.fetchone() is not None:
            return None, "Username already exists"

        salt = gensalt()
        hashed_password = hashpw(password.encode(), salt)
        cursor.execute(
            AuthQueries.ADD_USER,
            (username, hashed_password, salt, role),
        )
        db.commit()
        return User(username, role), None
