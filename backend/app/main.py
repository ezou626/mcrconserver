import logging
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.auth import (
    AuthQueries,
    router as auth_router,
    validate_api_key,
    validate_jwt_token,
)
from app.config import AppConfig
from app.common import User, Role
from app.rconclient import RCONWorkerPool, RCONCommand

from dotenv import load_dotenv

LOGGER = logging.getLogger(__name__)
POOL = RCONWorkerPool()


def load_env_file(env_path: str | Path) -> None:
    """Load environment variables from a .env file if available.

    :param env_path: Path to the .env file
    :type env_path: str | Path
    """
    env_path = Path(env_path)
    if env_path.exists():
        LOGGER.info(f"Loading environment variables from {env_path}")
        load_dotenv(env_path)
    else:
        LOGGER.debug(f"No .env file found at {env_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown of the RCON worker pool and other resources.
    """
    LOGGER.info("Minecraft RCON Server API is starting")

    load_env_file(os.getenv("MCRCON_ENV_FILE", ".env"))

    config = AppConfig()

    AuthQueries.initialize_tables(config.db_path)

    POOL.config = config.worker_config

    async with POOL:
        LOGGER.info("RCON worker pool started successfully")
        yield

    LOGGER.info("Minecraft RCON Server API is shutting down")


app = FastAPI(title="Minecraft RCON Server API", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return "Minecraft RCON Server API"


app.include_router(auth_router, prefix="/auth", tags=["auth"])

router = APIRouter()
pool = RCONWorkerPool()  # to be initialized in main


@router.post("/session/command")
async def command(
    command: str,
    user: User = Depends(validate_jwt_token),
    require_result: bool = True,
):
    if not user.role.check_permission(Role.ADMIN):
        raise HTTPException(status_code=403, detail="Forbidden")

    rcon_command = RCONCommand.create(
        command=command, user=user, require_result=require_result
    )

    try:
        await pool.queue_command(rcon_command)
    except RuntimeError:
        raise HTTPException(
            status_code=500, detail="Error queuing command: worker shutting down"
        )

    if not require_result:
        return "Command queued successfully"

    try:
        command_result = await rcon_command.get_command_result()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing command: {e}")

    return command_result


@router.post("/key/command")
async def command_with_api_key(
    command: str, user: User = Depends(validate_api_key), require_result: bool = True
):
    rcon_command = RCONCommand.create(
        command=command, user=user, require_result=require_result
    )

    try:
        await pool.queue_command(rcon_command)
    except RuntimeError:
        raise HTTPException(
            status_code=500, detail="Error queuing command: worker shutting down"
        )

    if not require_result:
        return "Command queued successfully"

    try:
        command_result = await rcon_command.get_command_result()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing command: {e}")

    return command_result
