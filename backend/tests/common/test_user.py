import unittest

from app.common.user import User, Role


class TestRole(unittest.TestCase):
    def test_check_permission_owner(self):
        """Test owner permissions"""
        owner = Role.OWNER

        self.assertTrue(owner.check_permission(Role.OWNER))
        self.assertTrue(owner.check_permission(Role.ADMIN))
        self.assertTrue(owner.check_permission(Role.USER))

    def test_check_permission_admin(self):
        """Test admin permissions"""
        admin = Role.ADMIN

        self.assertFalse(admin.check_permission(Role.OWNER))
        self.assertTrue(admin.check_permission(Role.ADMIN))
        self.assertTrue(admin.check_permission(Role.USER))

    def test_check_permission_user(self):
        """Test user permissions"""
        user = Role.USER

        self.assertFalse(user.check_permission(Role.OWNER))
        self.assertFalse(user.check_permission(Role.ADMIN))
        self.assertTrue(user.check_permission(Role.USER))


class TestUser(unittest.TestCase):
    def test_user_creation_with_role_enum(self):
        """Test User creation with Role enum"""
        user = User("testuser", role=Role.ADMIN)

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.role, Role.ADMIN)
        self.assertIsInstance(user.role, Role)

    def test_user_string_representation(self):
        """Test User string representation"""
        user = User("testuser", role=Role.ADMIN)
        str_cast = str(user)
        repr_str = repr(user)

        self.assertIn("testuser", str_cast)
        self.assertIn("ADMIN", str_cast)

        self.assertIn("User", repr_str)
        self.assertIn("testuser", repr_str)
        self.assertIn("ADMIN", repr_str)


if __name__ == "__main__":
    unittest.main()
