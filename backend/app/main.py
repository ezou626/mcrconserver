import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import AuthQueries, router as auth_router
from app.router import router as api_router, pool as worker_pool
from app.config import AppConfig

LOG = logging.getLogger(__name__)


def load_env_file(env_path: str | Path = ".env") -> None:
    """Load environment variables from a .env file if available.

    :param env_path: Path to the .env file
    :type env_path: str | Path
    """
    try:
        from dotenv import load_dotenv

        env_path = Path(env_path)
        if env_path.exists():
            LOG.info(f"Loading environment variables from {env_path}")
            load_dotenv(env_path)
        else:
            LOG.debug(f"No .env file found at {env_path}")
    except ImportError:
        LOG.debug("python-dotenv not available, skipping .env file loading")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown of the RCON worker pool and other resources.
    """
    LOG.info("Minecraft RCON Server API is starting")

    # Load .env file if available
    load_env_file()

    # Load configuration from environment
    try:
        config = AppConfig()
    except ValueError as e:
        LOG.error(f"Configuration error: {e}")
        raise RuntimeError(f"Startup aborted: {e}") from e

    # Setup logging
    config.setup_logging()

    # Initialize database
    AuthQueries.initialize_tables(config.db_path)

    # Configure worker pool
    global worker_pool
    worker_pool.password = config.rcon_password
    worker_pool.socket_timeout = config.rcon_socket_timeout
    worker_pool.worker_count = config.worker_count
    worker_pool.reconnect_pause = config.reconnect_pause
    worker_pool.shutdown_config = config.shutdown_details

    # Start worker pool
    async with worker_pool:
        LOG.info("RCON worker pool started successfully")
        yield

    LOG.info("Minecraft RCON Server API is shutting down")


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
app.include_router(api_router, prefix="/rcon", tags=["rcon"])
