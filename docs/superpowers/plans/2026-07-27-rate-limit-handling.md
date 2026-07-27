# Rate-Limit Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** fix `Trial failed: Structured LLM retry limit reached after 3 attempts.` recurring on full-dimension trials by adding real RPM/TPM-aware request pacing, `Retry-After`-aware backoff (with a configurable fallback for providers that don't send it), retry-vs-fail-fast error classification, and proper logging — all exposed through the existing `ExecutionConfig`/`PSALM.with_execution(...)` surface and the web app's Advanced settings.

**Architecture:** a new `_RateLimiter` (dual token-bucket, RPM + TPM, `tiktoken`-based estimation) lives in a new `psalm/agents/rate_limiter.py` module, reached via `_RunExecution.rate_limiter()` following the exact lazy-per-running-event-loop-cache pattern already used for `.semaphore()`. `BaseAgent._call_llm`/`_call_structured` are refactored to share one `_execute_with_retry` helper that: paces via the rate limiter, classifies each caught exception as retry-vs-fail-fast, computes backoff with `Retry-After`-header priority over a configured fallback over the existing jittered-exponential default, and logs every retry/failure via the standard `logging` module.

**Tech Stack:** Python 3.14, `tiktoken` (new direct dependency, already transitively installed), `openai`'s exception hierarchy (`RateLimitError`/`AuthenticationError`/`PermissionDeniedError`/`BadRequestError`), Pydantic v2; TypeScript/React/Mantine + FastAPI for the demo web app.

## Global Constraints

- Token debiting is **estimate-only** — no post-call true-up against actual usage, since no real call site in this codebase uses `include_raw=True` (verified: `_call_llm` has zero production callers; every real call goes through `_call_structured`). The bucket's continuous refill self-corrects for estimate drift over time.
- `_RateLimiter`'s internal `asyncio.Lock` must be created lazily per running event loop (same pattern as the semaphore fix), reached only via `_RunExecution.rate_limiter()`, never constructed once and reused across loops.
- `ExecutionConfig` new-field defaults: `max_requests_per_minute=60`, `max_tokens_per_minute=40000` (always-on, conservative), `retry_after_fallback_seconds=None` (off — no fallback needed when a provider does send the header).
- `_RunExecution`'s three new dataclass fields default to `None` (distinct from `ExecutionConfig`'s defaults) so every existing test that constructs `_RunExecution(...)` directly (6 call sites across `tests/unit/agents/test_base.py` and `tests/unit/test_builder.py`) keeps working unchanged — production code (`PSALM.build()`) always passes explicit values from `self._execution_config`, so the dataclass-level default only matters for test convenience.
- Error classification is **additive to today's catch-all**, never a replacement allowlist: any exception not explicitly classified (`_ErrorClassification(True, "unknown", "")`) retries exactly as it does today.
- Fail-fast classifications: `openai.AuthenticationError`, `openai.PermissionDeniedError`, `openai.BadRequestError`, and `openai.RateLimitError` specifically when `.code`/`.type` contains `"insufficient_quota"`. New error code `PSALM-A004` for this path, distinct from the existing `PSALM-A003` (retry-exhausted).
- `Retry-After` clamped to `_MAX_BACKOFF_SECONDS = 120.0` when read from the (untrusted, provider-controlled) response header; the user-configured `retry_after_fallback_seconds` is used as-is, not clamped.
- The web form's "disabled" convention for the three new rate-limit fields is `0` (not `None` — doesn't map onto a Mantine `NumberInput`); `examples/web/backend/execution.py`'s `build_psalm` translates `0 → None` before forwarding to `.with_execution(...)`.
- No changes to `psalm/courtroom/default.py`, `psalm/phases/deliberation.py`, or `PSALM.build()`'s `_ping_llm`/`_ping_all_llms` retry logic beyond `_RunExecution`'s new fields existing — the ping path does not gain rate limiting, `Retry-After` awareness, or error classification (deliberately out of scope: pings are single-token, one-shot per build, negligible RPM/TPM burden, and extending would require importing classification/backoff logic across a module boundary for no meaningful benefit).
- SDK test suite baseline before Task 1: `384 passed, 1 skipped` (confirmed via `python -m pytest tests/ -q` on a clean `v2` checkout). Web backend baseline: `64 passed`. Web frontend baseline: `90 passed` across 14 files.

---

## Task 1: `_RateLimiter` and `estimate_tokens`

**Files:**
- Create: `psalm/agents/rate_limiter.py`
- Test: `tests/unit/agents/test_rate_limiter.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `psalm.agents.rate_limiter._RateLimiter(max_requests_per_minute: int | None, max_tokens_per_minute: int | None)` with `async def acquire(self, estimated_tokens: int) -> None`. `psalm.agents.rate_limiter.estimate_tokens(messages: list[Any], model: str, max_completion_tokens: int | None) -> int`. Both consumed by Task 3/4, not yet wired into any agent.

- [ ] **Step 1: Add `tiktoken` as a direct dependency**

In `pyproject.toml`, change:
```toml
dependencies = [
    "langgraph>=1.2.6",
    "langchain>=1.3.10",
    "langchain-openai>=0.3.0",
    "pydantic>=2.13.4",
]
```
to:
```toml
dependencies = [
    "langgraph>=1.2.6",
    "langchain>=1.3.10",
    "langchain-openai>=0.3.0",
    "pydantic>=2.13.4",
    "tiktoken>=0.13.0",
]
```
`tiktoken` is already installed (transitive dependency of `langchain-openai`) — this only makes the direct dependency explicit, no install step is needed to proceed with the rest of this task.

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/agents/test_rate_limiter.py`:
```python
import asyncio
from unittest.mock import patch

import pytest

from psalm.agents.rate_limiter import _DEFAULT_COMPLETION_TOKEN_ESTIMATE, _RateLimiter, estimate_tokens


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


async def test_rate_limiter_blocks_until_capacity_available():
    fake_time = [0.0]

    def fake_monotonic():
        return fake_time[0]

    with patch("psalm.agents.rate_limiter.time.monotonic", side_effect=fake_monotonic):
        limiter = _RateLimiter(max_requests_per_minute=60, max_tokens_per_minute=None)
        await limiter.acquire(1)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(limiter.acquire(1), timeout=0.05)


async def test_rate_limiter_refill_replenishes_capacity_over_simulated_time():
    fake_time = [0.0]

    def fake_monotonic():
        return fake_time[0]

    with patch("psalm.agents.rate_limiter.time.monotonic", side_effect=fake_monotonic):
        limiter = _RateLimiter(max_requests_per_minute=60, max_tokens_per_minute=None)
        await limiter.acquire(1)
        fake_time[0] = 1.0
        await asyncio.wait_for(limiter.acquire(1), timeout=0.5)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_rate_limiter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'psalm.agents.rate_limiter'`

- [ ] **Step 4: Create `psalm/agents/rate_limiter.py`**

```python
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
        content = (
            message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
        )
        text_parts.append(str(content))
    prompt_tokens = len(encoding.encode(" ".join(text_parts)))
    completion_estimate = max_completion_tokens or _DEFAULT_COMPLETION_TOKEN_ESTIMATE
    return prompt_tokens + completion_estimate
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_rate_limiter.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 6: Run the full suite to confirm nothing else broke**

Run: `python -m pytest tests/ -q`
Expected: `392 passed, 1 skipped` (384 baseline + 8 new tests)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml psalm/agents/rate_limiter.py tests/unit/agents/test_rate_limiter.py
git commit -m "feat: add RPM/TPM token-bucket rate limiter"
```

