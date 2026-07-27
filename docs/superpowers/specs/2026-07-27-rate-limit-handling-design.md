# Rate-Limit Handling — Design

## 1. Overview

The `execution-concurrency-config` feature (merged 2026-07-21) added a shared `asyncio.Semaphore`
concurrency cap and configurable/jittered retry backoff, but a full-dimension trial still fails
with `Trial failed: Structured LLM retry limit reached after 3 attempts.` Root-cause investigation
(via `superpowers:systematic-debugging`) found three compounding gaps, none of them fixed by a
concurrency cap:

1. **A concurrency cap bounds simultaneous in-flight requests, not the rate of new requests over
   time.** A multi-dimension trial fires many sequential bursts (every deliberation round ×
   argumentation round × dimension); even capped at 8-at-a-time, sustained requests/minute can
   exceed a provider's actual RPM/TPM limit. This needs real rate *pacing*, not just a concurrency
   ceiling — matching the approach in OpenAI's own
   [rate-limit guide](https://developers.openai.com/cookbook/examples/how_to_handle_rate_limits#how-to-mitigate-rate-limit-errors)
   and
   [parallel-processing cookbook](https://github.com/openai/openai-cookbook/blob/main/examples/api_request_parallel_processor.py).
2. **Backoff is blind and too short.** `BaseAgent._call_llm`/`_call_structured` retry 3× with a
   jittered backoff that maxes out around ~3 seconds total — far short of the up-to-60s an actual
   per-minute rate-limit window can need to clear, and it never reads the `Retry-After` header the
   provider may already be sending.
3. **No error-type/error-code discrimination.** Every exception is retried identically for
   `max_retries` attempts, including permanently non-retryable ones (bad API key, insufficient
   quota, malformed request), wasting retry budget and producing the same generic failure message
   regardless of actual cause.

A fourth, related gap found during investigation: **there is no logging anywhere in `psalm/` or
the web backend** — failures are visible only via the in-band event stream (while a listener is
attached) and a terse final error string; the real traceback and cause chain is silently dropped.

**Goal:** add RPM/TPM-aware request pacing alongside the existing concurrency cap, make backoff
aware of the `Retry-After` header (with a configurable fallback for providers that don't send it),
classify errors into retry-vs-fail-fast so non-recoverable errors surface immediately with a
specific reason, and add proper logging so failures are diagnosable without a live event listener.
Every new setting is exposed through the same `ExecutionConfig`/`PSALM.with_execution(...)`
surface the concurrency work established, and surfaced in the web app's Advanced settings.

**Deliberately out of scope:** token *true-up* after each call (correcting the rate limiter's
token bucket from actual usage) — every real call in this codebase goes through
`_call_structured` via `.with_structured_output(...)` *without* `include_raw=True`, so no call
site currently has access to actual token-usage metadata; adding it would mean touching all ~15
structured-output call sites across `defense.py`/`prosecutor.py`/`juror.py`/`judge.py`, which is
out of proportion to a rate-limiting fix. Token debiting is estimate-only (pre-call), which is
still an effective pacing mechanism since the bucket continuously refills regardless.
Provider-specific client abstraction is also out of scope: PSALM always constructs `ChatOpenAI`
regardless of `base_url`, so the `openai` package's exception classes are already a safe,
provider-agnostic classification signal for *any* OpenAI-API-compatible endpoint — no new
abstraction is needed to support that.

## 2. RPM/TPM Rate Limiter

**New file `psalm/agents/rate_limiter.py`** — kept separate from `agents/base.py` so that file
doesn't take on a second responsibility as it grows.

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
                token_ok = self._token_capacity is None or self._token_capacity >= estimated_tokens
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
        content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
        text_parts.append(str(content))
    prompt_tokens = len(encoding.encode(" ".join(text_parts)))
    completion_estimate = max_completion_tokens or _DEFAULT_COMPLETION_TOKEN_ESTIMATE
    return prompt_tokens + completion_estimate
```

Buckets refill continuously (per-second, not a once-a-minute hard reset) to avoid a thundering
herd the instant a minute boundary passes. `acquire()` releases its lock between polls so
concurrent callers aren't needlessly serialized while waiting. Unknown models (any non-`gpt-*`
model, i.e. any third-party provider) fall back to `cl100k_base` — an approximation, which is
acceptable since this is a pacing estimate, not a billing calculation. `tiktoken` is already an
installed transitive dependency of `langchain-openai`; it becomes a direct dependency in
`pyproject.toml` since PSALM's own code now imports it.

`_RunExecution` (`psalm/agents/base.py`) gains a `rate_limiter()` method, following the exact same
lazy-per-running-event-loop-cache pattern already used for `semaphore()` — a `_RateLimiter`'s
internal `asyncio.Lock` has the identical loop-binding hazard the semaphore fix addressed, so this
bakes the same fix in from the start rather than risking a second final-review discovery of it.
Returns `None` when both `max_requests_per_minute` and `max_tokens_per_minute` are unset, meaning
pacing is disabled (matching the semaphore's existing all-or-nothing-per-run construction):

```python
@dataclass
class _RunExecution:
    max_concurrent_llm_calls: int
    max_retries: int
    backoff_factor: float
    max_requests_per_minute: int | None
    max_tokens_per_minute: int | None
    retry_after_fallback_seconds: float | None
    _semaphores: dict[int, asyncio.Semaphore] = field(default_factory=dict, repr=False)
    _rate_limiters: dict[int, _RateLimiter] = field(default_factory=dict, repr=False)

    def semaphore(self) -> asyncio.Semaphore:
        ...  # unchanged from the execution-concurrency-config feature

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

**Defaults:** `max_requests_per_minute=60`, `max_tokens_per_minute=40000` — always-on, anchored to
commonly-published OpenAI Tier 1 numbers for `gpt-4o-mini` (PSALM's own default model). Treated as
a reasonable floor, not a guarantee — real limits vary by model/tier/provider and drift over time,
so both remain fully overridable (including to disabled) via config and the web UI.

## 3. Retry-After-Aware Backoff

Three-tier priority replaces today's always-jittered-exponential backoff, applied only when an
error is classified as retryable (§4). These functions live in `psalm/agents/base.py` alongside
`_execute_with_retry` (§6), not in the new `rate_limiter.py` module — they're part of the retry
loop's backoff calculation, not the RPM/TPM pacing mechanism.

```python
_MAX_BACKOFF_SECONDS = 120.0


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

1. **Real `Retry-After` header**, if present on the exception's `.response` (works for any
   `openai.APIStatusError` subclass — `httpx.Headers` lookups are case-insensitive) — clamped to
   `_MAX_BACKOFF_SECONDS` so a misbehaving proxy can't stall a trial indefinitely. This clamp
   applies only here, not to the configured fallback below: the header is untrusted external
   input from the provider, while the fallback is a value the user deliberately set and owns the
   consequences of.
2. **Configured fallback** (`ExecutionConfig.retry_after_fallback_seconds`, default `None`) — used
   only when the header is absent, and used as-is (not clamped). This is the manual override for
   OpenAI-API-compatible providers that don't send the header at all.
3. **Existing jittered exponential backoff** — unchanged fallback-of-the-fallback, so behavior is
   identical to today for anyone who touches none of this new config.

## 4. Error Classification

These also live in `psalm/agents/base.py` (needs a new `import openai` there for the `isinstance`
checks below):

```python
@dataclass
class _ErrorClassification:
    retryable: bool
    reason: str
    suggestion: str


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


def _is_insufficient_quota(exc: "openai.RateLimitError") -> bool:
    code = getattr(exc, "code", None) or ""
    err_type = getattr(exc, "type", None) or ""
    return "insufficient_quota" in code or "insufficient_quota" in err_type
```

Classification is **additive to today's behavior, not a replacement allowlist**: anything not
explicitly matched (`_ErrorClassification(True, "unknown", "")`) still retries exactly as it does
now, so an unexpected exception type can't silently start failing fast.

- **Fail fast** (raise immediately, consumes no further retry budget): `AuthenticationError` (401),
  `PermissionDeniedError` (403), `BadRequestError` (400), and `RateLimitError` (429) specifically
  when the body's `error.code`/`error.type` indicates `insufficient_quota` — same HTTP status as a
  genuine rate limit, different (permanent) cause.
- **Retry** (existing behavior, now enhanced by §2/§3): `RateLimitError` otherwise, and everything
  not explicitly classified (today's catch-all, unchanged — covers `APIConnectionError`,
  `APITimeoutError`, `InternalServerError`, and anything else).

**New error code `PSALM-A004`** ("non-retryable agent error"), distinct from `PSALM-A003` ("retry
limit reached"), with `context.reason` naming the classification and `suggestion` tailored per
category — directly resolving the diagnosability gap (today, every failure produces the same
generic message regardless of cause).

## 5. Logging

`psalm/agents/base.py` gains `logger = logging.getLogger(__name__)` (module-qualified, so it's a
child of a `"psalm"`-rooted namespace an embedding application can configure at any granularity).
On each retry: `logger.warning(...)` with role/attempt/wait/error. On final failure (either
`PSALM-A003` or `PSALM-A004`): `logger.error(..., exc_info=True)`, capturing the full traceback and
`cause` chain that's already built (via `raise ... from exc`) but was previously never surfaced
anywhere. The SDK never configures handlers itself (standard library convention — a library
calling `logging.basicConfig()` internally can clobber an embedding application's own setup);
Python's `logging.lastResort` already prints `WARNING`+ to stderr with zero configuration, so this
works out of the box. `examples/web/backend/main.py` gains one `logging.basicConfig(...)` call at
startup — the natural place for a deployed app to own where its logs go.

## 6. Refactor: Shared Retry Loop

`_call_llm` and `_call_structured` currently duplicate the entire retry loop with only their
`ainvoke` target differing. Adding rate limiting, classification, and Retry-After-aware backoff to
both would triple that duplication and risk the two drifting out of sync. Both now delegate to a
single private helper:

```python
async def _execute_with_retry(self, messages: list[Any], invoke: Callable[[], Any]) -> Any:
    max_retries = self._execution.max_retries
    for attempt in range(max_retries):
        rate_limiter = self._execution.rate_limiter()
        if rate_limiter is not None:
            estimated_tokens = estimate_tokens(messages, self._config.model, self._config.max_tokens)
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
                    message=f"Non-retryable error from agent '{self.role}': {classification.reason}.",
                    context={
                        "role": self.role, "model": self._config.model,
                        "reason": classification.reason, "attempts": attempt + 1,
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
                    context={"role": self.role, "model": self._config.model, "attempts": max_retries},
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

Existing tests patch `type(agent._llm).ainvoke` / `structured_llm.ainvoke` directly rather than
`_call_llm`/`_call_structured` themselves, so this refactor preserves test compatibility — the
lambdas still call the exact same methods those tests already mock.

## 7. Config Surface

**`psalm/models/config.py` — `ExecutionConfig`** gains three fields, validated with `PSALM-C008`
(same code as existing fields, extended to accept `None`):
```python
class ExecutionConfig(BaseModel):
    max_concurrent_llm_calls: int = 8
    max_retries: int = 3
    backoff_factor: float = 2.0
    max_requests_per_minute: int | None = 60
    max_tokens_per_minute: int | None = 40000
    retry_after_fallback_seconds: float | None = None
```

**`psalm/builder.py` — `PSALM.with_execution(...)`** gains matching keyword arguments with
matching defaults, forwarded into `ExecutionConfig(...)` and, in `build()`, into `_RunExecution(...)`.

**`examples/web/backend/schemas.py` — `TrialConfigRequest`** gains three fields using `0` as the
web form's "disabled" convention (rather than `None`, which doesn't map cleanly onto a Mantine
`NumberInput`):
```python
    max_requests_per_minute: int = Field(default=60, ge=0)
    max_tokens_per_minute: int = Field(default=40000, ge=0)
    retry_after_fallback_seconds: float = Field(default=0, ge=0)
```

**`examples/web/backend/execution.py` — `build_psalm`** converts `0 → None` when forwarding (the
SDK's `ExecutionConfig` semantics use `None` for "disabled", not `0`, and `0` would fail SDK-side
validation if passed through literally):
```python
            .with_execution(
                max_concurrent_llm_calls=config.max_concurrent_llm_calls,
                max_retries=config.max_retries,
                max_requests_per_minute=config.max_requests_per_minute or None,
                max_tokens_per_minute=config.max_tokens_per_minute or None,
                retry_after_fallback_seconds=config.retry_after_fallback_seconds or None,
            )
```

**`examples/web/frontend/src/api/types.ts` — `TrialConfigInput`** gains the same three fields
(`number`). **`examples/web/frontend/src/routes/SetupPage.tsx`** gains three more `NumberInput`s in
the existing Advanced settings accordion, `min={0}` (unlike the existing concurrency/retry fields,
which use `min={1}` since 0 isn't meaningful for those — here `0` means "disabled"), defaulting to
60/40000/0, following the exact `useState` + payload-wiring pattern already established for
`max_concurrent_llm_calls`/`max_retries`.

## 8. Testing

- `_RateLimiter`: RPM cap respected, TPM cap respected, disabled (`None`/`None`) never blocks,
  `acquire()` waits and eventually succeeds once capacity refills — using a mocked/controlled
  clock (`time.monotonic`), not real multi-second sleeps.
- `estimate_tokens`: known text produces a token count in the expected ballpark; unknown model
  name falls back to `cl100k_base` without raising.
- `_extract_retry_after`/`_compute_backoff`: header present → used (clamped); header absent +
  fallback configured → fallback used; neither → existing jittered-exponential behavior preserved
  bit-for-bit (regression test against the pre-existing backoff tests).
- `_classify_error`: table-driven, one case per exception type/code combination in §4, asserting
  both `retryable` and `reason`.
- `_execute_with_retry` (via `_call_llm`/`_call_structured`, matching how the existing retry tests
  already exercise this): fail-fast path raises `PSALM-A004` with zero `asyncio.sleep` calls and
  without consuming the full retry budget; retryable path behaves as today's tests already assert,
  now additionally verified to call `rate_limiter.acquire(...)` before each attempt when a limiter
  is configured, and to skip it entirely when unconfigured (`None`).
- Logging: `caplog`-based tests confirming a `WARNING` on retry and an `ERROR` with `exc_info` set
  on final failure (both `PSALM-A003` and `PSALM-A004` paths).
- `ExecutionConfig`: defaults, custom values, and `PSALM-C008` validation for the three new fields
  (including that `None` is accepted, unlike the pre-existing fields).
- Web backend: `TrialConfigRequest` accepts/validates the three new fields (`ge=0`); `build_psalm`
  forwards them with the `0 → None` translation verified explicitly (a `0` in the request must
  reach `.with_execution(...)` as `None`, not `0`).
- Web frontend: `SetupPage.tsx` renders the three new fields with correct defaults/ids and forwards
  them in the `startTrial(...)` payload — extending the existing payload-assertion test, matching
  the pattern from the concurrency-config feature. `npm run build` (not just `npm test`) is run as
  part of verification, per the lesson from that feature's post-merge `tsc -b` failure.
- Full SDK, web-backend, and web-frontend suites re-run at the end.

## 9. Error Handling

No new failure modes beyond the two documented error codes. `PSALM-A004` (fail-fast) and the
existing `PSALM-A003` (retry-exhausted) both continue to carry `cause=exc` (the original exception,
preserved via `from exc`), now additionally logged with a full traceback via `exc_info=True` —
so nothing that previously surfaced is lost, only made more visible and, for the fail-fast case,
faster to reach (no wasted retry attempts on a permanent failure).

## 10. Files Added / Modified

**Added:**
- `psalm/agents/rate_limiter.py` — `_RateLimiter`, `estimate_tokens` (§2)
- `tests/unit/agents/test_rate_limiter.py`

**Modified:**
- `psalm/agents/base.py` — `_RunExecution.rate_limiter()`, `_execute_with_retry`,
  `_classify_error`/`_ErrorClassification`, `_compute_backoff`/`_extract_retry_after`, logging,
  `_call_llm`/`_call_structured` refactored to delegate (§2, §3, §4, §5, §6)
- `psalm/models/config.py` — `ExecutionConfig` gains 3 fields (§7)
- `psalm/builder.py` — `PSALM.with_execution(...)` gains 3 kwargs, `build()` forwards them (§7)
- `pyproject.toml` — `tiktoken` becomes a direct dependency (§2)
- `examples/web/backend/schemas.py` — `TrialConfigRequest` gains 3 fields (§7)
- `examples/web/backend/execution.py` — `build_psalm` forwards + translates `0 → None` (§7)
- `examples/web/backend/main.py` — one `logging.basicConfig(...)` call (§5)
- `examples/web/frontend/src/api/types.ts`, `examples/web/frontend/src/routes/SetupPage.tsx` (§7)
- Corresponding test files under `tests/unit/agents/`, `tests/unit/models/`, `tests/unit/`,
  `examples/web/backend/tests/`, `examples/web/frontend/src/routes/` (§8)

**Unchanged:** `psalm/courtroom/default.py`, `psalm/phases/deliberation.py` (no existing
`asyncio.gather` call site changes, consistent with the concurrency-config feature's constraint);
`DebateConfig` (rate-limit settings stay in `ExecutionConfig`, not folded in); the web app's SSE
event shape (`AgentCallRetrying`/`AgentCallFailed` gain no new fields — `PSALM-A004` reuses the
existing `code: str` field on `AgentCallFailed`, no frontend event-type change needed).

## 11. Breaking Changes

None functionally — every new field is optional with a default that preserves or improves current
behavior (rate limiter defaults to *on* with conservative values rather than *unlimited*, which is
a behavior change from today, but one specifically requested to fix the reported bug out of the
box; everything else defaults to `None`/unchanged). The `_call_llm`/`_call_structured` → shared
`_execute_with_retry` refactor (§6) changes internal structure but not either method's public
signature or externally observable behavior for existing callers/tests.
