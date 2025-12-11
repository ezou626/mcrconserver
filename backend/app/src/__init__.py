"""FastAPI application factory for RCON functionality."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiosqlite import connect as aiosqlite_connect
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.src.auth import (
    AuthQueries,
    Validate,
    configure_auth_router,
    configure_key_router,
)
from app.src.command_router import configure_command_router
from app.src.rconclient import RCONWorkerPool

from .config import load_config_from_env

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from .config import AppConfig

LOGGER = logging.getLogger(__name__)
POOL = RCONWorkerPool()


def configure_fastapi_app(config: AppConfig) -> FastAPI:
    """Configure and return the FastAPI application.

    :param config: Application configuration
    :return: Configured FastAPI application
    """
    worker_pool = RCONWorkerPool(config.worker_config)

    if not Path(config.database_path).parent.exists():
        Path(config.database_path).parent.mkdir(parents=True, exist_ok=True)
        LOGGER.info(
            "Created directory for database at %s",
            Path(config.database_path).parent,
        )

    if not Path(config.database_path).exists():
        LOGGER.info("Database file does not exist at %s", config.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[Any, Any]:
        """Application lifespan manager.

        Handles startup and shutdown of the RCON worker pool and other resources.
        """
        LOGGER.info("Minecraft RCON Server API is starting")

        async with (
            aiosqlite_connect(config.database_path) as db_connection,
            worker_pool as pool,
        ):
            auth_queries = AuthQueries(db_connection, config.security_manager)

            validate = Validate(auth_queries)

            auth_router = configure_auth_router(APIRouter(), validate)

            auth_router = configure_key_router(
                auth_router,
                validate,
            )

            command_router = configure_command_router(
                APIRouter(),
                pool,
                validate,
            )

            app.include_router(auth_router, prefix="/auth", tags=["auth"])
            app.include_router(command_router, prefix="/commands", tags=["commands"])

            yield

            LOGGER.info("Minecraft RCON Server API is shutting down")

    app = FastAPI(
        title="Minecraft RCON Server API",
        version="0.0.1",
        lifespan=lifespan,
        root_path=config.root_path,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def read_root() -> str:
        return "Minecraft RCON Server API"

    return app


__all__ = ["configure_fastapi_app", "load_config_from_env"]
