"""Tests for user-related functionality."""

import pytest  # noqa: F401

from app.src.common import Role


def test_check_permission() -> None:
    """Test owner permissions."""
    owner = Role.OWNER
    admin = Role.ADMIN
    user = Role.USER

    assert owner.check_permission(Role.OWNER)
    assert owner.check_permission(Role.ADMIN)
    assert owner.check_permission(Role.USER)

    assert not admin.check_permission(Role.OWNER)
    assert admin.check_permission(Role.ADMIN)
    assert admin.check_permission(Role.USER)

    assert not user.check_permission(Role.OWNER)
    assert not user.check_permission(Role.ADMIN)
    assert user.check_permission(Role.USER)


def test_has_higher_permission() -> None:
    """Test role hierarchy comparisons."""
    owner = Role.OWNER
    admin = Role.ADMIN
    user = Role.USER

    assert owner.has_higher_permission(admin)
    assert owner.has_higher_permission(user)
    assert not owner.has_higher_permission(owner)

    assert not admin.has_higher_permission(owner)
    assert admin.has_higher_permission(user)
    assert not admin.has_higher_permission(admin)

    assert not user.has_higher_permission(owner)
    assert not user.has_higher_permission(admin)
    assert not user.has_higher_permission(user)
