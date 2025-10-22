from enum import IntEnum


class Role(IntEnum):
    OWNER = 0
    ADMIN = 1
    USER = 2

    def check_permission(self, required_role: "Role") -> bool:
        return self.value <= required_role.value
