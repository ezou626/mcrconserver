"""Configuration management for the RCON server application.

This module provides utilities for loading and validating configuration
from environment variables.
"""

import logging
import os
from dataclasses import dataclass, field

from app.src.auth import SecurityManager
from app.src.rconclient import RCONWorkerPoolConfig

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def configure_logging(app_config: AppConfig) -> None:
    """Configure logging based on the application configuration.

    :param app_config: The application configuration instance
    """
    if not app_config.logging_level:
        logging.basicConfig(level=logging.INFO, force=True)
        return

    numeric_level = getattr(logging, app_config.logging_level.upper(), None)
    if not isinstance(numeric_level, int):
        LOGGER.warning("Invalid log level: %s, using INFO", app_config.logging_level)
        numeric_level = logging.INFO
    logging.basicConfig(level=numeric_level, force=True)


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables.

    This dataclass holds all configuration values for the RCON server application.
    All fields are initialized from environment variables using field creators.

    **Usage:**

    Load a .env file first if needed, then create the config:

    .. code-block:: python

        from dotenv import load_dotenv
        load_dotenv('.env')  # User's responsibility
        config = AppConfig()
    """

    DEFAULT_DATABASE_PATH: str = "database.db"
    DEFAULT_WORKER_COUNT: int = 3
    DEFAULT_RECONNECT_PAUSE: int = 5
    DEFAULT_API_KEY_LENGTH: int = 32
    MINIMUM_JWT_SECRET_KEY_LENGTH: int = 32
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    MINIMUM_PASSPHRASE_LENGTH: int = 20

    # Database configuration
    db_path: str = field(
        default_factory=lambda: os.getenv("DB_PATH", AppConfig.DEFAULT_DATABASE_PATH),
    )

    # Logging configuration
    logging_level: str | None = field(
        default_factory=lambda: os.getenv("LOGGING_LEVEL"),
    )

    # RCON configuration
    rcon_password: str = field(
        default_factory=lambda: AppConfig._getenv_str_required("RCON_PASSWORD"),
    )
    rcon_port: int = field(
        default_factory=lambda: AppConfig._getenv_int_required("RCON_PORT", 25575),
    )
    rcon_socket_timeout: int | None = field(
        default_factory=lambda: AppConfig._getenv_int("RCON_SOCKET_TIMEOUT"),
    )
    worker_count: int = field(
        default_factory=lambda: AppConfig._getenv_int_required("WORKER_COUNT", 3),
    )
    reconnect_pause: int = field(
        default_factory=lambda: AppConfig._getenv_int_required("RECONNECT_PAUSE", 5),
    )

    # Security configuration
    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", ""),
    )

    algorithm: str = field(
        default_factory=lambda: os.getenv("ALGORITHM", "HS512"),
    )

    access_token_expire_minutes: int = field(
        default_factory=lambda: AppConfig._getenv_int_required(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            AppConfig.DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
        ),
    )

    passphrase_min_length: int = field(
        default_factory=lambda: AppConfig._getenv_int_required(
            "PASSPHRASE_MIN_LENGTH",
            AppConfig.MINIMUM_PASSPHRASE_LENGTH,
        ),
    )

    api_key_length: int = field(
        default_factory=lambda: AppConfig._getenv_int_required(
            "API_KEY_LENGTH",
            AppConfig.DEFAULT_API_KEY_LENGTH,
        ),
    )

    # Shutdown configuration
    shutdown_grace_period: int | None = field(
        default_factory=lambda: AppConfig._getenv_int(
            "SHUTDOWN_GRACE_PERIOD",
            RCONWorkerPoolConfig.DISABLE,
        ),
    )
    shutdown_queue_clear_period: int | None = field(
        default_factory=lambda: AppConfig._getenv_int(
            "SHUTDOWN_QUEUE_CLEAR_PERIOD",
            RCONWorkerPoolConfig.NO_TIMEOUT,
        ),
    )
    shutdown_await_period: int | None = field(
        default_factory=lambda: AppConfig._getenv_int(
            "SHUTDOWN_AWAIT_PERIOD",
            RCONWorkerPoolConfig.NO_TIMEOUT,
        ),
    )

    def __post_init__(self) -> None:
        """Post-initialization validation."""
        if self.worker_count <= 0:
            msg = "WORKER_COUNT must be a positive integer"
            raise ValueError(msg)
        if len(self.secret_key) < self.MINIMUM_JWT_SECRET_KEY_LENGTH:
            LOGGER.warning(
                "SECRET_KEY is not set or too short, generating a random key",
            )
            self.secret_key = os.urandom(self.MINIMUM_JWT_SECRET_KEY_LENGTH).hex()

    @property
    def worker_config(self) -> RCONWorkerPoolConfig:
        """Create a RCONWorkerPoolConfig instance from this configuration.

        :return: Configured RCONWorkerPoolConfig instance
        :rtype: RCONWorkerPoolConfig
        """
        return RCONWorkerPoolConfig(
            password=self.rcon_password,
            port=self.rcon_port,
            socket_timeout=self.rcon_socket_timeout,
            worker_count=self.worker_count,
            reconnect_pause=self.reconnect_pause,
            grace_period=self.shutdown_grace_period,
            queue_clear_period=self.shutdown_queue_clear_period,
            await_shutdown_period=self.shutdown_await_period,
        )

    @property
    def security_manager(self) -> SecurityManager:
        """Create a SecurityManager instance from this configuration.

        :return: Configured SecurityManager instance
        :rtype: SecurityManager
        """
        return SecurityManager(
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            expire_minutes=self.access_token_expire_minutes,
            passphrase_min_length=self.passphrase_min_length,
            api_key_length=self.api_key_length,
        )

    @staticmethod
    def _getenv_str_required(key: str) -> str:
        """Get a required string environment variable.

        :param key: Environment variable name
        :type key: str
        :return: The environment variable value
        :rtype: str
        :raises ValueError: If variable is not set
        """
        value = os.getenv(key)
        if value is None:
            msg = f"Required environment variable {key} is not set"
            raise ValueError(msg)
        return value

    @staticmethod
    def _getenv_int(key: str, default: int | None = None) -> int | None:
        """Get an integer environment variable.

        :param key: Environment variable name
        :type key: str
        :param default: Default value if not set
        :type default: int | None
        :rtype: int | None
        :raises ValueError: If value cannot be converted to int
        """
        value_str = os.getenv(key)

        if value_str is None:
            return default

        try:
            return int(value_str)
        except ValueError as e:
            msg = f"Environment variable {key} must be an integer, got: {value_str}"
            raise ValueError(msg) from e

    @staticmethod
    def _getenv_int_required(key: str, default: int) -> int:
        """Get an integer environment variable with a default.

        :param key: Environment variable name
        :type key: str
        :param default: Default value if not set
        :type default: int
        :return: The environment variable value as integer or default
        :rtype: int
        :raises ValueError: If value cannot be converted to int
        """
        value_str = os.getenv(key)

        if value_str is None:
            return default

        try:
            return int(value_str)
        except ValueError as e:
            msg = f"Environment variable {key} must be an integer, got: {value_str}"
            raise ValueError(msg) from e
