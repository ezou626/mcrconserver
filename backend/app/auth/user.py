from .roles import Role


class User:
    def __init__(self, username: str, role: Role):
        self.username = username
        self.role = role
