import logging
from sqlite3 import connect

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

DB_PATH = "database.db"
LOG.info("Using database at: %s", DB_PATH)
db = None


def get_db_connection():
    global db
    if db is not None:
        return db
    db = connect(DB_PATH, check_same_thread=False)
    return db
