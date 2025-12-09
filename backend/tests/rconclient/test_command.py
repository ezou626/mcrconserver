"""Unit tests for the RCON client types module.

This module contains comprehensive tests for the :class:`~app.rconclient.types.RCONCommand`
class, including dependency management, topological sorting, and error handling.
"""

import asyncio
import unittest

from app.src.common.user import Role, User
from app.src.rconclient.command import RCONCommand


class TestRCONCommand(unittest.IsolatedAsyncioTestCase):
    """Test suite for the :class:`app.rconclient.types.RCONCommand` class.

    :cvar user: Test user fixture with admin role
    :cvar loop: Asyncio event loop for test isolation
    """

    def setUp(self):
        """Set up test fixtures and environment.

        Creates a test user with admin privileges and initializes a new
        asyncio event loop for test isolation.
        """
        self.user = User("testuser", role=Role.ADMIN)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Clean up test environment.

        Properly closes the asyncio event loop to prevent resource leaks.
        """
        self.loop.close()

    async def test_rcon_command_creation_with_result(self):
        """Test RCONCommand creation with result future."""
        future = asyncio.get_event_loop().create_future()
        command = RCONCommand(command="list", user=self.user, result=future)
        command.set_command_result("Player count: 5")

        self.assertEqual(command.command, "list")
        self.assertEqual(command.user, self.user)
        self.assertEqual(await command.get_command_result(), "Player count: 5")

    async def test_set_command_error_with_future(self):
        """Test setting command error when future exists and is awaited."""
        future = asyncio.get_event_loop().create_future()
        command = RCONCommand(command="list", user=self.user, result=future)
        error = Exception("THIS IS A TEST EXCEPTION")

        command.set_command_error(error)

        with self.assertRaises(Exception):
            await command.get_command_result()

    async def test_add_dependency(self):
        """Test adding a dependency to an RCONCommand."""
        future1 = asyncio.get_event_loop().create_future()
        command1 = RCONCommand(command="list", user=self.user, result=future1)
        future2 = asyncio.get_event_loop().create_future()
        command2 = RCONCommand(command="say Hello", user=self.user, result=future2)
        command2.add_dependency(command1)

        self.assertIn(command1, command2.dependencies)

    async def test_topological_sort_simple(self):
        """Verifies that a simple dependency chain
        is correctly sorted with dependencies appearing first.
        """
        future1 = asyncio.get_event_loop().create_future()
        command1 = RCONCommand(
            command="list",
            user=self.user,
            command_id=1,
            result=future1,
        )
        future2 = asyncio.get_event_loop().create_future()
        command2 = RCONCommand(
            command="say Hello",
            user=self.user,
            command_id=2,
            result=future2,
        )
        command2.add_dependency(command1)

        sorted_commands = RCONCommand.topological_sort([command2, command1])
        self.assertEqual(sorted_commands, [command1, command2])

    async def test_topological_sort_cycle(self):
        """Ensures that circular dependencies are properly detected
        and result in a :exc:`ValueError` being raised.
        """
        future1 = asyncio.get_event_loop().create_future()
        command1 = RCONCommand(
            command="list",
            user=self.user,
            command_id=1,
            result=future1,
        )
        future2 = asyncio.get_event_loop().create_future()
        command2 = RCONCommand(
            command="say Hello",
            user=self.user,
            command_id=2,
            result=future2,
        )
        command1.add_dependency(command2)
        command2.add_dependency(command1)

        with self.assertRaises(ValueError):
            RCONCommand.topological_sort([command1, command2])

    async def test_topological_sort_duplicate_ids(self):
        """Verifies that duplicate command IDs are detected"""
        future1 = asyncio.get_event_loop().create_future()
        command1 = RCONCommand(
            command="list",
            user=self.user,
            command_id=1,
            result=future1,
        )
        future2 = asyncio.get_event_loop().create_future()
        command2 = RCONCommand(
            command="say Hello",
            user=self.user,
            command_id=1,
            result=future2,
        )

        with self.assertRaises(ValueError):
            RCONCommand.topological_sort([command1, command2])

    async def test_topological_sort_large_graph(self):
        """Test topological sorting with a large, complex dependency graph."""
        commands: list[RCONCommand] = []
        for i in range(1, 11):
            future = asyncio.get_event_loop().create_future()
            commands.append(
                RCONCommand(
                    command=f"command{i}",
                    user=self.user,
                    command_id=i,
                    result=future,
                ),
            )

        # (dependency, dependent)
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
            commands[cmd_id - 1].add_dependency(commands[dep_id - 1])

        command_list = list(commands)
        sorted_commands = RCONCommand.topological_sort(command_list)

        # raw assert for Ruff
        assert sorted_commands is not None
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
        """Test cycle detection in a larger graph with multiple potential cycles."""
        commands: list[RCONCommand] = []
        for i in range(1, 11):
            future = asyncio.get_event_loop().create_future()
            commands.append(
                RCONCommand(
                    command=f"command{i}",
                    user=self.user,
                    command_id=i,
                    result=future,
                ),
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
            commands[cmd_id - 1].add_dependency(commands[dep_id - 1])

        with self.assertRaises(ValueError) as context:
            RCONCommand.topological_sort(commands)

        self.assertIn("Cycle detected", str(context.exception))

    async def test_topological_sort_disconnected_components(self):
        """Test topological sorting with disconnected components."""
        commands: list[RCONCommand] = []
        for i in range(1, 7):
            future = asyncio.get_event_loop().create_future()
            commands.append(
                RCONCommand(
                    command=f"command{i}",
                    user=self.user,
                    command_id=i,
                    result=future,
                ),
            )

        dependencies = [
            (1, 2),
            (2, 3),
            (4, 5),
        ]

        for dep_id, cmd_id in dependencies:
            commands[cmd_id - 1].add_dependency(commands[dep_id - 1])

        sorted_commands = RCONCommand.topological_sort(commands)

        # raw assert for Ruff
        assert sorted_commands is not None
        self.assertEqual(len(sorted_commands), 6)

        position = {cmd.command_id: i for i, cmd in enumerate(sorted_commands)}

        for dep_id, cmd_id in dependencies:
            self.assertLess(
                position[dep_id],
                position[cmd_id],
                f"Command {dep_id} should come before command {cmd_id}",
            )
