import unittest
import asyncio

from app.rconclient.types import RCONCommand
from app.common.user import User, Role


class TestRCONCommand(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.user = User("testuser", role=Role.ADMIN)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Tear down test fixtures"""
        self.loop.close()

    async def test_rcon_command_creation_with_result(self):
        """Test RCONCommand creation with result future"""
        command = RCONCommand("list", self.user, require_result=True)
        command.set_command_result("Player count: 5")

        self.assertEqual(command.command, "list")
        self.assertEqual(command.user, self.user)
        self.assertEqual(await command.get_command_result(), "Player count: 5")

    async def test_set_command_error_with_future(self):
        """Test setting command error when future exists"""
        command = RCONCommand("list", self.user, require_result=True)
        error = Exception("THIS IS A TEST EXCEPTION")

        command.set_command_error(error)

        with self.assertRaises(Exception):
            await command.get_command_result()
