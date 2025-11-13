import secrets

from .db_connection import get_db_connection
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

API_KEY_LENGTH = 128


def generate_api_key(username: str) -> str | None:
    """
    Generate a secure API key for the given username.
    """

    api_key = secrets.token_urlsafe(API_KEY_LENGTH)

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


def list_api_keys(
    username: str, page: int = 1, limit: int = 10
) -> tuple[list[tuple[str, str]], int]:
    """
    List API keys for the given username with pagination.
    Returns tuple of (api_keys, total_count)
    """
    db = get_db_connection()
    cursor = db.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) FROM api_keys WHERE username = ?", (username,))
    total_count = cursor.fetchone()[0]

    # Get paginated results
    offset = (page - 1) * limit
    cursor.execute(
        "SELECT api_key, created_at FROM api_keys WHERE username = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (username, limit, offset),
    )
    rows = cursor.fetchall()
    return [(row[0], row[1]) for row in rows], total_count


def list_all_api_keys(
    page: int = 1, limit: int = 10
) -> tuple[list[tuple[str, str, str]], int]:
    """
    List all API keys for all users with pagination.
    Returns tuple of (api_keys, total_count)
    """
    db = get_db_connection()
    cursor = db.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) FROM api_keys")
    total_count = cursor.fetchone()[0]

    # Get paginated results
    offset = (page - 1) * limit
    cursor.execute(
        "SELECT api_key, username, created_at FROM api_keys ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = cursor.fetchall()
    return [(row[0], row[1], row[2]) for row in rows], total_count
