from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from langchain_openai import ChatOpenAI

from psalm.exceptions import PSALMAgentError
from psalm.models.config import AgentConfig

_RETRY_ATTEMPTS = 3
_BACKOFF_FACTOR = 2.0


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            organization=config.org_id,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
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
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                return await self._llm.ainvoke(messages)
            except Exception as exc:
                if attempt == _RETRY_ATTEMPTS - 1:
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=f"LLM retry limit reached after {_RETRY_ATTEMPTS} attempts.",
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": _RETRY_ATTEMPTS,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                await asyncio.sleep(_BACKOFF_FACTOR**attempt)
        raise RuntimeError("unreachable")

    async def _call_structured(self, structured_llm: Any, messages: list[Any]) -> Any:
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                return await structured_llm.ainvoke(messages)
            except Exception as exc:
                if attempt == _RETRY_ATTEMPTS - 1:
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=(
                            f"Structured LLM retry limit reached after {_RETRY_ATTEMPTS} attempts."
                        ),
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": _RETRY_ATTEMPTS,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                await asyncio.sleep(_BACKOFF_FACTOR**attempt)
        raise RuntimeError("unreachable")