---

## Task 2: Error Classification and Retry-After-Aware Backoff

**Files:**
- Modify: `psalm/agents/base.py`
- Test: `tests/unit/agents/test_base.py`

**Interfaces:**
- Produces: `psalm.agents.base._ErrorClassification` (dataclass: `retryable: bool`, `reason: str`, `suggestion: str`), `psalm.agents.base._classify_error(exc: Exception) -> _ErrorClassification`, `psalm.agents.base._extract_retry_after(exc: Exception) -> float | None`, `psalm.agents.base._compute_backoff(exc: Exception, attempt: int, backoff_factor: float, fallback_seconds: float | None) -> float`, `psalm.agents.base._MAX_BACKOFF_SECONDS: float`. None of these are wired into the retry loop yet (Task 4).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/agents/test_base.py`:
```python
import httpx
import openai


def _make_status_error(cls, status_code: int, body: dict | None = None, headers: dict | None = None):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code, request=request, headers=headers or {})
    return cls("error", response=response, body=body)


def _make_rate_limit_error(code: str = "rate_limit_exceeded", retry_after: str | None = None):
    headers = {"retry-after": retry_after} if retry_after else {}
    return _make_status_error(
        openai.RateLimitError, 429, body={"code": code, "type": code}, headers=headers,
    )


def test_classify_error_authentication_error_fails_fast():
    from psalm.agents.base import _classify_error
    exc = _make_status_error(openai.AuthenticationError, 401)
    result = _classify_error(exc)
    assert result.retryable is False
    assert result.reason == "authentication_error"


def test_classify_error_permission_denied_fails_fast():
    from psalm.agents.base import _classify_error
    exc = _make_status_error(openai.PermissionDeniedError, 403)
    result = _classify_error(exc)
    assert result.retryable is False
    assert result.reason == "permission_denied"


def test_classify_error_bad_request_fails_fast():
    from psalm.agents.base import _classify_error
    exc = _make_status_error(openai.BadRequestError, 400)
    result = _classify_error(exc)
    assert result.retryable is False
    assert result.reason == "bad_request"


def test_classify_error_insufficient_quota_fails_fast():
    from psalm.agents.base import _classify_error
    exc = _make_rate_limit_error(code="insufficient_quota")
    result = _classify_error(exc)
    assert result.retryable is False
    assert result.reason == "insufficient_quota"


def test_classify_error_genuine_rate_limit_is_retryable():
    from psalm.agents.base import _classify_error
    exc = _make_rate_limit_error(code="rate_limit_exceeded")
    result = _classify_error(exc)
    assert result.retryable is True
    assert result.reason == "rate_limited"


def test_classify_error_unknown_exception_is_retryable():
    from psalm.agents.base import _classify_error
    result = _classify_error(Exception("some transient network blip"))
    assert result.retryable is True
    assert result.reason == "unknown"


def test_extract_retry_after_reads_header():
    from psalm.agents.base import _extract_retry_after
    exc = _make_rate_limit_error(retry_after="30")
    assert _extract_retry_after(exc) == 30.0


def test_extract_retry_after_returns_none_when_absent():
    from psalm.agents.base import _extract_retry_after
    exc = _make_rate_limit_error()
    assert _extract_retry_after(exc) is None


def test_extract_retry_after_returns_none_for_exception_without_response():
    from psalm.agents.base import _extract_retry_after
    assert _extract_retry_after(Exception("boom")) is None


def test_compute_backoff_prefers_retry_after_header():
    from psalm.agents.base import _compute_backoff
    exc = _make_rate_limit_error(retry_after="5")
    wait = _compute_backoff(exc, attempt=0, backoff_factor=2.0, fallback_seconds=99.0)
    assert wait == 5.0


def test_compute_backoff_clamps_retry_after_to_max():
    from psalm.agents.base import _MAX_BACKOFF_SECONDS, _compute_backoff
    exc = _make_rate_limit_error(retry_after="99999")
    wait = _compute_backoff(exc, attempt=0, backoff_factor=2.0, fallback_seconds=None)
    assert wait == _MAX_BACKOFF_SECONDS


def test_compute_backoff_uses_fallback_when_header_absent():
    from psalm.agents.base import _compute_backoff
    exc = _make_rate_limit_error()
    wait = _compute_backoff(exc, attempt=0, backoff_factor=2.0, fallback_seconds=7.5)
    assert wait == 7.5


def test_compute_backoff_uses_jittered_exponential_when_neither_available():
    from psalm.agents.base import _compute_backoff
    wait = _compute_backoff(Exception("boom"), attempt=1, backoff_factor=2.0, fallback_seconds=None)
    assert 0 <= wait <= 2.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_base.py -k "classify_error or extract_retry_after or compute_backoff" -v`
Expected: FAIL with `ImportError: cannot import name '_classify_error'`

- [ ] **Step 3: Add classification and backoff functions to `psalm/agents/base.py`**

Add `import openai` to the top-level imports (alphabetically, after `import asyncio` and before `import random`):
```python
import asyncio
import openai
import random
```

Add these definitions after the `_RunExecution` class and before `class BaseAgent`:
```python
_MAX_BACKOFF_SECONDS = 120.0


@dataclass
class _ErrorClassification:
    retryable: bool
    reason: str
    suggestion: str


def _is_insufficient_quota(exc: openai.RateLimitError) -> bool:
    code = getattr(exc, "code", None) or ""
    err_type = getattr(exc, "type", None) or ""
    return "insufficient_quota" in code or "insufficient_quota" in err_type


def _classify_error(exc: Exception) -> _ErrorClassification:
    if isinstance(exc, openai.AuthenticationError):
        return _ErrorClassification(False, "authentication_error", "Check your API key.")
    if isinstance(exc, openai.PermissionDeniedError):
        return _ErrorClassification(
            False, "permission_denied",
            "Check your API key's permissions for this model/endpoint.",
        )
    if isinstance(exc, openai.BadRequestError):
        return _ErrorClassification(
            False, "bad_request", "Check the request configuration (model, parameters).",
        )
    if isinstance(exc, openai.RateLimitError):
        if _is_insufficient_quota(exc):
            return _ErrorClassification(
                False, "insufficient_quota",
                "Your account has insufficient quota — check your provider's billing dashboard.",
            )
        return _ErrorClassification(True, "rate_limited", "")
    return _ErrorClassification(True, "unknown", "")


def _extract_retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    header = response.headers.get("retry-after")
    if header is None:
        return None
    try:
        value = float(header)
    except (TypeError, ValueError):
        return None
    return max(0.0, value)


