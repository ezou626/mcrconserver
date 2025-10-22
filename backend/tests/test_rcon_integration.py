import unittest


@unittest.skip(
    "RCON integration tests are planned once a test Minecraft server is available."
)
class TestRconIntegration(unittest.TestCase):
    def test_send_basic_command(self):
        # TODO: Spin up test server and validate a no-op command (e.g., 'list')
        pass

    def test_permission_enforced(self):
        # TODO: Ensure only users with sufficient roles can issue admin commands
        pass
