"""Configuration management for the RCON server application.

This module provides utilities for loading and validating configuration
from environment variables.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

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
