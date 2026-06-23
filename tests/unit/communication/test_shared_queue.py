import asyncio
import pytest
from psalm.communication.shared_queue import SharedMessageQueue


async def test_post_and_snapshot():
    queue = SharedMessageQueue()
    await queue.post({"role": "prosecutor", "content": "Argument 1"})
    await queue.post({"role": "defense", "content": "Counter 1"})
    snapshot = queue.snapshot()
    assert len(snapshot) == 2
    assert snapshot[0]["role"] == "prosecutor"


async def test_snapshot_is_copy():
    queue = SharedMessageQueue()
    await queue.post({"role": "prosecutor", "content": "Arg"})
    snap = queue.snapshot()
    snap.append({"role": "intruder", "content": "injected"})
    assert len(queue.snapshot()) == 1  # original unmodified


async def test_concurrent_posts():
    queue = SharedMessageQueue()

    async def post_many(n: int) -> None:
        for i in range(n):
            await queue.post({"index": i})

    await asyncio.gather(post_many(50), post_many(50))
    assert len(queue.snapshot()) == 100


async def test_clear():
    queue = SharedMessageQueue()
    await queue.post({"content": "msg"})
    queue.clear()
    assert queue.snapshot() == []
