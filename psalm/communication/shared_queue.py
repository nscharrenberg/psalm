from __future__ import annotations

import asyncio
from typing import Any

from psalm.communication.base import MessageQueue


class SharedMessageQueue(MessageQueue):
    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def post(self, message: dict[str, Any]) -> None:
        async with self._lock:
            self._messages.append(message)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()
