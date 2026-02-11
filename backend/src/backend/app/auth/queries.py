"""Authentication and API key management database utilities.

Using the AuthQueries class as a repository for
authentication-related queries.
"""

import logging
import secrets
from enum import StrEnum
from typing import TYPE_CHECKING

import aiosqlite
from aiosqlite import Connection
from bcrypt import checkpw, gensalt, hashpw
from pydantic import BaseModel

from backend.common import Role, User

if TYPE_CHECKING:
    from datetime import datetime

    from .security_manager import SecurityManager

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class APIKeyOrderBy(StrEnum):
    """Fields to order API key listings by."""

    CREATED_AT = "created_at"
    USERNAME = "username"
    API_KEY = "api_key"


class KeyListOptions(BaseModel):
    """Options for listing API keys.

    :param user: Filter by specific user. If None, returns all API keys
    :param page: Page number for pagination (1-based)
    :param limit: Number of results per page
    :param order_by: Field to order by
    :param order_desc: Whether to order in descending order
    :param created_after: Filter API keys created after this date (ISO format)
    :param created_before: Filter API keys created before this date (ISO format)
    """

    user: User | None = None
    page: int = 1
    limit: int = 10
    order_by: APIKeyOrderBy | None = APIKeyOrderBy.CREATED_AT
    order_desc: bool = True
    created_after: datetime | None = None
    created_before: datetime | None = None


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
        """  # noqa: S105

    DELETE_USER = """
        DELETE FROM users WHERE username = ?;
        """

    def __init__(
        self,
        connection: Connection,
        security_manager: SecurityManager,
    ) -> None:
        """Create an AuthQueries instance.

        :param connection: Database connection
        :param security_manager: Security configuration manager
        """
        self.connection = connection
        self.security_manager = security_manager

    @classmethod
    async def create(
        cls,
        db_path: str,
        security_manager: SecurityManager,
    ) -> AuthQueries:
        """Create an AuthQueries instance with an aiosqlite connection.

        :param db_path: Path to the SQLite database file
        :param security_manager: Security configuration manager
        :return: Configured AuthQueries instance
        """
        connection = await aiosqlite.connect(db_path)
        return cls(connection, security_manager)

    async def close(self) -> None:
        """Close the database connection."""
        await self.connection.close()

    async def initialize_tables(
        self,
        owner_credentials: tuple[str, str] | None = None,
    ) -> None:
        """Create users and api_keys tables if they do not exist.

        Creates the necessary database tables for authentication and API key management.
        This method should be called during application startup.

        :param owner_credentials: Optional (username, password) tuple for seeding the
            owner account. If the database has no users and credentials are provided,
            the owner account is created automatically. If no credentials are provided
            and the database has no users, a warning is logged.
        """
        async with self.connection as db:
            try:
                await db.execute(AuthQueries.CREATE_USERS_TABLE)
                await db.execute(AuthQueries.CREATE_API_KEYS_TABLE)

                # setup owner account if no users exist
                if await self.count_users() != 0:
                    await db.commit()
                    return

                if owner_credentials is None:
                    LOGGER.warning(
                        "No users found in database and no owner credentials "
                        "provided. The server will start without an owner account.",
                    )
                    await db.commit()
                    return

                username, password = owner_credentials
                salt = gensalt()
                hashed_password = hashpw(password.encode(), salt)
                await db.execute(
                    AuthQueries.ADD_USER,
                    (username, hashed_password, salt, Role.OWNER),
                )
                LOGGER.info(
                    "No users found in database; created default owner account "
                    "with username '%s'",
                    username,
                )

                await db.commit()
            except Exception:
                await db.rollback()
                LOGGER.exception("Error initializing tables")

    async def count_users(self) -> int:
        """Return the number of users in the users table.

        :return: Number of users
        """
        async with self.connection as db:
            result = await db.execute(AuthQueries.COUNT_USERS)
            result = await result.fetchone()
        return result[0] if result else 0

    async def authenticate_user(self, username: str, password: str) -> User | None:
        """Retrieve user authentication info by username.

        :param username: The username of the user
        :param password: The plaintext password to verify
        :return: The User object if authentication is successful, None otherwise
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
        :param password: The desired password
        :return: An error message if creation failed, None otherwise
        """
        error = self.security_manager.validate_password(password)
        if error:
            return error

        async with self.connection as db:
            try:
                result = await db.execute(
                    AuthQueries.GET_USER_WITH_USERNAME,
                    (user.username,),
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
            except Exception:
                await db.rollback()
                LOGGER.exception("Error creating account for %s", user.username)
                return "Failed to create account"

    async def delete_account(self, username: str) -> int:
        """Delete the user account with the given username.

        :param username: The username of the account to delete
        :return: Number of rows deleted
        """
        async with self.connection as db:
            try:
                result = await db.execute(AuthQueries.DELETE_USER, (username,))
                await db.commit()
            except Exception:
                await db.rollback()
                LOGGER.exception("Error deleting account %s", username)
                return 0
            else:
                return result.rowcount if result else 0

    async def change_password(self, username: str, new_password: str) -> str | None:
        """Change the password for the given username.

        :param username: The username to change the password for
        :param new_password: The new password
        :return: An error message if the password change failed, None otherwise
        """
        error = self.security_manager.validate_password(new_password)
        if error:
            return error

        async with self.connection as db:
            try:
                result = await db.execute(
                    AuthQueries.GET_USER_WITH_USERNAME,
                    (username,),
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
            except Exception:
                await db.rollback()
                LOGGER.exception("Error changing password for %s", username)
                return "Failed to change password"

    async def generate_api_key(self, user: User) -> str | None:
        """Generate a secure API key for the given username.

        :param user: The User object to generate the API key for
        :return: The generated API key as a string, or None if generation failed
        """
        username = user.username
        api_key = secrets.token_urlsafe(self.security_manager.api_key_length)

        async with self.connection as db:
            try:
                await db.execute(
                    "INSERT INTO api_keys (api_key, username) VALUES (?, ?)",
                    (api_key, username),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                LOGGER.exception("Error generating API key for %s", username)
                return None
            else:
                return api_key

    async def revoke_api_key(self, api_key: str) -> int:
        """Revoke the given API key.

        :param api_key: The API key to revoke
        :return: Number of rows deleted
        """
        async with self.connection as db:
            try:
                result = await db.execute(
                    "DELETE FROM api_keys WHERE api_key = ?",
                    (api_key,),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                LOGGER.exception("Error revoking API key %s", api_key)
                return 0
            else:
                return result.rowcount if result else 0

    def _build_filters(
        self,
        options: KeyListOptions,
    ) -> tuple[str, list]:
        where = []
        params = []

        if options.user is not None:
            where.append("username = ?")
            params.append(options.user.username)

        if options.created_after:
            where.append("created_at > ?")
            params.append(options.created_after.isoformat())

        if options.created_before:
            where.append("created_at < ?")
            params.append(options.created_before.isoformat())

        clause = f" WHERE {' AND '.join(where)}" if where else ""
        return clause, params

    async def _select_api_keys(
        self,
        options: KeyListOptions,
        where_clause: str,
        params: list[str],
    ) -> list[tuple[str, str, str]]:
        """Select API keys based on the given options.

        :param options: Sanitized options for selection query
        :param where_clause: Sanitized WHERE clause for filtering
        :param params: Parameters for the WHERE clause
        :return: A list of tuples of (api_key, username, created_at)
        """
        offset = (options.page - 1) * options.limit

        order_clause = " "
        if options.order_by:
            ordering = "DESC" if options.order_desc else "ASC"
            order_clause = f" ORDER BY {options.order_by} {ordering}"

        # where clause is built safely in _build_filters, order_by is enum-validated
        query = (
            f"SELECT api_key, username, created_at FROM api_keys"  # noqa: S608
            f"{where_clause}{order_clause} "
            f"LIMIT ? OFFSET ?"
        )

        result = await self.connection.execute(query, [*params, options.limit, offset])
        rows = await result.fetchall()
        return [tuple(r) for r in rows]

    async def list_api_keys(
        self,
        options: KeyListOptions,
    ) -> tuple[list[tuple[str, str, str]], int]:
        """List API keys based on the given options.

        :param options: Options for filtering and pagination
        :return: Tuple of (list of (key, username, created_at), total count)
        """
        where_clause, params = self._build_filters(options)
        rows = await self._select_api_keys(
            options,
            where_clause,
            params,
        )

        return rows, len(rows)

    async def get_user_by_api_key(self, api_key: str) -> User | None:
        """Get user by API key.

        :param api_key: The API key to look up
        :return: The User object if API key is valid, None otherwise
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
