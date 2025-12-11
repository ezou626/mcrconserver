"""Tests for user-related functionality."""

import pytest

from app.common import Role


@pytest.fixture
def roles() -> tuple[Role, Role, Role]:
    """Create test roles."""
    return Role.OWNER, Role.ADMIN, Role.USER


def test_check_permission(roles: tuple[Role, Role, Role]) -> None:
    """Test role permissions."""
    owner, admin, user = roles

    assert owner.check_permission(Role.OWNER)
    assert owner.check_permission(Role.ADMIN)
    assert owner.check_permission(Role.USER)

    assert not admin.check_permission(Role.OWNER)
    assert admin.check_permission(Role.ADMIN)
    assert admin.check_permission(Role.USER)

    assert not user.check_permission(Role.OWNER)
    assert not user.check_permission(Role.ADMIN)
    assert user.check_permission(Role.USER)


def test_has_higher_permission(roles: tuple[Role, Role, Role]) -> None:
    """Test role hierarchy comparisons."""
    owner, admin, user = roles

    assert owner.has_higher_permission(admin)
    assert owner.has_higher_permission(user)
    assert not owner.has_higher_permission(owner)

    assert not admin.has_higher_permission(owner)
    assert admin.has_higher_permission(user)
    assert not admin.has_higher_permission(admin)

    assert not user.has_higher_permission(owner)
    assert not user.has_higher_permission(admin)
    assert not user.has_higher_permission(user)
