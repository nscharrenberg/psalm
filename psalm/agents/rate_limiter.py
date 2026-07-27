from __future__ import annotations

import asyncio
import time
from typing import Any

import tiktoken

_POLL_INTERVAL_SECONDS = 0.25
_DEFAULT_COMPLETION_TOKEN_ESTIMATE = 500
_FALLBACK_ENCODING = "cl100k_base"


class _RateLimiter:
    def __init__(
        self, max_requests_per_minute: int | None, max_tokens_per_minute: int | None,
    ) -> None:
        self._max_requests_per_minute = max_requests_per_minute
        self._max_tokens_per_minute = max_tokens_per_minute
        self._request_capacity = (
            float(max_requests_per_minute) if max_requests_per_minute is not None else None
        )
        self._token_capacity = (
            float(max_tokens_per_minute) if max_tokens_per_minute is not None else None
        )
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int) -> None:
        while True:
            async with self._lock:
                self._refill()
                request_ok = self._request_capacity is None or self._request_capacity >= 1.0
                token_ok = (
                    self._token_capacity is None or self._token_capacity >= estimated_tokens
                )
                if request_ok and token_ok:
                    if self._request_capacity is not None:
                        self._request_capacity -= 1.0
                    if self._token_capacity is not None:
                        self._token_capacity -= estimated_tokens
                    return
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        if self._max_requests_per_minute is not None:
            self._request_capacity = min(
                float(self._max_requests_per_minute),
                (self._request_capacity or 0.0) + elapsed * (self._max_requests_per_minute / 60.0),
            )
        if self._max_tokens_per_minute is not None:
            self._token_capacity = min(
                float(self._max_tokens_per_minute),
                (self._token_capacity or 0.0) + elapsed * (self._max_tokens_per_minute / 60.0),
            )


def estimate_tokens(messages: list[Any], model: str, max_completion_tokens: int | None) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding(_FALLBACK_ENCODING)
    text_parts = []
    for message in messages:
        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = getattr(message, "content", "")
        text_parts.append(str(content))
    prompt_tokens = len(encoding.encode(" ".join(text_parts)))
    completion_estimate = max_completion_tokens or _DEFAULT_COMPLETION_TOKEN_ESTIMATE
    return prompt_tokens + completion_estimate
