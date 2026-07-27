from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import openai
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from psalm.agents.rate_limiter import _RateLimiter, estimate_tokens
from psalm.events import AgentCallFailed, AgentCallRetrying, emit
from psalm.exceptions import PSALMAgentError
from psalm.models.config import AgentConfig


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


logger = logging.getLogger(__name__)


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


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, execution: _RunExecution) -> None:
        self._config = config
        self._execution = execution
        self._llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=SecretStr(config.api_key) if config.api_key else None,
            organization=config.org_id,
            model=config.model,
            temperature=config.temperature,
            max_completion_tokens=config.max_tokens,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            seed=config.seed,
            timeout=config.timeout_seconds,
        )

    @property
    @abstractmethod
    def role(self) -> str: ...

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
                            f"Non-retryable error from agent '{self.role}': "
                            f"{classification.reason}."
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
