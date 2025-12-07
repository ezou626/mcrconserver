"""Init file for app package."""

import os
from typing import TYPE_CHECKING

from app.src import configure_fastapi_app, load_config_from_env

if TYPE_CHECKING:
    from fastapi import FastAPI


def create_app(env_file: str | None = os.environ.get("ENV_FILE", ".env")) -> FastAPI:
    """Create and configure the FastAPI application.

    The default here is for uvicorn command line usage, in which case the user
    should set ENV_FILE environment variable if they want a different file.

    :param env_file: Optional path to the environment configuration file
    :return: Configured FastAPI application
    """
    config = load_config_from_env(env_file)
    return configure_fastapi_app(config)
