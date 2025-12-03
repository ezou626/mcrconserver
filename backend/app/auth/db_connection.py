import logging
from sqlite3 import connect

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

_db_path = None
_db = None


def set_db_path(path: str) -> None:
    global _db_path, _db
    _db_path = path
    LOGGER.debug(f"Database path set to: {_db_path}")
    if _db is not None:
        _db.close()
        _db = None


def get_db_connection():
    global _db
    if _db is not None:
        return _db
    if _db_path is None:
        raise RuntimeError("Database path is not set.")
    _db = connect(_db_path, check_same_thread=False)
    LOGGER.debug(f"Database connection established to: {_db_path}")
    return _db
