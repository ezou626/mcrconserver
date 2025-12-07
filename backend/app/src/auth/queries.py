"""All queries related to authentication and API key management.

Using the AuthQueries class as a repository for
authentication-related queries.
"""

import secrets
import logging

import aiosqlite
from aiosqlite import Connection
from bcrypt import checkpw, gensalt, hashpw

from app.src.common import User, Role
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

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    @classmethod
    async def create(cls, db_path: str) -> "AuthQueries":
        """Create an AuthQueries instance with an aiosqlite connection.

        :param db_path: Path to the SQLite database file
        :type db_path: str
        :return: Configured AuthQueries instance
        :rtype: AuthQueries
        """
        connection = await aiosqlite.connect(db_path)
        return cls(connection)

    async def close(self) -> None:
        """Close the database connection.

        :return: None
        :rtype: None
        """
        await self.connection.close()

    async def initialize_tables(self) -> None:
        """Create users and api_keys tables if they do not exist.

        Creates the necessary database tables for authentication and API key management.
        This method should be called during application startup.
        """
        async with self.connection as db:
            try:
                await db.execute(AuthQueries.CREATE_USERS_TABLE)
                await db.execute(AuthQueries.CREATE_API_KEYS_TABLE)
                await db.commit()
            except Exception as e:
                await self.connection.rollback()
                LOGGER.error(f"Error initializing tables: {e}")

    async def count_users(self) -> int:
        """Return the number of users in the users table.

        :return: Number of users
        :rtype: int
        """
        async with self.connection as db:
            result = await db.execute(AuthQueries.COUNT_USERS)
            result = await result.fetchone()
        return result[0] if result else 0

    async def authenticate_user(self, username: str, password: str) -> User | None:
        """Retrieve user authentication info by username.

        :param username: The username of the user
        :type username: str
        :param password: The plaintext password to verify
        :type password: str
        :return: The User object if authentication is successful, None otherwise
        :rtype: User | None
        """
        async with self.connection as db:
            result = await db.execute(AuthQueries.GET_USER_AUTH_INFO, (username,))
            row = await result.fetchone()
            if row is None:
                return None
            stored_hashed_password, role = row
            if checkpw(password.encode(), stored_hashed_password):
                return User(username, role=Role(int(role)))
            return None

    async def create_account(self, user: User, password: str) -> str | None:
        """Create a new user account with the given username, password, and role.

        :param user: The User object containing username and role
        :type user: User
        :param password: The desired password
        :type password: str
        :return: An error message if creation failed, None otherwise
        :rtype: str | None
        """
        error = password_requirements(password)
        if error:
            return error

        async with self.connection as db:
            try:
                result = await db.execute(
                    AuthQueries.GET_USER_WITH_USERNAME, (user.username,)
                )
                existing_user = await result.fetchone()
                if existing_user is not None:
                    return "Username already exists"

                salt = gensalt()
                hashed_password = hashpw(password.encode(), salt)
                await db.execute(
                    AuthQueries.ADD_USER,
                    (user.username, hashed_password, salt, user.role),
                )
                await db.commit()
                return None
            except Exception as e:
                await db.rollback()
                LOGGER.error(f"Error creating account for {user.username}: {e}")
                return "Failed to create account"

    async def delete_account(self, username: str) -> int:
        """Delete the user account with the given username.

        :param username: The username of the account to delete
        :type username: str
        :return: Number of rows deleted
        :rtype: int
        """
        async with self.connection as db:
            try:
                result = await db.execute(AuthQueries.DELETE_USER, (username,))
                await db.commit()
                return result.rowcount if result else 0
            except Exception as e:
                await db.rollback()
                LOGGER.error(f"Error deleting account {username}: {e}")
                return 0

    async def change_password(self, username: str, new_password: str) -> str | None:
        """Change the password for the given username.

        :param username: The username to change the password for
        :type username: str
        :param new_password: The new password
        :type new_password: str
        :return: An error message if the password change failed, None otherwise
        :rtype: str | None
        """
        error = password_requirements(new_password)
        if error:
            return error

        async with self.connection as db:
            try:
                result = await db.execute(
                    AuthQueries.GET_USER_WITH_USERNAME, (username,)
                )
                user_exists = await result.fetchone()
                if user_exists is None:
                    return "Username does not exist"

                salt = gensalt()
                hashed_password = hashpw(new_password.encode(), salt)
                await db.execute(
                    AuthQueries.UPDATE_USER_PASSWORD,
                    (hashed_password, salt, username),
                )
                await db.commit()
                return None
            except Exception as e:
                await db.rollback()
                LOGGER.error(f"Error changing password for {username}: {e}")
                return "Failed to change password"

    async def generate_api_key(self, user: User) -> str | None:
        """Generate a secure API key for the given username.

        :param user: The User object to generate the API key for
        :type user: User
        :return: The generated API key, or None if generation failed
        :rtype: str | None
        """
        username = user.username
        api_key = secrets.token_urlsafe(API_KEY_LENGTH)

        async with self.connection as db:
            try:
                await db.execute(
                    "INSERT INTO api_keys (api_key, username) VALUES (?, ?)",
                    (api_key, username),
                )
                await db.commit()
                return api_key
            except Exception as e:
                await db.rollback()
                LOGGER.error(f"Error generating API key for {username}: {e}")
                return None

    async def revoke_api_key(self, api_key: str) -> int:
        """Revoke the given API key.

        :param api_key: The API key to revoke
        :type api_key: str
        :return: Number of rows deleted
        :rtype: int
        """
        async with self.connection as db:
            try:
                result = await db.execute(
                    "DELETE FROM api_keys WHERE api_key = ?", (api_key,)
                )
                await db.commit()
                return result.rowcount if result else 0
            except Exception as e:
                await db.rollback()
                LOGGER.error(f"Error revoking API key: {e}")
                return 0

    async def list_api_keys(
        self,
        username: str | None = None,
        page: int = 1,
        limit: int = 10,
        order_by: str = "created_at",
        order_desc: bool = True,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> tuple[list[tuple], int]:
        """List API keys with optional filtering and pagination.

        :param username: Filter by specific username. If None, returns all API keys
        :type username: str | None
        :param page: Page number for pagination (1-based)
        :type page: int
        :param limit: Number of results per page
        :type limit: int
        :param order_by: Field to order by ('created_at', 'username', 'api_key')
        :type order_by: str
        :param order_desc: Whether to order in descending order
        :type order_desc: bool
        :param created_after: Filter API keys created after this date (ISO format)
        :type created_after: str | None
        :param created_before: Filter API keys created before this date (ISO format)
        :type created_before: str | None
        :return: (api_keys, total_count) where api_keys is list of tuples.
                If username is provided: [(api_key, created_at), ...]
                If username is None: [(api_key, username, created_at), ...]
        :rtype: tuple[list[tuple], int]
        """
        async with self.connection as db:
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
            result = await db.execute(count_query, params)
            count_row = await result.fetchone()
            total_count = count_row[0] if count_row else 0

            offset = (page - 1) * limit

            if username is not None:
                select_fields = "api_key, created_at"
            else:
                select_fields = "api_key, username, created_at"

            query = f"SELECT {select_fields} FROM api_keys{where_clause} ORDER BY {order_by} {order_direction} LIMIT ? OFFSET ?"
            result = await db.execute(query, params + [limit, offset])
            rows = await result.fetchall()

            return [tuple(row) for row in rows], total_count

    async def get_user_by_api_key(self, api_key: str) -> User | None:
        """Get user by API key.

        :param api_key: The API key to look up
        :type api_key: str
        :return: The User object if API key is valid, None otherwise
        :rtype: User | None
        """
        async with self.connection as db:
            result = await db.execute(AuthQueries.GET_USER_BY_API_KEY, (api_key,))
            row = await result.fetchone()
            if not row:
                return None

            username = row[0]
            result = await db.execute(AuthQueries.GET_USER_WITH_USERNAME, (username,))
            role_row = await result.fetchone()
            if not role_row:
                return None

            return User(username, role=Role(int(role_row[0])))
