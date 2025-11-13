from app.auth.account_helpers import create_account
from app.auth.key_helpers import (
    generate_api_key,
    list_all_api_keys,
    list_api_keys,
    revoke_api_key,
)
from app.auth.roles import Role

from tests.test_base import DBTestCase, TEST_OWNER_USERNAME


class TestApiKeys(DBTestCase):
    def test_owner_can_generate_and_revoke_api_key(self):
        # Ensure owner exists from base setUp
        api_key = generate_api_key(TEST_OWNER_USERNAME)
        self.assertIsNotNone(api_key)
        assert api_key is not None

        # Listed under owner
        keys = list_api_keys(TEST_OWNER_USERNAME)
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0][0], api_key)

        # Revoke and verify
        revoked = revoke_api_key(api_key)
        self.assertEqual(revoked, 1)
        self.assertEqual(len(list_api_keys(TEST_OWNER_USERNAME)), 0)

    def test_list_all_api_keys(self):
        # Create additional users and keys
        user = create_account("alice", "An0ther!VeryStrongPassword_12345", Role.ADMIN)
        self.assertIsNotNone(user)
        generate_api_key(TEST_OWNER_USERNAME)
        generate_api_key("alice")

        all_keys = list_all_api_keys()
        owners = {u for (_, u, _ts) in all_keys}
        self.assertTrue(TEST_OWNER_USERNAME in owners)
        self.assertTrue("alice" in owners)