def _compute_backoff(
    exc: Exception, attempt: int, backoff_factor: float, fallback_seconds: float | None,
) -> float:
    retry_after = _extract_retry_after(exc)
    if retry_after is not None:
        return min(retry_after, _MAX_BACKOFF_SECONDS)
    if fallback_seconds is not None:
        return fallback_seconds
    backoff = backoff_factor**attempt
    return random.uniform(0, backoff)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_base.py -v`
Expected: PASS (all tests in the file, including the 13 new ones — the file's existing tests are unaffected since nothing wired into `_call_llm`/`_call_structured` yet)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `405 passed, 1 skipped` (392 from Task 1 + 13 new tests)

- [ ] **Step 6: Commit**

```bash
git add psalm/agents/base.py tests/unit/agents/test_base.py
git commit -m "feat: add error classification and Retry-After-aware backoff computation"
```

---

## Task 3: `ExecutionConfig` and `_RunExecution` Rate-Limit Fields

**Files:**
- Modify: `psalm/models/config.py`
- Modify: `psalm/agents/base.py`
- Test: `tests/unit/models/test_config.py`
- Test: `tests/unit/agents/test_base.py`

**Interfaces:**
- Consumes: `psalm.agents.rate_limiter._RateLimiter` (Task 1).
- Produces: `ExecutionConfig.max_requests_per_minute: int | None = 60`, `ExecutionConfig.max_tokens_per_minute: int | None = 40000`, `ExecutionConfig.retry_after_fallback_seconds: float | None = None`. `_RunExecution.max_requests_per_minute/max_tokens_per_minute/retry_after_fallback_seconds` (all `= None` at the dataclass level), `_RunExecution.rate_limiter() -> _RateLimiter | None`.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/models/test_config.py`, replace `test_execution_config_defaults`:
```python
def test_execution_config_defaults():
    from psalm.models.config import ExecutionConfig
    config = ExecutionConfig()
    assert config.max_concurrent_llm_calls == 8
    assert config.max_retries == 3
    assert config.backoff_factor == 2.0
```
with:
```python
def test_execution_config_defaults():
    from psalm.models.config import ExecutionConfig
    config = ExecutionConfig()
    assert config.max_concurrent_llm_calls == 8
    assert config.max_retries == 3
    assert config.backoff_factor == 2.0
    assert config.max_requests_per_minute == 60
    assert config.max_tokens_per_minute == 40000
    assert config.retry_after_fallback_seconds is None
```

Append to the same file:
```python
def test_execution_config_accepts_none_for_rate_limit_fields():
    from psalm.models.config import ExecutionConfig
    config = ExecutionConfig(max_requests_per_minute=None, max_tokens_per_minute=None)
    assert config.max_requests_per_minute is None
    assert config.max_tokens_per_minute is None


def test_execution_config_rejects_non_positive_max_requests_per_minute():
    from psalm.models.config import ExecutionConfig
    with pytest.raises(PSALMConfigError) as exc_info:
        ExecutionConfig(max_requests_per_minute=0)
    assert exc_info.value.code == "PSALM-C008"


def test_execution_config_rejects_non_positive_max_tokens_per_minute():
    from psalm.models.config import ExecutionConfig
    with pytest.raises(PSALMConfigError) as exc_info:
        ExecutionConfig(max_tokens_per_minute=0)
    assert exc_info.value.code == "PSALM-C008"


def test_execution_config_rejects_non_positive_retry_after_fallback_seconds():
    from psalm.models.config import ExecutionConfig
    with pytest.raises(PSALMConfigError) as exc_info:
        ExecutionConfig(retry_after_fallback_seconds=0.0)
    assert exc_info.value.code == "PSALM-C008"
```

Append to `tests/unit/agents/test_base.py`:
```python
def test_run_execution_rate_limiter_returns_none_when_disabled():
    from psalm.agents.base import _RunExecution
    execution = _RunExecution(max_concurrent_llm_calls=8, max_retries=3, backoff_factor=2.0)
    assert execution.rate_limiter() is None


async def test_run_execution_rate_limiter_returns_same_instance_within_a_loop():
    from psalm.agents.base import _RunExecution
    execution = _RunExecution(
        max_concurrent_llm_calls=8, max_retries=3, backoff_factor=2.0,
        max_requests_per_minute=60, max_tokens_per_minute=None,
    )
    assert execution.rate_limiter() is execution.rate_limiter()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/models/test_config.py tests/unit/agents/test_base.py -k "rate_limit_fields or requests_per_minute or tokens_per_minute or fallback_seconds or run_execution_rate_limiter" -v`
Expected: FAIL — `test_execution_config_defaults` fails on the new assertions (`AttributeError` or `AssertionError`), the two `run_execution_rate_limiter` tests fail with `AttributeError: '_RunExecution' object has no attribute 'rate_limiter'`

- [ ] **Step 3: Add the three fields to `ExecutionConfig`**

In `psalm/models/config.py`, replace:
```python
class ExecutionConfig(BaseModel):
    max_concurrent_llm_calls: int = 8
    max_retries: int = 3
    backoff_factor: float = 2.0

    @field_validator("max_concurrent_llm_calls", "max_retries")
    @classmethod
    def validate_positive_int(cls, v: int, info) -> int:
        if v < 1:
            raise PSALMConfigError(
                code="PSALM-C008",
                message=f"{info.field_name} must be >= 1, got {v}.",
                context={"field": info.field_name, "value": v},
                suggestion="Set a value of 1 or greater.",
            )
        return v

    @field_validator("backoff_factor")
    @classmethod
    def validate_backoff_factor(cls, v: float) -> float:
        if v <= 0:
            raise PSALMConfigError(
                code="PSALM-C008",
                message=f"backoff_factor must be > 0, got {v}.",
                context={"field": "backoff_factor", "value": v},
                suggestion="Set a positive value (e.g. 2.0).",
            )
        return v
```
with:
```python
class ExecutionConfig(BaseModel):
    max_concurrent_llm_calls: int = 8
    max_retries: int = 3
    backoff_factor: float = 2.0
    max_requests_per_minute: int | None = 60
    max_tokens_per_minute: int | None = 40000
    retry_after_fallback_seconds: float | None = None

    @field_validator(
        "max_concurrent_llm_calls", "max_retries", "max_requests_per_minute", "max_tokens_per_minute",
    )
    @classmethod
    def validate_positive_int(cls, v: int | None, info) -> int | None:
        if v is not None and v < 1:
            raise PSALMConfigError(
                code="PSALM-C008",
                message=f"{info.field_name} must be >= 1, got {v}.",
                context={"field": info.field_name, "value": v},
                suggestion="Set a value of 1 or greater, or None to disable (where applicable).",
            )
        return v

    @field_validator("backoff_factor", "retry_after_fallback_seconds")
    @classmethod
    def validate_positive_float(cls, v: float | None, info) -> float | None:
        if v is not None and v <= 0:
            raise PSALMConfigError(
                code="PSALM-C008",
                message=f"{info.field_name} must be > 0, got {v}.",
                context={"field": info.field_name, "value": v},
                suggestion="Set a positive value, or None to disable (where applicable).",
            )
        return v
```

- [ ] **Step 4: Add the three fields and `rate_limiter()` to `_RunExecution`**

In `psalm/agents/base.py`, add a new import line (alphabetically, before `from psalm.events import ...`):
```python
from psalm.agents.rate_limiter import _RateLimiter
```

