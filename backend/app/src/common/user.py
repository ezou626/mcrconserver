"""Fundamental user data model for app"""

from dataclasses import dataclass
from enum import IntEnum


class Role(IntEnum):
    """User roles with hierarchical permissions."""

    OWNER = 0
    ADMIN = 1
    USER = 2

    def check_permission(self, required_role: "Role") -> bool:
        return self.value <= required_role.value


@dataclass
class User:
    """Data structure representing a user."""

    username: str
    role: Role
