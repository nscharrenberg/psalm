import asyncio
from unittest.mock import patch

import pytest

from psalm.agents.rate_limiter import (
    _DEFAULT_COMPLETION_TOKEN_ESTIMATE,
    _RateLimiter,
    estimate_tokens,
)


def test_estimate_tokens_known_model():
    tokens = estimate_tokens(
        messages=[{"role": "user", "content": "hello world"}],
        model="gpt-4o-mini",
        max_completion_tokens=None,
    )
    assert tokens > _DEFAULT_COMPLETION_TOKEN_ESTIMATE
    assert tokens < _DEFAULT_COMPLETION_TOKEN_ESTIMATE + 20


def test_estimate_tokens_unknown_model_falls_back_to_cl100k_base():
    tokens = estimate_tokens(
        messages=[{"role": "user", "content": "hello world"}],
        model="some-third-party-model-xyz",
        max_completion_tokens=None,
    )
    assert tokens > 0


def test_estimate_tokens_uses_max_completion_tokens_when_set():
    tokens_with_override = estimate_tokens(
        messages=[{"role": "user", "content": "hi"}], model="gpt-4o-mini", max_completion_tokens=50,
    )
    tokens_default = estimate_tokens(
        messages=[{"role": "user", "content": "hi"}], model="gpt-4o-mini", max_completion_tokens=None,
    )
    assert tokens_with_override < tokens_default


async def test_rate_limiter_respects_request_cap():
    limiter = _RateLimiter(max_requests_per_minute=1, max_tokens_per_minute=None)
    await limiter.acquire(10)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire(10), timeout=0.05)


async def test_rate_limiter_respects_token_cap():
    limiter = _RateLimiter(max_requests_per_minute=None, max_tokens_per_minute=100)
    await limiter.acquire(90)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire(50), timeout=0.05)


async def test_rate_limiter_disabled_never_blocks():
    limiter = _RateLimiter(max_requests_per_minute=None, max_tokens_per_minute=None)
    await asyncio.wait_for(
        asyncio.gather(*[limiter.acquire(1000) for _ in range(50)]), timeout=0.1,
    )


async def test_rate_limiter_refill_replenishes_capacity_over_simulated_time():
    # Exhausts the single unit of capacity with max_requests_per_minute=1, then jumps the
    # mocked clock forward by a full 60s BEFORE the second acquire — so that second acquire
    # resolves on its first lock-check (capacity is already refilled to 1.0 by the time it's
    # called) rather than needing to actually poll/sleep while time.monotonic is frozen. This
    # matters because patch("psalm.agents.rate_limiter.time.monotonic", ...) patches the
    # shared `time` module object process-wide (Python modules are singletons), which also
    # freezes asyncio's own internal clock — if a call under this patch genuinely needed to
    # block and rely on asyncio.wait_for's timeout firing, the frozen clock would make that
    # timeout never arrive, hanging the test indefinitely instead of failing cleanly.
    fake_time = [0.0]

    def fake_monotonic():
        return fake_time[0]

    with patch("psalm.agents.rate_limiter.time.monotonic", side_effect=fake_monotonic):
        limiter = _RateLimiter(max_requests_per_minute=1, max_tokens_per_minute=None)
        await limiter.acquire(1)
        fake_time[0] = 60.0
        await asyncio.wait_for(limiter.acquire(1), timeout=0.5)