Replace:
```python
@dataclass
class _RunExecution:
    max_concurrent_llm_calls: int
    max_retries: int
    backoff_factor: float
    _semaphores: dict[int, asyncio.Semaphore] = field(default_factory=dict, repr=False)

    def semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        key = id(loop)
        sem = self._semaphores.get(key)
        if sem is None:
            sem = asyncio.Semaphore(self.max_concurrent_llm_calls)
            self._semaphores[key] = sem
        return sem
```
with:
```python
@dataclass
class _RunExecution:
    max_concurrent_llm_calls: int
    max_retries: int
    backoff_factor: float
    max_requests_per_minute: int | None = None
    max_tokens_per_minute: int | None = None
    retry_after_fallback_seconds: float | None = None
    _semaphores: dict[int, asyncio.Semaphore] = field(default_factory=dict, repr=False)
    _rate_limiters: dict[int, _RateLimiter] = field(default_factory=dict, repr=False)

    def semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        key = id(loop)
        sem = self._semaphores.get(key)
        if sem is None:
            sem = asyncio.Semaphore(self.max_concurrent_llm_calls)
            self._semaphores[key] = sem
        return sem

    def rate_limiter(self) -> _RateLimiter | None:
        if self.max_requests_per_minute is None and self.max_tokens_per_minute is None:
            return None
        loop = asyncio.get_running_loop()
        key = id(loop)
        limiter = self._rate_limiters.get(key)
        if limiter is None:
            limiter = _RateLimiter(self.max_requests_per_minute, self.max_tokens_per_minute)
            self._rate_limiters[key] = limiter
        return limiter
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/models/test_config.py tests/unit/agents/test_base.py -v`
Expected: PASS (all tests in both files)

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `411 passed, 1 skipped` (405 from Task 2 + 6 new tests: 4 in test_config.py + 2 in test_base.py — `test_execution_config_defaults` was modified, not added)

- [ ] **Step 7: Commit**

```bash
git add psalm/models/config.py psalm/agents/base.py tests/unit/models/test_config.py tests/unit/agents/test_base.py
git commit -m "feat: add RPM/TPM/retry-after-fallback fields to ExecutionConfig and _RunExecution"
```

---

## Task 4: Wire Rate Limiting, Classification, Backoff, and Logging into the Retry Loop

**Files:**
- Modify: `psalm/agents/base.py`
- Test: `tests/unit/agents/test_base.py`

**Interfaces:**
- Consumes: `_classify_error`, `_compute_backoff`, `_MAX_BACKOFF_SECONDS` (Task 2); `_RunExecution.rate_limiter()` (Task 3); `estimate_tokens` (Task 1).
- Produces: `BaseAgent._execute_with_retry(self, messages: list[Any], invoke: Callable[[], Any]) -> Any`. `_call_llm`/`_call_structured` keep their exact existing signatures, now delegating to it.

This task changes the most behaviorally-sensitive code in the plan — verify carefully that every existing test in `tests/unit/agents/test_base.py` still passes unmodified (they should: `run_execution` and all direct `_RunExecution(...)` constructions in that file leave the three new fields at their `None` dataclass default, so `rate_limiter()` returns `None` and every existing exception in those tests is a plain `Exception`, which `_classify_error` marks retryable — the new code paths are additive and invisible to those tests).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/agents/test_base.py`:
```python
async def test_execute_with_retry_calls_rate_limiter_acquire_when_configured(agent_config):
    from psalm.agents.base import _RunExecution

    execution = _RunExecution(
        max_concurrent_llm_calls=8, max_retries=3, backoff_factor=2.0,
        max_requests_per_minute=60, max_tokens_per_minute=None,
    )
    agent = _TestAgent(config=agent_config, execution=execution)
    mock_limiter = AsyncMock()

    with patch.object(_RunExecution, "rate_limiter", return_value=mock_limiter):
        with patch.object(type(agent._llm), "ainvoke", new=AsyncMock(return_value="ok")):
            result = await agent._call_llm([{"role": "user", "content": "hi"}])

    assert result == "ok"
    mock_limiter.acquire.assert_called_once()


async def test_execute_with_retry_skips_rate_limiter_when_disabled(agent_config, run_execution):
    agent = _TestAgent(config=agent_config, execution=run_execution)

    with patch.object(type(agent._llm), "ainvoke", new=AsyncMock(return_value="ok")):
        result = await agent._call_llm([{"role": "user", "content": "hi"}])

    assert result == "ok"
    assert run_execution.rate_limiter() is None


async def test_call_llm_fails_fast_on_authentication_error(agent_config, run_execution):
    agent = _TestAgent(config=agent_config, execution=run_execution)
    auth_error = _make_status_error(openai.AuthenticationError, 401)

    with bound_event_sink() as sink:
        with patch.object(type(agent._llm), "ainvoke", new=AsyncMock(side_effect=auth_error)) as mock_ainvoke:
            with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock()) as mock_sleep:
                with pytest.raises(PSALMAgentError) as exc_info:
                    await agent._call_llm([{"role": "user", "content": "hi"}])
        events = await drain_events(sink)

    assert exc_info.value.code == "PSALM-A004"
    assert exc_info.value.context["reason"] == "authentication_error"
    assert mock_ainvoke.call_count == 1
    mock_sleep.assert_not_called()
    failed = [e for e in events if isinstance(e, AgentCallFailed)]
    assert len(failed) == 1
    assert failed[0].code == "PSALM-A004"


async def test_call_llm_fails_fast_on_insufficient_quota(agent_config, run_execution):
    agent = _TestAgent(config=agent_config, execution=run_execution)
    quota_error = _make_rate_limit_error(code="insufficient_quota")

    with patch.object(type(agent._llm), "ainvoke", new=AsyncMock(side_effect=quota_error)) as mock_ainvoke:
        with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            with pytest.raises(PSALMAgentError) as exc_info:
                await agent._call_llm([{"role": "user", "content": "hi"}])

    assert exc_info.value.code == "PSALM-A004"
    assert exc_info.value.context["reason"] == "insufficient_quota"
    assert mock_ainvoke.call_count == 1
    mock_sleep.assert_not_called()


async def test_call_llm_retries_genuine_rate_limit_error(agent_config, run_execution):
    agent = _TestAgent(config=agent_config, execution=run_execution)
    rate_limit_error = _make_rate_limit_error(code="rate_limit_exceeded")

    with patch.object(
        type(agent._llm), "ainvoke", new=AsyncMock(side_effect=[rate_limit_error, "ok"]),
    ):
        with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            result = await agent._call_llm([{"role": "user", "content": "hi"}])

    assert result == "ok"
    mock_sleep.assert_called_once()


async def test_call_llm_honors_retry_after_header_in_backoff(agent_config, run_execution):
    agent = _TestAgent(config=agent_config, execution=run_execution)
    rate_limit_error = _make_rate_limit_error(code="rate_limit_exceeded", retry_after="42")
    recorded_sleeps = []

    async def fake_sleep(seconds):
        recorded_sleeps.append(seconds)

    with patch.object(
        type(agent._llm), "ainvoke", new=AsyncMock(side_effect=[rate_limit_error, "ok"]),
    ):
        with patch("psalm.agents.base.asyncio.sleep", new=fake_sleep):
            await agent._call_llm([{"role": "user", "content": "hi"}])

    assert recorded_sleeps == [42.0]


async def test_call_llm_logs_warning_on_retry(agent_config, run_execution, caplog):
    agent = _TestAgent(config=agent_config, execution=run_execution)
    with caplog.at_level("WARNING", logger="psalm.agents.base"):
        with patch.object(
            type(agent._llm), "ainvoke", new=AsyncMock(side_effect=[Exception("boom"), "ok"]),
        ):
            with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock()):
                await agent._call_llm([{"role": "user", "content": "hi"}])

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "test-agent" in warnings[0].getMessage()


