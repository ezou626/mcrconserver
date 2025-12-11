"""Configuration management for the RCON server application.

This module provides utilities for loading and validating configuration
from environment variables.
"""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from jwt.algorithms import get_default_algorithms

from app.auth import SecurityManager
from app.rconclient import RCONWorkerPoolConfig

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

_PORT_UPPER_BOUND = 65536
_DEFAULT_WORKER_COUNT = 5
_DEFAULT_RECONNECT_PAUSE_SECONDS = 5
_DEFAULT_RCON_PORT = 25575
_MINUTES_IN_DAY = 60 * 24
_DEFAULT_PASSPHRASE_MIN_LENGTH = 20
_DEFAULT_API_KEY_LENGTH = 64


def configure_logging(app_config: AppConfig) -> None:
    """Configure logging based on the application configuration.

    :param app_config: The application configuration instance
    """
    if not app_config.logging_level:
        logging.basicConfig(level=logging.INFO)
        return

    numeric_level = getattr(logging, app_config.logging_level.upper(), None)
    if numeric_level is None:
        LOGGER.warning("Invalid log level: %s, using INFO", app_config.logging_level)
        numeric_level = logging.INFO
    logging.basicConfig(level=numeric_level)


@dataclass
class AppConfig:
    """Holds application configuration loaded from environment variables."""

    database_path: str
    logging_level: str | None
    root_path: str

    rcon_password: str
    rcon_port: int
    rcon_socket_timeout: int | None
    worker_count: int
    reconnect_pause: int

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    passphrase_min_length: int
    api_key_length: int

    shutdown_grace_period: int | None
    shutdown_queue_clear_period: int | None
    shutdown_await_period: int | None

    def __post_init__(self) -> None:
        """Initialize derived configuration attributes."""
        self.worker_config = RCONWorkerPoolConfig(
            password=self.rcon_password,
            port=self.rcon_port,
            socket_timeout=self.rcon_socket_timeout,
            worker_count=self.worker_count,
            reconnect_pause=self.reconnect_pause,
            grace_period=self.shutdown_grace_period,
            queue_clear_period=self.shutdown_queue_clear_period,
            await_shutdown_period=self.shutdown_await_period,
        )

        self.security_manager = SecurityManager(
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            expire_minutes=self.access_token_expire_minutes,
            passphrase_min_length=self.passphrase_min_length,
            api_key_length=self.api_key_length,
        )


def get_env_str(
    var_name: str,
    default: str | None,
    value_checker: Callable[[str], bool] | None = None,
) -> str:
    """Get an environment variable as a string with optional constraints.

    :param var_name: Name of the environment variable
    :param default: Default value if the variable is not set
    :param value_checker: Optional function to validate the value
    :return: The environment variable value
    :raises ValueError: If the value does not meet the constraints
    """
    value = os.getenv(var_name, default)
    if value is None:
        msg = f"Environment variable {var_name} is required"
        raise ValueError(msg)

    if value_checker and not value_checker(value):
        msg = f"Environment variable {var_name} has invalid value: {value}"
        raise ValueError(msg)

    return value


def get_env_optional_int(
    var_name: str,
    default: int | None,
    value_checker: Callable[[int], bool] | None = None,
) -> int | None:
    """Get an environment variable as an integer with optional constraints.

    To indicate None, set the environment variable to an empty string.
    To indicate the default, leave the environment variable unset.
    To indicate an integer value, set the environment variable to that integer.

    :param var_name: Name of the environment variable
    :param default: Default value if the variable is not set
    :param value_checker: Optional function to validate the value
    :return: The environment variable value as an integer
    :raises ValueError: If the value does not meet the constraints or is not an integer
    """
    value_str = os.getenv(var_name)
    if value_str is None:
        return default

    if value_str == "":
        return None

    if not value_str.isnumeric():
        msg = f"Environment variable {var_name} must be an integer, got: {value_str}"
        raise ValueError(msg)

    value = int(value_str)

    if value_checker and not value_checker(value):
        msg = f"Environment variable {var_name} has invalid value: {value}"
        raise ValueError(msg)

    return value


