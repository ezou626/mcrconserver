import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import initialize_user_table, initialize_keys_table
from .auth import (
    router as auth_router,
)
from .router import router as api_router
from .rconclient import worker, shutdown_worker

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("API is starting up")

load_dotenv()
initialize_user_table()
initialize_keys_table()


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOG.info("App is starting up")
    task = asyncio.create_task(worker())
    try:
        yield
    finally:
        LOG.info("App is shutting down")
        # Cancel background task on shutdown
        shutdown_worker()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Minecraft RCON Server", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # No credentials needed with JWT bearer tokens
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello World!"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(api_router, prefix="/rcon", tags=["rcon"])
