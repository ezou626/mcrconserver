from asyncio import Future, get_event_loop
from dataclasses import dataclass, field

from ..auth.user import User


@dataclass
class RCONCommand:
    command: str
    user: User
    _result: Future | None = field(default=None, repr=False)
    error: str | None = field(default=None)

    def __init__(self, command: str, user: User, require_result: bool = True) -> None:
        self.command = command
        self.user = user
        if require_result:
            self._result = get_event_loop().create_future()
        else:
            self._result = None
        self.error = None

    def set_command_result(self, result: str) -> None:
        """Set the result on the associated Future if one is present.

        Args:
            result: The result of the command from the Minecraft server.
        """
        if self._result is not None and not self._result.done():
            self._result.set_result(result)

    def set_command_error(self, error: Exception) -> None:
        """Set an error on the associated Future if one is present.

        Args:
            error: The exception that occurred while processing the command.
        """
        self.error = str(error)
        if self._result is not None and not self._result.done():
            self._result.set_exception(Exception(str(error)))

    async def get_command_result(self) -> str | None:
        """Await and get the result from the associated Future if one is present.

        Returns:
            The result string if available, else None.

        Raises:
            Exception: If the command resulted in an error.
        """
        if self._result is not None:
            return await self._result
        return None
