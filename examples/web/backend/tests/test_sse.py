import asyncio
import json

from sse import stream_trial_events
from trials import TrialStore


async def test_stream_replays_backlog_immediately():
    store = TrialStore()
    record = store.create("s", "t", {})
    await store.append_event(record.id, {"type": "run_started"})
    await store.append_event(record.id, {"type": "final_verdict_reached"})
    await store.mark_done(record.id, {"verdict": "Guilty"})

    messages = [msg async for msg in stream_trial_events(store, record.id) if msg.startswith("data: ")]
    parsed = [json.loads(m[len("data: "):]) for m in messages]
    assert parsed == [{"type": "run_started"}, {"type": "final_verdict_reached"}]


async def test_stream_yields_new_events_as_they_arrive():
    store = TrialStore()
    record = store.create("s", "t", {})

    async def producer() -> None:
        await asyncio.sleep(0.05)
        await store.append_event(record.id, {"type": "run_started"})
        await asyncio.sleep(0.05)
        await store.mark_done(record.id, {"verdict": "Guilty"})

    producer_task = asyncio.create_task(producer())
    collected = [msg async for msg in stream_trial_events(store, record.id) if msg.startswith("data: ")]
    await producer_task
    parsed = [json.loads(m[len("data: "):]) for m in collected]
    assert parsed == [{"type": "run_started"}]


async def test_stream_sends_heartbeat_when_idle():
    store = TrialStore()
    record = store.create("s", "t", {})

    async def eventually_finish() -> None:
        await asyncio.sleep(0.3)
        await store.mark_done(record.id, {"verdict": "Guilty"})

    asyncio.create_task(eventually_finish())
    messages = [msg async for msg in stream_trial_events(store, record.id, heartbeat_interval=0.05)]
    assert any(m.startswith(": keep-alive") for m in messages)


async def test_stream_returns_nothing_for_unknown_trial():
    store = TrialStore()
    messages = [msg async for msg in stream_trial_events(store, "nonexistent")]
    assert messages == []
