from __future__ import annotations
from typing import Any


class PSALMError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        context: dict[str, Any] | None = None,
        suggestion: str = "",
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.context = context or {}
        self.suggestion = suggestion
        self.cause = cause
        super().__init__(self._format())

    def _format(self) -> str:
        lines = [f"{type(self).__name__} [{self.code}]: {self.message}"]
        if self.context:
            lines.append(f"  Context: {self.context}")
        if self.suggestion:
            lines.append(f"  Suggestion: {self.suggestion}")
        return "\n".join(lines)


class PSALMConfigError(PSALMError):
    """PSALM-C* — raised at .build() for bad configuration."""


class PSALMValidationError(PSALMError):
    """PSALM-V* — raised at .evaluate() for invalid inputs."""


class PSALMRuntimeError(PSALMError):
    """PSALM-R* — recoverable phase-level failure, recorded in metadata."""


class PSALMAgentError(PSALMError):
    """PSALM-A* — LLM-level failure."""
