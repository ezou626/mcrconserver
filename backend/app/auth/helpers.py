import logging
from sqlite3 import connect
import getpass

from bcrypt import checkpw, gensalt, hashpw

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("Auth helpers are being imported")

SPECIAL_CHARACTERS = "!@#$%^&*()-_=+[{]}"

DB_PATH = "database.db"
LOG.info("Using database at: %s", DB_PATH)
db = None


def get_db_connection():
    global db
    if db is not None:
        return db
    db = connect(DB_PATH, check_same_thread=False)
    return db


def initialize_user_table():
    db = get_db_connection()

    # check if users table exists, if not create it
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT NOT NULL,
            salt TEXT NOT NULL,
            api_key TEXT
        );
        """
    )
    db.commit()

    # if no users exist, prompt to create an admin user

    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    username = input("Please enter the admin username: ")
    admin_password = None
    while not admin_password:
        admin_password = getpass.getpass("Please enter the admin password: ")
        if not is_password_valid(admin_password):
            admin_password = None
            continue
    admin_password_confirm = getpass.getpass("Please re-enter the admin password: ")
    if admin_password != admin_password_confirm:
        return None
    salt = gensalt()
    hashed_password = hashpw(admin_password.encode(), salt)
    db.execute(
        "INSERT INTO users (username, hashed_password, salt) VALUES (?, ?, ?)",
        (username, hashed_password, salt),
    )
    db.commit()


def is_password_valid(admin_password: str) -> bool:
    """
    Password requirements logic.
    """
    if len(admin_password) < 8:
        print("Admin password must be at least 8 characters long")
        return False
    if not any(c.isupper() for c in admin_password):
        print("Admin password must contain at least one uppercase letter")
        return False
    if not any(c.islower() for c in admin_password):
        print("Admin password must contain at least one lowercase letter")
        return False
    if not any(c.isdigit() for c in admin_password):
        print("Admin password must contain at least one digit")
        return False
    if not any(c in SPECIAL_CHARACTERS for c in admin_password):
        print(
            "Admin password must contain at least one special character in "
            + SPECIAL_CHARACTERS
        )
        return False
    return True


def check_password(username: str, password: str) -> bool:
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT hashed_password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row is None:
        return False
    stored_hashed_password = row[0]
    return checkpw(password.encode(), stored_hashed_password)
