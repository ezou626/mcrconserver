import logging
from sqlite3 import connect

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

db_path = None
db = None


def set_db_path(path: str) -> None:
    global db_path, db
    db_path = path
    LOGGER.debug(f"Database path set to: {db_path}")
    if db is not None:
        db.close()
        db = None


def get_db_connection():
    global db
    if db is not None:
        return db
    if db_path is None:
        raise RuntimeError("Database path is not set.")
    db = connect(db_path, check_same_thread=False)
    LOGGER.debug(f"Database connection established to: {db_path}")
    return db