async def test_call_llm_logs_error_with_exc_info_on_final_failure(agent_config, run_execution, caplog):
    agent = _TestAgent(config=agent_config, execution=run_execution)
    with caplog.at_level("ERROR", logger="psalm.agents.base"):
        with patch.object(
            type(agent._llm), "ainvoke", new=AsyncMock(side_effect=Exception("persistent")),
        ):
            with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(PSALMAgentError):
                    await agent._call_llm([{"role": "user", "content": "hi"}])

    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(errors) == 1
    assert errors[0].exc_info is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_base.py -k "execute_with_retry or fails_fast or retries_genuine or honors_retry_after or logs_warning or logs_error" -v`
Expected: FAIL — the fail-fast tests raise `PSALMAgentError` with code `PSALM-A003` instead of `PSALM-A004` (today's code has no classification), the logging tests find zero log records (no logger exists yet), the rate-limiter tests find `mock_limiter.acquire` never called

- [ ] **Step 3: Replace `_call_llm`/`_call_structured` with the shared `_execute_with_retry`**

In `psalm/agents/base.py`, add `import logging` to the top-level imports (alphabetically, before `import openai`), and add `Callable` to the `typing` import:
```python
from typing import Any, Callable
```

Add a module-level logger, immediately after the imports and before `_MAX_BACKOFF_SECONDS = 120.0`:
```python
logger = logging.getLogger(__name__)
```

Replace the entire `_call_llm` and `_call_structured` methods (everything from `async def _call_llm` through the second method's closing `raise RuntimeError("unreachable")`):
```python
    async def _call_llm(self, messages: list[Any]) -> Any:
        max_retries = self._execution.max_retries
        for attempt in range(max_retries):
            try:
                async with self._execution.semaphore():
                    return await self._llm.ainvoke(messages)
            except Exception as exc:
                if attempt == max_retries - 1:
                    await emit(AgentCallFailed(
                        role=self.role, attempts=max_retries, code="PSALM-A003", error=str(exc),
                    ))
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=f"LLM retry limit reached after {max_retries} attempts.",
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": max_retries,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                backoff = self._execution.backoff_factor**attempt
                jittered = random.uniform(0, backoff)
                await emit(AgentCallRetrying(
                    role=self.role, attempt=attempt + 1, max_attempts=max_retries,
                    backoff_seconds=jittered, error=str(exc),
                ))
                await asyncio.sleep(jittered)
        raise RuntimeError("unreachable")

    async def _call_structured(self, structured_llm: Any, messages: list[Any]) -> Any:
        max_retries = self._execution.max_retries
        for attempt in range(max_retries):
            try:
                async with self._execution.semaphore():
                    return await structured_llm.ainvoke(messages)
            except Exception as exc:
                if attempt == max_retries - 1:
                    await emit(AgentCallFailed(
                        role=self.role, attempts=max_retries, code="PSALM-A003", error=str(exc),
                    ))
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=(
                            f"Structured LLM retry limit reached after {max_retries} attempts."
                        ),
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": max_retries,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                backoff = self._execution.backoff_factor**attempt
                jittered = random.uniform(0, backoff)
                await emit(AgentCallRetrying(
                    role=self.role, attempt=attempt + 1, max_attempts=max_retries,
                    backoff_seconds=jittered, error=str(exc),
                ))
                await asyncio.sleep(jittered)
        raise RuntimeError("unreachable")
```
with:
```python
    async def _execute_with_retry(self, messages: list[Any], invoke: Callable[[], Any]) -> Any:
        max_retries = self._execution.max_retries
        for attempt in range(max_retries):
            rate_limiter = self._execution.rate_limiter()
            if rate_limiter is not None:
                estimated_tokens = estimate_tokens(
                    messages, self._config.model, self._config.max_tokens,
                )
                await rate_limiter.acquire(estimated_tokens)
            try:
                async with self._execution.semaphore():
                    return await invoke()
            except Exception as exc:
                classification = _classify_error(exc)
                if not classification.retryable:
                    logger.error(
                        "Non-retryable agent error (role=%s, model=%s, reason=%s)",
                        self.role, self._config.model, classification.reason, exc_info=True,
                    )
                    await emit(AgentCallFailed(
                        role=self.role, attempts=attempt + 1, code="PSALM-A004", error=str(exc),
                    ))
                    raise PSALMAgentError(
                        code="PSALM-A004",
                        message=(
                            f"Non-retryable error from agent '{self.role}': {classification.reason}."
                        ),
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "reason": classification.reason,
                            "attempts": attempt + 1,
                        },
                        suggestion=classification.suggestion,
                        cause=exc,
                    ) from exc
                if attempt == max_retries - 1:
                    logger.error(
                        "LLM retry limit reached (role=%s, model=%s, attempts=%d)",
                        self.role, self._config.model, max_retries, exc_info=True,
                    )
                    await emit(AgentCallFailed(
                        role=self.role, attempts=max_retries, code="PSALM-A003", error=str(exc),
                    ))
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=f"LLM retry limit reached after {max_retries} attempts.",
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": max_retries,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                wait = _compute_backoff(
                    exc, attempt, self._execution.backoff_factor,
                    self._execution.retry_after_fallback_seconds,
                )
                logger.warning(
                    "Retrying agent call (role=%s, attempt=%d/%d, wait=%.2fs): %s",
                    self.role, attempt + 1, max_retries, wait, exc,
                )
                await emit(AgentCallRetrying(
                    role=self.role, attempt=attempt + 1, max_attempts=max_retries,
                    backoff_seconds=wait, error=str(exc),
                ))
                await asyncio.sleep(wait)
        raise RuntimeError("unreachable")

    async def _call_llm(self, messages: list[Any]) -> Any:
        return await self._execute_with_retry(messages, lambda: self._llm.ainvoke(messages))

    async def _call_structured(self, structured_llm: Any, messages: list[Any]) -> Any:
        return await self._execute_with_retry(messages, lambda: structured_llm.ainvoke(messages))
```

Add `estimate_tokens` to the existing `psalm.agents.rate_limiter` import line:
```python
from psalm.agents.rate_limiter import _RateLimiter, estimate_tokens
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_base.py -v`
Expected: PASS (every test in the file — all pre-existing tests plus every new one from Tasks 2-4)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `419 passed, 1 skipped` (411 from Task 3 + 8 new tests)

- [ ] **Step 6: Commit**

```bash
git add psalm/agents/base.py tests/unit/agents/test_base.py
git commit -m "feat: wire rate limiting, error classification, retry-after backoff, and logging into the retry loop"
```

---

## Task 5: Builder Wiring

**Files:**
- Modify: `psalm/builder.py`
- Test: `tests/unit/test_builder.py`

**Interfaces:**
- Consumes: `ExecutionConfig`'s 3 new fields (Task 3), `_RunExecution`'s 3 new fields (Task 3).
- Produces: `PSALM.with_execution(...)` gains 3 new keyword arguments with defaults matching `ExecutionConfig`.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_builder.py`, replace `test_default_execution_config`:
```python
def test_default_execution_config():
    builder = PSALM()
    assert builder._execution_config.max_concurrent_llm_calls == 8
    assert builder._execution_config.max_retries == 3
    assert builder._execution_config.backoff_factor == 2.0
```
with:
```python
def test_default_execution_config():
    builder = PSALM()
    assert builder._execution_config.max_concurrent_llm_calls == 8
    assert builder._execution_config.max_retries == 3
    assert builder._execution_config.backoff_factor == 2.0
    assert builder._execution_config.max_requests_per_minute == 60
    assert builder._execution_config.max_tokens_per_minute == 40000
    assert builder._execution_config.retry_after_fallback_seconds is None
```

