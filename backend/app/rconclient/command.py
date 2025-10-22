from asyncio import Future
from ..auth.user import User


class RCONCommand:
    def __init__(self, command: str, user: User, future: Future):
        self.command = command
        self.user = user
        self.future = future

    def __repr__(self):
        return f"RCONCommand(command={self.command}, user={self.user.username}, future={self.future})"

    def set_command_result(self, command_result: str) -> None:
        self.future.set_result(command_result)
