import asyncio
import logging
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import initialize_user_table, initialize_keys_table
from .auth import (
    router as auth_router,
)
from .router import router as api_router
from .rconclient import worker, shutdown_worker, get_connection_event

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

initialize_user_table()
initialize_keys_table()


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOG.info("Minecraft RCON Server API is starting")

    logging_level = os.getenv("LOGGING_LEVEL")
    logging.basicConfig(level=logging_level)

    password = os.getenv("RCON_PASSWORD")
    timeout_str = os.getenv("RCON_TIMEOUT")
    timeout = int(timeout_str) if timeout_str is not None else None

    if not password:
        raise RuntimeError("Startup aborted: RCON_PASSWORD must be set")

    task = asyncio.create_task(worker(rcon_password=password, timeout=timeout))

    await get_connection_event().wait()

    yield

    LOG.info("Minecraft RCON Server API is shutting down")
    shutdown_worker()
    await task


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
