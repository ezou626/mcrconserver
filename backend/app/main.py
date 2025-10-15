import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .auth import initialize_user_table, initialize_keys_table
from .auth import (
    router as auth_router,
)
from .router import router as api_router
from .rconclient import worker

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
app.include_router(api_router, prefix="/api", tags=["api"])
