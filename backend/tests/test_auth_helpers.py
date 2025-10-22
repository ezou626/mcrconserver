from app.auth.account_helpers import (
    change_password,
    check_password,
    create_account,
    delete_account,
)
from app.auth.roles import Role
from app.auth.db_connection import get_db_connection

from test_base import DBTestCase, TEST_OWNER_PASSWORD, TEST_OWNER_USERNAME


class TestAccountHelpers(DBTestCase):
    def test_owner_created_on_init(self):
        conn = get_db_connection()
        cur = conn.execute(
            "SELECT username, role FROM users WHERE username = ?",
            (TEST_OWNER_USERNAME,),
        )
        row = cur.fetchone()
        self.assertIsNotNone(row, "Owner user should exist after initialization")
        self.assertEqual(row[0], TEST_OWNER_USERNAME)
        self.assertEqual(int(row[1]), int(Role.OWNER))

    def test_create_and_delete_user(self):
        user = create_account("alice", "An0ther!VeryStrongPassword_12345", Role.ADMIN)
        self.assertIsNotNone(user)
        # Help type checkers understand user is not None
        assert user is not None
        self.assertEqual(user.username, "alice")
        self.assertEqual(int(user.role), int(Role.ADMIN))

        # Ensure it exists in DB
        conn = get_db_connection()
        cur = conn.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("alice",))
        self.assertEqual(cur.fetchone()[0], 1)

        # Delete and verify
        deleted = delete_account("alice")
        self.assertEqual(deleted, 1)
        cur = conn.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("alice",))
        self.assertEqual(cur.fetchone()[0], 0)

    def test_change_password_and_check(self):
        # Wrong password fails
        self.assertIsNone(check_password(TEST_OWNER_USERNAME, "wrong-password"))

        # Change password
        err = change_password(TEST_OWNER_USERNAME, "Sup3r!LongPassword_ForOwner+++")
        self.assertIsNone(err)

        # Old password should fail; new one should succeed
        self.assertIsNone(check_password(TEST_OWNER_USERNAME, TEST_OWNER_PASSWORD))
        user = check_password(TEST_OWNER_USERNAME, "Sup3r!LongPassword_ForOwner+++")
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.username, TEST_OWNER_USERNAME)
        self.assertEqual(int(user.role), int(Role.OWNER))
