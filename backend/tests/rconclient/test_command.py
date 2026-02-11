"""Unit tests for the RCON client types module.

This module contains tests for the :class:`~backend.rconclient.command.RCONCommand`
class, including dependency management and error handling.
"""

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from backend.common.user import Role, User
from backend.rconclient.command import RCONCommand, RCONCommandSpecification

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
    future = asyncio.get_running_loop().create_future()
    command = RCONCommand(command="list", user=test_user, result=future)
    command.set_command_result("Player count: 5")

    assert command.command == "list"
    assert command.user == test_user
    assert await command.get_command_result() == "Player count: 5"


@pytest.mark.asyncio
async def test_set_command_error_with_future(test_user: User) -> None:
    """Test setting command error when future exists and is awaited."""
    future = asyncio.get_running_loop().create_future()
    command = RCONCommand(command="list", user=test_user, result=future)
    error = RuntimeError("THIS IS A TEST EXCEPTION")

    command.set_command_error(error)

    with pytest.raises(RuntimeError):
        await command.get_command_result()


@pytest.mark.asyncio
async def test_add_dependency(test_user: User) -> None:
    """Test adding a dependency to an RCONCommand."""
    future1 = asyncio.get_running_loop().create_future()
    command1 = RCONCommand(command="list", user=test_user, result=future1)
    future2 = asyncio.get_running_loop().create_future()
    command2 = RCONCommand(command="say Hello", user=test_user, result=future2)
    command2.add_dependency(command1)

    assert command1 in command2.dependencies


@pytest.mark.asyncio
async def test_create_job_from_specification_simple(test_user: User) -> None:
    """Test creating job with simple dependencies."""
    specs = [
        RCONCommandSpecification(id=1, cmd="setup"),
        RCONCommandSpecification(id=2, cmd="action", dependencies=[1]),
    ]

    commands = list(RCONCommand.create_job_from_specification(specs, test_user))
    by_id = {c.command_id: c for c in commands}

    assert len(commands) == 2  # noqa: PLR2004
    assert len(by_id[2].dependencies) == 1
    assert by_id[2].dependencies[0].command_id == 1
    assert by_id[1].command == "setup"
    assert by_id[2].command == "action"


@pytest.mark.asyncio
async def test_create_job_from_specification_complex(test_user: User) -> None:
    """Test create_job_from_specification with more complex dependencies."""
    specs = [
        RCONCommandSpecification(id=1, cmd="setup"),
        RCONCommandSpecification(id=2, cmd="action1", dependencies=[1]),
        RCONCommandSpecification(id=3, cmd="action2", dependencies=[1]),
        RCONCommandSpecification(id=4, cmd="cleanup", dependencies=[2, 3]),
    ]

    commands = RCONCommand.create_job_from_specification(specs, test_user)
    by_id = {c.command_id: c for c in commands}

    # Check all edges exist
    assert len(by_id[2].dependencies) == 1
    assert by_id[2].dependencies[0].command_id == 1
    assert len(by_id[3].dependencies) == 1
    assert by_id[3].dependencies[0].command_id == 1
    assert len(by_id[4].dependencies) == 2  # noqa: PLR2004
    assert {d.command_id for d in by_id[4].dependencies} == {2, 3}


@pytest.mark.asyncio
async def test_topological_sort_simple(test_user: User) -> None:
    """Verify a simple dependency chain."""
    specs = [
        RCONCommandSpecification(id=1, cmd="list"),
        RCONCommandSpecification(id=2, cmd="say Hello", dependencies=[1]),
    ]
    commands = RCONCommand.create_job_from_specification(specs, test_user)

    sorted_commands = RCONCommand.topological_sort(commands)
    assert [c.command_id for c in sorted_commands] == [1, 2]


@pytest.mark.asyncio
async def test_topological_sort_cycle(test_user: User) -> None:
    """Ensures that circular dependencies are properly detected."""
    specs = [
        RCONCommandSpecification(id=1, cmd="list", dependencies=[2]),
        RCONCommandSpecification(id=2, cmd="say Hello", dependencies=[1]),
    ]
    commands = RCONCommand.create_job_from_specification(specs, test_user)

    with pytest.raises(ValueError, match=r"cycle|Cycle"):
        RCONCommand.topological_sort(commands)


