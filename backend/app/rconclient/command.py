from asyncio import Future
from dataclasses import dataclass, field

from ..auth.user import User


@dataclass
class RCONCommand:
    command: str
    user: User
    future: Future | None = field(default=None, repr=False)
    error: str | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return (
            f"RCONCommand(command={self.command!r}, "
            f"user={self.user.username!r}, "
            f"future_set={self.future is not None})"
        )

    def set_command_result(self, result: str) -> None:
        """Set the result on the associated Future if one is present."""
        if self.future is not None and not self.future.done():
            self.future.set_result(result)

    def set_command_error(self, error: Exception) -> None:
        """Set an error on the associated Future if one is present."""
        self.error = str(error)
        if self.future is not None and not self.future.done():
            self.future.set_exception(Exception(str(error)))