Append to the same file:
```python
def test_with_execution_stores_rate_limit_fields():
    builder = PSALM().with_execution(
        max_requests_per_minute=10, max_tokens_per_minute=1000, retry_after_fallback_seconds=5.0,
    )
    assert builder._execution_config.max_requests_per_minute == 10
    assert builder._execution_config.max_tokens_per_minute == 1000
    assert builder._execution_config.retry_after_fallback_seconds == 5.0


async def test_build_applies_configured_rate_limit_settings():
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_execution(
            max_requests_per_minute=15, max_tokens_per_minute=2000, retry_after_fallback_seconds=3.0,
        )
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        courtroom = await builder.build()
    execution = courtroom._courtroom._argumentation_phase._prosecutor._execution
    assert execution.max_requests_per_minute == 15
    assert execution.max_tokens_per_minute == 2000
    assert execution.retry_after_fallback_seconds == 3.0
    assert execution.rate_limiter() is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_builder.py -k "default_execution_config or with_execution_stores_rate_limit or applies_configured_rate_limit" -v`
Expected: FAIL — `test_default_execution_config` fails on the new assertions (`AttributeError`), `test_with_execution_stores_rate_limit_fields` fails with `TypeError: with_execution() got an unexpected keyword argument 'max_requests_per_minute'`

- [ ] **Step 3: Update `PSALM.with_execution` and `build()`**

In `psalm/builder.py`, replace:
```python
    def with_execution(
        self,
        max_concurrent_llm_calls: int = 8,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> PSALM:
        self._execution_config = ExecutionConfig(
            max_concurrent_llm_calls=max_concurrent_llm_calls,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )
        return self
```
with:
```python
    def with_execution(
        self,
        max_concurrent_llm_calls: int = 8,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        max_requests_per_minute: int | None = 60,
        max_tokens_per_minute: int | None = 40000,
        retry_after_fallback_seconds: float | None = None,
    ) -> PSALM:
        self._execution_config = ExecutionConfig(
            max_concurrent_llm_calls=max_concurrent_llm_calls,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            max_requests_per_minute=max_requests_per_minute,
            max_tokens_per_minute=max_tokens_per_minute,
            retry_after_fallback_seconds=retry_after_fallback_seconds,
        )
        return self
```

Replace:
```python
    async def build(self) -> _BuiltPSALM:
        self._validate_config()
        execution = _RunExecution(
            max_concurrent_llm_calls=self._execution_config.max_concurrent_llm_calls,
            max_retries=self._execution_config.max_retries,
            backoff_factor=self._execution_config.backoff_factor,
        )
        await self._ping_all_llms(execution)
        return self._assemble(execution)
```
with:
```python
    async def build(self) -> _BuiltPSALM:
        self._validate_config()
        execution = _RunExecution(
            max_concurrent_llm_calls=self._execution_config.max_concurrent_llm_calls,
            max_retries=self._execution_config.max_retries,
            backoff_factor=self._execution_config.backoff_factor,
            max_requests_per_minute=self._execution_config.max_requests_per_minute,
            max_tokens_per_minute=self._execution_config.max_tokens_per_minute,
            retry_after_fallback_seconds=self._execution_config.retry_after_fallback_seconds,
        )
        await self._ping_all_llms(execution)
        return self._assemble(execution)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_builder.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `421 passed, 1 skipped` (419 from Task 4 + 2 new tests — `test_default_execution_config` was modified, not added)

- [ ] **Step 6: Commit**

```bash
git add psalm/builder.py tests/unit/test_builder.py
git commit -m "feat: thread rate-limit settings through PSALM.with_execution()"
```

---

## Task 6: Web Backend — `TrialConfigRequest`, `build_psalm`, Logging Setup

**Files:**
- Modify: `examples/web/backend/schemas.py`
- Modify: `examples/web/backend/execution.py`
- Modify: `examples/web/backend/main.py`
- Test: `examples/web/backend/tests/test_execution.py`

**Interfaces:**
- Consumes: `PSALM.with_execution(...)`'s 3 new kwargs (Task 5).
- Produces: `TrialConfigRequest.max_requests_per_minute: int = 60`, `.max_tokens_per_minute: int = 40000`, `.retry_after_fallback_seconds: float = 0` (web form's `0` = disabled convention). `build_psalm` translates `0 → None` before forwarding.

- [ ] **Step 1: Write the failing tests**

In `examples/web/backend/tests/test_execution.py`, replace `test_build_psalm_forwards_execution_settings`:
```python
async def test_build_psalm_forwards_execution_settings():
    from unittest.mock import MagicMock

    config = _config(max_concurrent_llm_calls=2, max_retries=1)
    resolved = resolve_config(config)
    captured = {}

    class _FakeBuilder:
        def with_prosecutor(self, **kw): return self
        def with_defense(self, **kw): return self
        def with_judge(self, **kw): return self
        def with_jury(self, jury): return self
        def with_dimensions(self, dims): return self
        def with_debate(self, **kw): return self
        def with_voting(self, strategies): return self
        def with_evaluation_strategy(self, strategy): return self
        def with_execution(self, **kw):
            captured.update(kw)
            return self
        async def build(self): return "built"

    with patch("execution.PSALM", return_value=_FakeBuilder()):
        result = await build_psalm(config, resolved)

    assert captured == {"max_concurrent_llm_calls": 2, "max_retries": 1}
    assert result == "built"
```
with:
```python
async def test_build_psalm_forwards_execution_settings():
    from unittest.mock import MagicMock

    config = _config(max_concurrent_llm_calls=2, max_retries=1)
    resolved = resolve_config(config)
    captured = {}

    class _FakeBuilder:
        def with_prosecutor(self, **kw): return self
        def with_defense(self, **kw): return self
        def with_judge(self, **kw): return self
        def with_jury(self, jury): return self
        def with_dimensions(self, dims): return self
        def with_debate(self, **kw): return self
        def with_voting(self, strategies): return self
        def with_evaluation_strategy(self, strategy): return self
        def with_execution(self, **kw):
            captured.update(kw)
            return self
        async def build(self): return "built"

    with patch("execution.PSALM", return_value=_FakeBuilder()):
        result = await build_psalm(config, resolved)

    assert captured == {
        "max_concurrent_llm_calls": 2, "max_retries": 1,
        "max_requests_per_minute": 60, "max_tokens_per_minute": 40000,
        "retry_after_fallback_seconds": None,
    }
    assert result == "built"