@pytest.mark.asyncio
async def test_topological_sort_duplicate_ids(test_user: User) -> None:
    """Verifies that duplicate command IDs are detected."""
    specs = [
        RCONCommandSpecification(id=1, cmd="list", dependencies=[]),
        RCONCommandSpecification(id=1, cmd="say Hello", dependencies=[]),
    ]

    with pytest.raises(ValueError, match=r"duplicate|Duplicate"):
        RCONCommand.create_job_from_specification(specs, test_user)


@pytest.mark.asyncio
async def test_topological_sort_large_graph(test_user: User) -> None:
    """Test topological sorting with a large, complex dependency graph."""
    specs = [
        RCONCommandSpecification(id=1, cmd="command1"),
        RCONCommandSpecification(id=2, cmd="command2"),
        RCONCommandSpecification(id=3, cmd="command3", dependencies=[1]),
        RCONCommandSpecification(id=4, cmd="command4", dependencies=[1, 2]),
        RCONCommandSpecification(id=5, cmd="command5", dependencies=[2]),
        RCONCommandSpecification(id=6, cmd="command6", dependencies=[3]),
        RCONCommandSpecification(id=7, cmd="command7", dependencies=[3, 4]),
        RCONCommandSpecification(id=8, cmd="command8", dependencies=[4, 5]),
        RCONCommandSpecification(id=9, cmd="command9", dependencies=[6, 7]),
        RCONCommandSpecification(id=10, cmd="command10", dependencies=[7, 8]),
    ]

    commands = RCONCommand.create_job_from_specification(specs, test_user)
    sorted_commands = RCONCommand.topological_sort(commands)

    assert len(sorted_commands) == len(specs)

    position = {cmd.command_id: i for i, cmd in enumerate(sorted_commands)}

    for cmd in sorted_commands:
        for dependency in cmd.dependencies:
            assert position[dependency.command_id] < position[cmd.command_id], (
                f"Dependency {dependency.command_id} comes before {cmd.command_id}"
            )


@pytest.mark.asyncio
async def test_topological_sort_complex_cycle_detection(test_user: User) -> None:
    """Test cycle detection in a larger graph with multiple potential cycles."""
    specs = [
        RCONCommandSpecification(id=1, cmd="command1", dependencies=[2]),
        RCONCommandSpecification(id=2, cmd="command2", dependencies=[3]),
        RCONCommandSpecification(id=3, cmd="command3", dependencies=[4]),
        RCONCommandSpecification(id=4, cmd="command3", dependencies=[5, 1]),
        RCONCommandSpecification(id=5, cmd="command3", dependencies=[1, 3]),
        RCONCommandSpecification(id=6, cmd="command3", dependencies=[2]),
    ]

    commands = RCONCommand.create_job_from_specification(specs, test_user)

    with pytest.raises(ValueError, match="Cycle detected") as exc_info:
        RCONCommand.topological_sort(commands)

    assert "Cycle detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_topological_sort_disconnected_components(test_user: User) -> None:
    """Test topological sorting with disconnected components."""
    specs = [
        RCONCommandSpecification(id=1, cmd="command1"),
        RCONCommandSpecification(id=2, cmd="command2", dependencies=[1]),
        RCONCommandSpecification(id=3, cmd="command3", dependencies=[2]),
        RCONCommandSpecification(id=4, cmd="command4"),
        RCONCommandSpecification(id=5, cmd="command5", dependencies=[4]),
        RCONCommandSpecification(id=6, cmd="command6"),
    ]

    commands = list(RCONCommand.create_job_from_specification(specs, test_user))
    sorted_commands = RCONCommand.topological_sort(commands)

    assert len(sorted_commands) == len(specs)

    position = {cmd.command_id: i for i, cmd in enumerate(sorted_commands)}

    # Check the dependencies that exist
    assert position[1] < position[2], "Command 1 should come before command 2"
    assert position[2] < position[3], "Command 2 should come before command 3"
    assert position[4] < position[5], "Command 4 should come before command 5"
