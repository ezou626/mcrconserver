import unittest

from app.common.user import User, Role


class TestRole(unittest.TestCase):
    def test_role_enum_values(self):
        """Test Role enum has correct values"""
        self.assertEqual(Role.OWNER.value, 0)
        self.assertEqual(Role.ADMIN.value, 1)
        self.assertEqual(Role.USER.value, 2)

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

    def test_role_hierarchy_logic(self):
        """Test that permission checking follows hierarchy"""
        # Lower numeric values have higher permissions
        self.assertTrue(Role.OWNER.value < Role.ADMIN.value < Role.USER.value)

    def test_role_from_integer(self):
        """Test creating Role from integer values"""
        self.assertEqual(Role(0), Role.OWNER)
        self.assertEqual(Role(1), Role.ADMIN)
        self.assertEqual(Role(2), Role.USER)

    def test_invalid_role_value(self):
        """Test invalid role values raise errors"""
        with self.assertRaises(ValueError):
            Role(99)

        with self.assertRaises(ValueError):
            Role(-1)

    def test_role_comparison(self):
        """Test Role comparison operations"""
        self.assertTrue(Role.OWNER < Role.ADMIN)
        self.assertTrue(Role.ADMIN < Role.USER)
        self.assertFalse(Role.USER < Role.ADMIN)

    def test_role_equality(self):
        """Test Role equality"""
        self.assertEqual(Role.OWNER, Role(0))
        self.assertEqual(Role.ADMIN, Role(1))
        self.assertNotEqual(Role.OWNER, Role.ADMIN)


class TestUser(unittest.TestCase):
    def test_user_creation_with_role_enum(self):
        """Test User creation with Role enum"""
        user = User("testuser", role=Role.ADMIN)

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.role, Role.ADMIN)
        self.assertIsInstance(user.role, Role)

    def test_user_equality(self):
        """Test User equality comparison"""
        user1 = User("testuser", role=Role.ADMIN)
        user2 = User("testuser", role=Role.ADMIN)
        user3 = User("testuser", role=Role.USER)
        user4 = User("different", role=Role.ADMIN)

        self.assertEqual(user1, user2)
        self.assertNotEqual(user1, user3)
        self.assertNotEqual(user1, user4)

    def test_user_string_representation(self):
        """Test User string representation"""
        user = User("testuser", role=Role.ADMIN)
        str_repr = str(user)

        self.assertIn("testuser", str_repr)
        self.assertIn("ADMIN", str_repr)

    def test_user_repr(self):
        """Test User repr representation"""
        user = User("testuser", role=Role.ADMIN)
        repr_str = repr(user)

        self.assertIn("User", repr_str)
        self.assertIn("testuser", repr_str)

    def test_username(self):
        """Test User username with different string types"""
        user1 = User("testuser", role=Role.USER)
        user2 = User("test_user", role=Role.USER)
        user3 = User("123user", role=Role.USER)
        user4 = User("", role=Role.USER)

        self.assertEqual(user1.username, "testuser")
        self.assertEqual(user2.username, "test_user")
        self.assertEqual(user3.username, "123user")
        self.assertEqual(user4.username, "")


if __name__ == "__main__":
    unittest.main()
