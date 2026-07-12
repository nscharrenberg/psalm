from __future__ import annotations

import asyncio
import itertools
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class PSALMEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    sequence: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str = ""
    dimension: str | None = None
    category: Literal["lifecycle", "argumentation", "deliberation", "verdict", "agent"]
    type: str


class EventSink:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._queue: asyncio.Queue[PSALMEvent] = asyncio.Queue()
        self._seq = itertools.count(1)

    async def put(self, event: PSALMEvent) -> None:
        stamped = event.model_copy(update={"run_id": self.run_id, "sequence": next(self._seq)})
        await self._queue.put(stamped)

    async def get(self) -> PSALMEvent:
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()
