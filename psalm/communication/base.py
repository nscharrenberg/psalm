from abc import ABC, abstractmethod
from typing import Any


class MessageQueue(ABC):
    @abstractmethod
    async def post(self, message: dict[str, Any]) -> None: ...

    @abstractmethod
    def snapshot(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def clear(self) -> None: ...
