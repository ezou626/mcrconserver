from asyncio import Future
from dataclasses import dataclass, field

from ..auth.user import User


@dataclass
class RCONCommand:
    command: str
    user: User
    future: Future | None = field(default=None, repr=False)
    error: str | None = field(default=None)

    def set_command_result(self, result: str) -> None:
        """Set the result on the associated Future if one is present."""
        if self.future is not None and not self.future.done():
            self.future.set_result(result)

    def set_command_error(self, error: Exception) -> None:
        """Set an error on the associated Future if one is present."""
        self.error = str(error)
        if self.future is not None and not self.future.done():
            self.future.set_exception(Exception(str(error)))

    async def get_command_result(self) -> str | None:
        """Await and get the result from the associated Future if one is present.

        Returns:
            The result string if available, else None.

        Raises:
            Exception: If the command resulted in an error.
        """
        if self.future is not None:
            return await self.future
        return None
