from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from trials import TrialStore


async def stream_trial_events(
    store: TrialStore, trial_id: str, heartbeat_interval: float = 15.0
) -> AsyncIterator[str]:
    record = store.get(trial_id)
    if record is None:
        return

    index = 0
    while True:
        while index < len(record.events):
            yield f"data: {json.dumps(record.events[index])}\n\n"
            index += 1
        if record.status != "running":
            return
        async with record.condition:
            if index >= len(record.events) and record.status == "running":
                try:
                    await asyncio.wait_for(record.condition.wait(), timeout=heartbeat_interval)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
