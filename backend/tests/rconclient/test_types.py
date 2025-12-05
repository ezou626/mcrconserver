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
        command = RCONCommand.create("list", self.user, require_result=True)
        command.set_command_result("Player count: 5")

        self.assertEqual(command.command, "list")
        self.assertEqual(command.user, self.user)
        self.assertEqual(await command.get_command_result(), "Player count: 5")

    async def test_set_command_error_with_future(self):
        """Test setting command error when future exists"""
        command = RCONCommand.create("list", self.user, require_result=True)
        error = Exception("THIS IS A TEST EXCEPTION")

        command.set_command_error(error)

        with self.assertRaises(Exception):
            await command.get_command_result()

    async def test_add_dependency(self):
        """Test adding a dependency to an RCONCommand"""
        command1 = RCONCommand.create("list", self.user, require_result=True)
        command2 = RCONCommand.create("say Hello", self.user, require_result=True)
        command2.add_dependency(command1)

        self.assertIn(command1, command2.dependencies)

    async def test_topological_sort_simple(self):
        """Test topological sorting of two RCON commands"""
        command1 = RCONCommand.create(
            "list", self.user, command_id=1, require_result=True
        )
        command2 = RCONCommand.create(
            "say Hello", self.user, command_id=2, require_result=True
        )
        command2.add_dependency(command1)

        sorted_commands = RCONCommand.topological_sort([command2, command1])
        self.assertEqual(sorted_commands, [command1, command2])

    async def test_topological_sort_cycle(self):
        """Test topological sorting with a cycle in dependencies"""
        command1 = RCONCommand.create(
            "list", self.user, command_id=1, require_result=True
        )
        command2 = RCONCommand.create(
            "say Hello", self.user, command_id=2, require_result=True
        )
        command1.add_dependency(command2)
        command2.add_dependency(command1)

        with self.assertRaises(ValueError):
            RCONCommand.topological_sort([command1, command2])

    async def test_topological_sort_duplicate_ids(self):
        """Test topological sorting with duplicate command IDs"""
        command1 = RCONCommand.create(
            "list", self.user, command_id=1, require_result=True
        )
        command2 = RCONCommand.create(
            "say Hello", self.user, command_id=1, require_result=True
        )

        sorted_commands = RCONCommand.topological_sort([command1, command2])
        self.assertIsNone(sorted_commands)

    async def test_topological_sort_large_graph(self):
        """Test topological sorting with a large, complex dependency graph"""

        commands = {}
        for i in range(1, 11):
            commands[i] = RCONCommand.create(
                f"command{i}", self.user, command_id=i, require_result=True
            )

        # Set up dependencies (dependency_id, dependent_id)
        dependencies = [
            (1, 3),
            (1, 4),
            (2, 4),
            (2, 5),
            (3, 6),
            (3, 7),
            (4, 7),
            (4, 8),
            (5, 8),
            (6, 9),
            (7, 9),
            (7, 10),
            (8, 10),
        ]

        for dep_id, cmd_id in dependencies:
            commands[cmd_id].add_dependency(commands[dep_id])

        command_list = list(commands.values())
        sorted_commands = RCONCommand.topological_sort(command_list)

        assert sorted_commands is not None

        self.assertIsNotNone(sorted_commands)
        self.assertEqual(len(sorted_commands), 10)

        position = {cmd.command_id: i for i, cmd in enumerate(sorted_commands)}

        for cmd in sorted_commands:
            for dependency in cmd.dependencies:
                self.assertLess(
                    position[dependency.command_id],
                    position[cmd.command_id],
                    f"Dependency {dependency.command_id} should come before {cmd.command_id}",
                )

        for dep_id, cmd_id in dependencies:
            self.assertLess(
                position[dep_id],
                position[cmd_id],
                f"Command {dep_id} should come before command {cmd_id}",
            )

    async def test_topological_sort_complex_cycle_detection(self):
        """Test cycle detection in a larger graph with multiple potential cycles"""

        commands = {}
        for i in range(1, 11):
            commands[i] = RCONCommand.create(
                f"command{i}", self.user, command_id=i, require_result=True
            )

        dependencies = [
            (1, 2),
            (2, 3),
            (3, 1),
            (4, 5),
            (5, 6),
            (6, 4),
            (2, 4),
            (7, 8),
            (3, 7),
            (5, 9),
            (9, 10),
        ]

        for dep_id, cmd_id in dependencies:
            commands[cmd_id].add_dependency(commands[dep_id])

        with self.assertRaises(ValueError) as context:
            RCONCommand.topological_sort(list(commands.values()))

        self.assertIn("Cycle detected", str(context.exception))

    async def test_topological_sort_disconnected_components(self):
        """Test topological sorting with disconnected components"""

        commands = {}
        for i in range(1, 7):
            commands[i] = RCONCommand.create(
                f"command{i}", self.user, command_id=i, require_result=True
            )

        dependencies = [
            (1, 2),
            (2, 3),
            (4, 5),
        ]

        for dep_id, cmd_id in dependencies:
            commands[cmd_id].add_dependency(commands[dep_id])

        sorted_commands = RCONCommand.topological_sort(list(commands.values()))

        assert sorted_commands is not None
        self.assertEqual(len(sorted_commands), 6)

        position = {cmd.command_id: i for i, cmd in enumerate(sorted_commands)}

        for dep_id, cmd_id in dependencies:
            self.assertLess(
                position[dep_id],
                position[cmd_id],
                f"Command {dep_id} should come before command {cmd_id}",
            )
