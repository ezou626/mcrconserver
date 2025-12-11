"""Unit tests for the RCON client types module.

This module contains tests for the :class:`~app.rconclient.types.RCONCommand`
class, including dependency management and error handling.
"""

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from app.common.user import Role, User
from app.rconclient.command import RCONCommand

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def test_user() -> User:
    """Create a test user with admin role."""
    return User("testuser", role=Role.ADMIN)


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, Any]:
    """Create an isolated event loop for testing."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_rcon_command_creation_with_result(test_user: User) -> None:
    """Test RCONCommand creation with result future."""
    future = asyncio.get_event_loop().create_future()
    command = RCONCommand(command="list", user=test_user, result=future)
    command.set_command_result("Player count: 5")

    assert command.command == "list"
    assert command.user == test_user
    assert await command.get_command_result() == "Player count: 5"


@pytest.mark.asyncio
async def test_set_command_error_with_future(test_user: User) -> None:
    """Test setting command error when future exists and is awaited."""
    future = asyncio.get_event_loop().create_future()
    command = RCONCommand(command="list", user=test_user, result=future)
    error = RuntimeError("THIS IS A TEST EXCEPTION")

    command.set_command_error(error)

    with pytest.raises(RuntimeError):
        await command.get_command_result()


@pytest.mark.asyncio
async def test_add_dependency(test_user: User) -> None:
    """Test adding a dependency to an RCONCommand."""
    future1 = asyncio.get_event_loop().create_future()
    command1 = RCONCommand(command="list", user=test_user, result=future1)
    future2 = asyncio.get_event_loop().create_future()
    command2 = RCONCommand(command="say Hello", user=test_user, result=future2)
    command2.add_dependency(command1)

    assert command1 in command2.dependencies


@pytest.mark.asyncio
async def test_topological_sort_simple(test_user: User) -> None:
    """Verify a simple dependency chain."""
    future1 = asyncio.get_event_loop().create_future()
    command1 = RCONCommand(
        command="list",
        user=test_user,
        command_id=1,
        result=future1,
    )
    future2 = asyncio.get_event_loop().create_future()
    command2 = RCONCommand(
        command="say Hello",
        user=test_user,
        command_id=2,
        result=future2,
    )
    command2.add_dependency(command1)

    sorted_commands = RCONCommand.topological_sort([command2, command1])
    assert sorted_commands == [command1, command2]


@pytest.mark.asyncio
async def test_topological_sort_cycle(test_user: User) -> None:
    """Ensures that circular dependencies are properly detected."""
    future1 = asyncio.get_event_loop().create_future()
    command1 = RCONCommand(
        command="list",
        user=test_user,
        command_id=1,
        result=future1,
    )
    future2 = asyncio.get_event_loop().create_future()
    command2 = RCONCommand(
        command="say Hello",
        user=test_user,
        command_id=2,
        result=future2,
    )
    command1.add_dependency(command2)
    command2.add_dependency(command1)

    with pytest.raises(ValueError, match="Cycle detected"):
        RCONCommand.topological_sort([command1, command2])


@pytest.mark.asyncio
async def test_topological_sort_duplicate_ids(test_user: User) -> None:
    """Verifies that duplicate command IDs are detected."""
    future1 = asyncio.get_event_loop().create_future()
    command1 = RCONCommand(
        command="list",
        user=test_user,
        command_id=1,
        result=future1,
    )
    future2 = asyncio.get_event_loop().create_future()
    command2 = RCONCommand(
        command="say Hello",
        user=test_user,
        command_id=1,
        result=future2,
    )

    with pytest.raises(ValueError, match="Duplicate"):
        RCONCommand.topological_sort([command1, command2])


@pytest.mark.asyncio
async def test_topological_sort_large_graph(test_user: User) -> None:
    """Test topological sorting with a large, complex dependency graph."""
    commands: list[RCONCommand] = []
    for i in range(1, 11):
        future = asyncio.get_event_loop().create_future()
        commands.append(
            RCONCommand(
                command=f"command{i}",
                user=test_user,
                command_id=i,
                result=future,
            ),
        )

    # dependency, dependent
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
    assert len(sorted_commands) == len(commands)

    position = {cmd.command_id: i for i, cmd in enumerate(sorted_commands)}

    for cmd in sorted_commands:
        for dependency in cmd.dependencies:
            assert position[dependency.command_id] < position[cmd.command_id], (
                f"Dependency {dependency.command_id} comes before {cmd.command_id}"
            )

    for dep_id, cmd_id in dependencies:
        assert position[dep_id] < position[cmd_id], (
            f"Command {dep_id} comes before command {cmd_id}"
        )


@pytest.mark.asyncio
async def test_topological_sort_complex_cycle_detection(test_user: User) -> None:
    """Test cycle detection in a larger graph with multiple potential cycles."""
    commands: list[RCONCommand] = []
    for i in range(1, 11):
        future = asyncio.get_event_loop().create_future()
        commands.append(
            RCONCommand(
                command=f"command{i}",
                user=test_user,
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

    with pytest.raises(ValueError, match="Cycle detected") as exc_info:
        RCONCommand.topological_sort(commands)

    assert "Cycle detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_topological_sort_disconnected_components(test_user: User) -> None:
    """Test topological sorting with disconnected components."""
    commands: list[RCONCommand] = []
    for i in range(1, 7):
        future = asyncio.get_event_loop().create_future()
        commands.append(
            RCONCommand(
                command=f"command{i}",
                user=test_user,
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
    assert len(sorted_commands) == len(commands)

    position = {cmd.command_id: i for i, cmd in enumerate(sorted_commands)}

    for dep_id, cmd_id in dependencies:
        assert position[dep_id] < position[cmd_id], (
            f"Command {dep_id} should come before command {cmd_id}"
        )
