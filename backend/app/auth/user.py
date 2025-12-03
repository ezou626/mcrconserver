"""Fundamental user data structure."""

from dataclasses import dataclass
from .roles import Role


@dataclass
class User:
    username: str
    role: Role
