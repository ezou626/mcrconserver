import secrets

from .db_connection import get_db_connection
from .user import User


def generate_api_key(username: str) -> str | None:
    """
    Generate a secure API key for the given username.
    """

    api_key = secrets.token_urlsafe(64)

    try:
        db = get_db_connection()
        db.execute(
            "INSERT INTO api_keys (api_key, username) VALUES (?, ?)",
            (api_key, username),
        )
        db.commit()
    except Exception as e:
        print(f"Error generating API key: {e}")
        return None

    return api_key


def revoke_api_key(api_key: str):
    """
    Revoke the given API key. Anyone with the permissions can revoke it.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM api_keys WHERE api_key = ?", (api_key,))
    db.commit()
    return cursor.rowcount


def validate_api_key(api_key: str) -> User | None:
    """
    Validate the given API key.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT username FROM api_keys WHERE api_key = ?",
        (api_key,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    cursor.execute(
        "SELECT role FROM users WHERE username = ?",
        (row[0],),
    )
    role_row = cursor.fetchone()
    if not role_row:
        return None

    from .roles import Role  # local import to avoid cycles

    return User(row[0], role=Role(int(role_row[0])))


def list_api_keys(username: str) -> list[tuple[str, str]]:
    """
    List all API keys for the given username.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT api_key, created_at FROM api_keys WHERE username = ?", (username,)
    )
    rows = cursor.fetchall()
    return [(row[0], row[1]) for row in rows]


def list_all_api_keys() -> list[tuple[str, str, str]]:
    """
    List all API keys for all users.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT api_key, username, created_at FROM api_keys")
    rows = cursor.fetchall()
    return [(row[0], row[1], row[2]) for row in rows]