async def test_build_psalm_translates_zero_to_none_for_rate_limit_fields():
    config = _config(max_requests_per_minute=0, max_tokens_per_minute=0, retry_after_fallback_seconds=0)
    resolved = resolve_config(config)
    captured = {}

    class _FakeBuilder:
        def with_prosecutor(self, **kw): return self
        def with_defense(self, **kw): return self
        def with_judge(self, **kw): return self
        def with_jury(self, jury): return self
        def with_dimensions(self, dims): return self
        def with_debate(self, **kw): return self
        def with_voting(self, strategies): return self
        def with_evaluation_strategy(self, strategy): return self
        def with_execution(self, **kw):
            captured.update(kw)
            return self
        async def build(self): return "built"

    with patch("execution.PSALM", return_value=_FakeBuilder()):
        await build_psalm(config, resolved)

    assert captured["max_requests_per_minute"] is None
    assert captured["max_tokens_per_minute"] is None
    assert captured["retry_after_fallback_seconds"] is None


def test_trial_config_request_rate_limit_defaults():
    config = _config()
    assert config.max_requests_per_minute == 60
    assert config.max_tokens_per_minute == 40000
    assert config.retry_after_fallback_seconds == 0


def test_trial_config_request_rejects_negative_max_requests_per_minute():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _config(max_requests_per_minute=-1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest examples/web/backend -q` (from the repo root — not `cd examples/web/backend`, since this repo's shared `.venv` has `psalm` editable-installed against the main checkout, and `cd`-ing into that directory before running pytest silently resolves the wrong `psalm` package)
Expected: FAIL — `test_build_psalm_forwards_execution_settings` fails on the dict equality (new keys missing), `test_build_psalm_translates_zero_to_none_for_rate_limit_fields` and `test_trial_config_request_rate_limit_defaults` fail with `TypeError`/`AttributeError` (fields don't exist yet)

- [ ] **Step 3: Add the three fields to `TrialConfigRequest`**

In `examples/web/backend/schemas.py`, replace:
```python
class TrialConfigRequest(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str]
    evaluation_strategy: str = "fully_separate"
    argumentation_rounds: int = 3
    deliberation_rounds: int = 2
    time_limit_seconds: int = 120
    max_concurrent_llm_calls: int = Field(default=8, ge=1)
    max_retries: int = Field(default=3, ge=1)
    prosecutor: AgentConfigRequest = AgentConfigRequest()
    defense: AgentConfigRequest = AgentConfigRequest()
    judge: AgentConfigRequest = AgentConfigRequest()
    jury: list[JurorConfigRequest] = [
        JurorConfigRequest(), JurorConfigRequest(), JurorConfigRequest(),
    ]
```
with:
```python
class TrialConfigRequest(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str]
    evaluation_strategy: str = "fully_separate"
    argumentation_rounds: int = 3
    deliberation_rounds: int = 2
    time_limit_seconds: int = 120
    max_concurrent_llm_calls: int = Field(default=8, ge=1)
    max_retries: int = Field(default=3, ge=1)
    max_requests_per_minute: int = Field(default=60, ge=0)
    max_tokens_per_minute: int = Field(default=40000, ge=0)
    retry_after_fallback_seconds: float = Field(default=0, ge=0)
    prosecutor: AgentConfigRequest = AgentConfigRequest()
    defense: AgentConfigRequest = AgentConfigRequest()
    judge: AgentConfigRequest = AgentConfigRequest()
    jury: list[JurorConfigRequest] = [
        JurorConfigRequest(), JurorConfigRequest(), JurorConfigRequest(),
    ]
```

- [ ] **Step 4: Forward and translate the settings in `build_psalm`**

In `examples/web/backend/execution.py`, replace:
```python
            .with_execution(
                max_concurrent_llm_calls=config.max_concurrent_llm_calls,
                max_retries=config.max_retries,
            )
```
with:
```python
            .with_execution(
                max_concurrent_llm_calls=config.max_concurrent_llm_calls,
                max_retries=config.max_retries,
                max_requests_per_minute=config.max_requests_per_minute or None,
                max_tokens_per_minute=config.max_tokens_per_minute or None,
                retry_after_fallback_seconds=config.retry_after_fallback_seconds or None,
            )
```

- [ ] **Step 5: Add startup logging configuration**

In `examples/web/backend/main.py`, add `import logging` as the first import (before `from pathlib import Path`), and add a `logging.basicConfig(...)` call right after the imports, before `app = FastAPI(...)`:
```python
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routes import api_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="psalm courtroom demo")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest examples/web/backend -q` (from the repo root)
Expected: PASS (all tests, `67 passed`)

- [ ] **Step 7: Commit**

```bash
git add examples/web/backend/schemas.py examples/web/backend/execution.py examples/web/backend/main.py examples/web/backend/tests/test_execution.py
git commit -m "feat(web): forward rate-limit settings to PSALM builder, add startup logging"
```

---

## Task 7: Web Frontend — Trial Config Form Fields

**Files:**
- Modify: `examples/web/frontend/src/api/types.ts`
- Modify: `examples/web/frontend/src/routes/SetupPage.tsx`
- Modify: `examples/web/frontend/src/routes/SetupPage.test.tsx`
- Modify: `examples/web/frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: `TrialConfigRequest`'s 3 new fields (Task 6) — field names must match exactly since they're sent as the JSON request body.
- Produces: three new `NumberInput`s in `SetupPage`'s Advanced settings, `min={0}` (0 = disabled, unlike the existing concurrency/retry fields which use `min={1}`).

Before starting, grep the whole frontend source for every place `TrialConfigInput` is used as a type annotation for an object literal (not just `SetupPage.tsx`) — the prior `execution-concurrency-config` feature missed `client.test.ts`'s `sampleConfig`, which broke `npm run build` (though not `npm test`) after merge. This task explicitly includes that file so it doesn't happen again.

- [ ] **Step 1: Write the failing test assertions**

In `examples/web/frontend/src/routes/SetupPage.test.tsx`, in the `"submits the trial with the right payload and navigates on success"` test, add these three lines directly after `expect(payload.max_retries).toBe(3);`:
```tsx
    expect(payload.max_requests_per_minute).toBe(60);
    expect(payload.max_tokens_per_minute).toBe(40000);
    expect(payload.retry_after_fallback_seconds).toBe(0);
```

In `examples/web/frontend/src/api/client.test.ts`, replace:
```ts
const sampleConfig: TrialConfigInput = {
  source_text: "s", target_text: "t", dimensions: ["Character"], evaluation_strategy: "fully_separate",
  argumentation_rounds: 3, deliberation_rounds: 2, time_limit_seconds: 120,
  max_concurrent_llm_calls: 8, max_retries: 3,
  prosecutor: {}, defense: {}, judge: {}, jury: [],
};
```
with:
```ts
const sampleConfig: TrialConfigInput = {
  source_text: "s", target_text: "t", dimensions: ["Character"], evaluation_strategy: "fully_separate",
  argumentation_rounds: 3, deliberation_rounds: 2, time_limit_seconds: 120,
  max_concurrent_llm_calls: 8, max_retries: 3,
  max_requests_per_minute: 60, max_tokens_per_minute: 40000, retry_after_fallback_seconds: 0,
  prosecutor: {}, defense: {}, judge: {}, jury: [],
};
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/frontend && npx vitest run src/routes/SetupPage.test.tsx src/api/client.test.ts`
Expected: FAIL — `SetupPage.test.tsx`'s new assertions fail (`payload.max_requests_per_minute` is `undefined`); `client.test.ts` fails to even compile/run under `tsc`-checked test config once `TrialConfigInput` gains the new required fields (or, if Vitest's type-stripping lets it through at test-run time despite the TS error, at minimum confirm via `npm run build` in Step 6 that the pre-fix state fails there)