def get_env_int(
    var_name: str,
    default: int,
    value_checker: Callable[[int], bool] | None = None,
) -> int:
    """Get an environment variable as an integer with optional constraints.

    :param var_name: Name of the environment variable
    :param default: Default value if the variable is not set
    :param value_checker: Optional function to validate the value
    :return: The environment variable value as an integer
    :raises ValueError: If the value does not meet the constraints or is not an integer
    """
    value_str = os.getenv(var_name)
    if value_str is None or value_str == "":
        return default

    if not value_str.isnumeric():
        msg = f"Environment variable {var_name} must be an integer, got: {value_str}"
        raise ValueError(msg)

    value = int(value_str)

    if value_checker and not value_checker(value):
        msg = f"Environment variable {var_name} has invalid value: {value}"
        raise ValueError(msg)

    return value


def load_config_from_env(env_file: str | Path | None) -> AppConfig:
    """Load application configuration from environment variables.

    :return: An AppConfig instance populated with environment variable values
    """
    if env_file:
        load_dotenv(dotenv_path=env_file)

    return AppConfig(
        database_path=get_env_str("DATABASE_PATH", "./mcrconserver_sqlite.db"),
        logging_level=get_env_str(
            "LOGGING_LEVEL",
            "INFO",
            None,
        ),
        root_path=get_env_str(
            "ROOT_PATH",
            "",
        ),
        rcon_password=get_env_str("RCON_PASSWORD", None),
        rcon_port=get_env_int(
            "RCON_PORT",
            _DEFAULT_RCON_PORT,
            lambda port: 0 < port < _PORT_UPPER_BOUND,
        ),
        rcon_socket_timeout=get_env_optional_int(
            "RCON_SOCKET_TIMEOUT",
            None,  # if not set, no timeout
            lambda timeout: timeout >= 0,
        ),
        worker_count=get_env_int(
            "WORKER_COUNT",
            _DEFAULT_WORKER_COUNT,
            lambda count: count > 0,
        ),
        reconnect_pause=get_env_int(
            "RECONNECT_PAUSE",
            _DEFAULT_RECONNECT_PAUSE_SECONDS,
            lambda pause: pause >= 0,
        ),
        secret_key=get_env_str("SECRET_KEY", os.urandom(32).hex()),
        algorithm=get_env_str(
            "ALGORITHM",
            "HS512",
            lambda algorithm: algorithm in get_default_algorithms(),
        ),
        access_token_expire_minutes=get_env_int(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            _MINUTES_IN_DAY,  # default 1 day
            lambda minutes: minutes > 0,
        ),
        passphrase_min_length=get_env_int(
            "PASSPHRASE_MIN_LENGTH",
            _DEFAULT_PASSPHRASE_MIN_LENGTH,
            lambda length: length > 0,
        ),
        api_key_length=get_env_int(
            "API_KEY_LENGTH",
            _DEFAULT_API_KEY_LENGTH,
            lambda length: length > 0,
        ),
        shutdown_grace_period=get_env_optional_int(
            "SHUTDOWN_GRACE_PERIOD",
            RCONWorkerPoolConfig.DISABLE,
            lambda period: RCONWorkerPoolConfig.valid_shutdown_phase_timeout(period),
        ),
        shutdown_queue_clear_period=get_env_optional_int(
            "SHUTDOWN_QUEUE_CLEAR_PERIOD",
            RCONWorkerPoolConfig.NO_TIMEOUT,
            lambda period: RCONWorkerPoolConfig.valid_shutdown_phase_timeout(period),
        ),
        shutdown_await_period=get_env_optional_int(
            "SHUTDOWN_AWAIT_PERIOD",
            RCONWorkerPoolConfig.NO_TIMEOUT,
            lambda period: RCONWorkerPoolConfig.valid_shutdown_phase_timeout(period),
        ),
    )
