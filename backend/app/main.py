import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .auth import initialize_user_table, initialize_keys_table, validate_session
from .auth import (
    router as auth_router,
)
from .rconclient import get_queue_size, queue_command, worker

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
    yield
    LOG.info("App is shutting down")
    try:
        yield
    finally:
        # Cancel background task on shutdown
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Minecraft RCON Server", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    same_site="strict",
    session_cookie="session_id",
    secret_key=os.environ.get("SECRET_KEY", os.urandom(32).hex()),
    max_age=86400 * 7,  # 7 days
    https_only=True,
    path="/",
)


@app.get("/")
def read_root():
    return {"message": "Hello World!"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])


@app.post("/command")
async def command(command: str, _user: str = Depends(validate_session)):
    if not command:
        return {"success": False, "message": "No command provided"}

    queue_size = get_queue_size()
    if queue_size >= 100:
        return {"success": False, "message": "Server is busy. Please try again later."}

    if queue_command(command):
        return {"success": True}
    return {"success": False, "message": "Failed to process command."}