- [ ] **Step 3: Add the three fields to `TrialConfigInput`**

In `examples/web/frontend/src/api/types.ts`, replace:
```ts
export interface TrialConfigInput {
  source_text: string;
  target_text: string;
  dimensions: string[];
  evaluation_strategy: string;
  argumentation_rounds: number;
  deliberation_rounds: number;
  time_limit_seconds: number;
  max_concurrent_llm_calls: number;
  max_retries: number;
  prosecutor: AgentConfigInput;
  defense: AgentConfigInput;
  judge: AgentConfigInput;
  jury: JurorConfigInput[];
}
```
with:
```ts
export interface TrialConfigInput {
  source_text: string;
  target_text: string;
  dimensions: string[];
  evaluation_strategy: string;
  argumentation_rounds: number;
  deliberation_rounds: number;
  time_limit_seconds: number;
  max_concurrent_llm_calls: number;
  max_retries: number;
  max_requests_per_minute: number;
  max_tokens_per_minute: number;
  retry_after_fallback_seconds: number;
  prosecutor: AgentConfigInput;
  defense: AgentConfigInput;
  judge: AgentConfigInput;
  jury: JurorConfigInput[];
}
```

- [ ] **Step 4: Add state, form fields, and payload wiring to `SetupPage.tsx`**

Replace:
```tsx
  const [maxConcurrentLlmCalls, setMaxConcurrentLlmCalls] = useState(8);
  const [maxRetries, setMaxRetries] = useState(3);
```
with:
```tsx
  const [maxConcurrentLlmCalls, setMaxConcurrentLlmCalls] = useState(8);
  const [maxRetries, setMaxRetries] = useState(3);
  const [maxRequestsPerMinute, setMaxRequestsPerMinute] = useState(60);
  const [maxTokensPerMinute, setMaxTokensPerMinute] = useState(40000);
  const [retryAfterFallbackSeconds, setRetryAfterFallbackSeconds] = useState(0);
```

Replace the `startTrial` call inside `handleSubmit`:
```tsx
      const { trial_id } = await startTrial({
        source_text: sourceText,
        target_text: targetText,
        dimensions: selectedDimensions,
        evaluation_strategy: evaluationStrategy,
        argumentation_rounds: argumentationRounds,
        deliberation_rounds: deliberationRounds,
        time_limit_seconds: timeLimitSeconds,
        max_concurrent_llm_calls: maxConcurrentLlmCalls,
        max_retries: maxRetries,
        prosecutor,
        defense,
        judge,
        jury,
      });
```
with:
```tsx
      const { trial_id } = await startTrial({
        source_text: sourceText,
        target_text: targetText,
        dimensions: selectedDimensions,
        evaluation_strategy: evaluationStrategy,
        argumentation_rounds: argumentationRounds,
        deliberation_rounds: deliberationRounds,
        time_limit_seconds: timeLimitSeconds,
        max_concurrent_llm_calls: maxConcurrentLlmCalls,
        max_retries: maxRetries,
        max_requests_per_minute: maxRequestsPerMinute,
        max_tokens_per_minute: maxTokensPerMinute,
        retry_after_fallback_seconds: retryAfterFallbackSeconds,
        prosecutor,
        defense,
        judge,
        jury,
      });
```

Replace the `max-retries` `NumberInput` inside the "Advanced settings" `Accordion.Panel`:
```tsx
                    <NumberInput
                      id="max-retries" label="Max retries" min={1}
                      value={maxRetries}
                      onChange={(value) => setMaxRetries(Number(value))}
                    />
```
with:
```tsx
                    <NumberInput
                      id="max-retries" label="Max retries" min={1}
                      value={maxRetries}
                      onChange={(value) => setMaxRetries(Number(value))}
                    />
                    <NumberInput
                      id="max-requests-per-minute" label="Max requests per minute (0 = unlimited)" min={0}
                      value={maxRequestsPerMinute}
                      onChange={(value) => setMaxRequestsPerMinute(Number(value))}
                    />
                    <NumberInput
                      id="max-tokens-per-minute" label="Max tokens per minute (0 = unlimited)" min={0}
                      value={maxTokensPerMinute}
                      onChange={(value) => setMaxTokensPerMinute(Number(value))}
                    />
                    <NumberInput
                      id="retry-after-fallback-seconds"
                      label="Retry-After fallback (seconds, 0 = disabled)" min={0}
                      value={retryAfterFallbackSeconds}
                      onChange={(value) => setRetryAfterFallbackSeconds(Number(value))}
                    />
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd examples/web/frontend && npx vitest run src/routes/SetupPage.test.tsx src/api/client.test.ts`
Expected: PASS (all tests in both files)

- [ ] **Step 6: Run the full frontend suite AND the production build**

Run: `cd examples/web/frontend && npm test`
Expected: all tests pass, `90 passed` across 14 files (no new test cases were added, only assertions extended, matching the count from the prior `execution-concurrency-config` feature)

Run: `cd examples/web/frontend && npm run build`
Expected: succeeds with no `tsc` errors — this is the check that would have caught the missed `client.test.ts` field on the prior feature; do not skip it.

- [ ] **Step 7: Commit**

```bash
git add examples/web/frontend/src/api/types.ts examples/web/frontend/src/routes/SetupPage.tsx examples/web/frontend/src/routes/SetupPage.test.tsx examples/web/frontend/src/api/client.test.ts
git commit -m "feat(web): expose RPM/TPM/retry-after-fallback settings in the trial config form"
```

---

## Task 8: Full-Suite Verification

**Files:** none (verification only)

**Interfaces:** none — this task runs all suites end-to-end (including the production frontend build) and confirms nothing regressed.

- [ ] **Step 1: Run the full SDK suite**

Run: `python -m pytest tests/ -q`
Expected: `421 passed, 1 skipped` (per the running total established in Task 5, Step 5 — if any earlier task's actual count differed from this plan's prediction, expect that adjusted total instead)

- [ ] **Step 2: Run the full web backend suite**

Run: `python -m pytest examples/web/backend -q` (from the repo root)
Expected: `67 passed`, 0 failures

- [ ] **Step 3: Run the full web frontend suite and production build**

Run: `cd examples/web/frontend && npm test`
Expected: `90 passed` across 14 files, 0 failures

Run: `cd examples/web/frontend && npm run build`
Expected: succeeds with no errors

- [ ] **Step 4: Manually sanity-check the demo app (if a local OpenAI-compatible endpoint is available)**

Start the backend and frontend, open the trial setup form, confirm the three new "Max requests per minute" / "Max tokens per minute" / "Retry-After fallback" fields appear in Advanced settings pre-filled with 60/40000/0, and start a full-dimension trial. This step is exploratory (not a pass/fail gate) — its purpose is to confirm the original reported symptom no longer occurs. Skip if no live LLM endpoint is available; the automated suites in Steps 1-3 are the actual completion gate.

- [ ] **Step 5: Report**

No commit for this task (verification only). Confirm to the user: exact pass/fail counts from Steps 1-3, and whether Step 4 was performed and what was observed.
