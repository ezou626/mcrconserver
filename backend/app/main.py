from dotenv import load_dotenv
from fastapi import FastAPI, Form
import logging
import asyncio
import uvicorn
from contextlib import asynccontextmanager
import sqlite3

from .rconclient import worker, queue_command, get_queue_size
from .auth import (
    initialize_session_table,
    initialize_user_table,
    get_db_connection,
    router as auth_router,
)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("API is starting up")
LOG.info(uvicorn.Config.asgi_version)

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOG.info("App is starting up")
    db = get_db_connection()
    initialize_user_table(db)
    initialize_session_table(db)
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


@app.get("/")
def read_root():
    return {"message": "Hello World!"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
