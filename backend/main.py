from dotenv import load_dotenv
from fastapi import FastAPI
import logging
import asyncio
import uvicorn
from rconclient import worker, queue_command, get_queue_size
from contextlib import asynccontextmanager
import sqlite3
from helpers import initialize_session_table, initialize_user_table, check_password

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("API is starting up")
LOG.info(uvicorn.Config.asgi_version)

load_dotenv()

DB_PATH = "database.db"
LOG.info("Using database at: %s", DB_PATH)
db = None


def get_db_connection():
    global db
    if db is not None:
        return db
    db = sqlite3.connect(DB_PATH)
    initialize_user_table(db)
    initialize_session_table(db)
    return db


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


@app.get("/")
def read_root():
    return {"message": "Hello World!"}


@app.post("/login")
def login(username: str, password: str):
    db = get_db_connection()

    if check_password(db, username, password):
        return {"success": True, "message": "Login successful"}
    else:
        return {"success": False, "message": "Invalid username or password"}
