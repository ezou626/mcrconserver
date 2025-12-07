"""Fundamental user data model for app."""

from enum import IntEnum


class Role(IntEnum):
    """User roles with hierarchical permissions."""

    OWNER = 0
    ADMIN = 1
    USER = 2

    def check_permission(self, required_role: Role) -> bool:
        """Check if the current role has permission for the required role.

        :param required_role: Description
        :return: True if the current role has permission, False otherwise
        """
        return self.value <= required_role.value


class UserBase:
    """Base class for user-related data structures."""

    username: str
    role: Role
