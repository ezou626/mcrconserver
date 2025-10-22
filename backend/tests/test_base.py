import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

# Import low-level DB module so we can steer it to a temp DB file per test
from app.auth import db_connection
from app.auth.account_helpers import initialize_user_table, initialize_keys_table


TEST_OWNER_USERNAME = "owner"
TEST_OWNER_PASSWORD = "Str0ng!Password-With_Length>=20"


def _reset_db_to(path: str):
    """
    Point the auth DB to the provided file path and ensure a clean slate.
    Closes any existing connection, deletes the file if present, and resets globals.
    """
    # Close pre-existing connection if present
    if getattr(db_connection, "db", None) is not None:
        try:
            db_connection.db.close()
        except Exception:
            pass
    # Reset connection handle
    db_connection.db = None
    db_connection.DB_PATH = path

    if os.path.exists(path):
        os.remove(path)


@contextmanager
def _owner_creation_patches():
    """
    Provide input/getpass responses so initialize_user_table() won't block.
    """
    with (
        patch("app.auth.account_helpers.input", return_value=TEST_OWNER_USERNAME),
        patch(
            "app.auth.account_helpers.getpass.getpass",
            side_effect=[TEST_OWNER_PASSWORD, TEST_OWNER_PASSWORD],
        ),
    ):
        yield


class DBTestCase(unittest.TestCase):
    """
    Base TestCase that prepares an isolated temporary SQLite database and
    ensures the auth tables are initialized with a default owner account.
    """

    def setUp(self) -> None:
        # Each test gets its own temp DB file for isolation
        self._tmpdir = tempfile.TemporaryDirectory(prefix="mcrconserver-test-")
        self.db_path = os.path.join(self._tmpdir.name, "test.db")

        _reset_db_to(self.db_path)

        # Initialize tables and seed owner without interactive prompts
        with _owner_creation_patches():
            initialize_user_table()
        initialize_keys_table()

        return super().setUp()

    def tearDown(self) -> None:
        # Clean up temp DB file and directory
        try:
            _reset_db_to(self.db_path)
        finally:
            try:
                self._tmpdir.cleanup()
            except Exception:
                pass
        return super().tearDown()
