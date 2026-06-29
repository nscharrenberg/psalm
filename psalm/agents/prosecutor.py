from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument


class _ArgumentList(BaseModel):
    arguments: list[Argument]


_SYSTEM_PROMPT = """\
You are a legal prosecutor in a copyright infringement case governed by EU copyright law.
Analyze the provided texts and identify evidence of copyright infringement for each dimension.
For each dimension, construct structured arguments backed by verbatim excerpts from both texts.
Every argument MUST include at least one proof with verbatim excerpts from both the source and
target texts. Focus on substantial similarity of protected creative expression — ignore generic
tropes and unprotectable elements.
"""


class Prosecutor(BaseAgent):
    @property
    def role(self) -> str:
        return "prosecutor"

    async def gather_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[str],
        round: int,
    ) -> list[Argument]:
        structured_llm = self._llm.with_structured_output(_ArgumentList)
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
                    f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
                    f"Dimensions to analyze: {', '.join(dimensions)}\n"
                    f"Round: {round}\n\n"
                    "For each dimension, provide arguments with verbatim proof excerpts from "
                    "both texts."
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return [
                a.model_copy(update={"round": round, "agent_role": "prosecutor"})
                for a in result.arguments
            ]
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Prosecutor failed to return valid structured arguments.",
                context={"role": self.role, "round": round, "dimensions": dimensions},
                suggestion=(
                    "Check the LLM model supports structured output and the prompt is not too "
                    "long."
                ),
                cause=exc,
            ) from exc
