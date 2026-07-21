from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from psalm.events import AgentCallFailed, AgentCallRetrying, emit
from psalm.exceptions import PSALMAgentError
from psalm.models.config import AgentConfig


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
