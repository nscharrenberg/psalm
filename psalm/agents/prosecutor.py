from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument


class _ArgumentList(BaseModel):
    arguments: list[Argument]


_SYSTEM_PROMPT = """\
You are a legal prosecutor in a copyright infringement case governed by EU copyright law.
Identify only arguments where the target text copies the source's PROTECTED creative expression.

DO NOT argue the following — they are legally unprotectable and will be dismissed:
- Shared character archetypes or personality traits ("both protagonists are liars/isolated/traumatized")
- Common plot devices ("both experience betrayal", "both have a mentor")
- Genre conventions or settings ("both set in an industrial city", "both feature a clock tower")
- Abstract themes or emotions ("both explore trust and deception", "both deal with grief")
- Physical traits that differ in expression ("one has a scar, one has a tattoo")

ONLY argue where you can show the target copied specific creative EXPRESSION from the source:
- Near-verbatim or closely paraphrased passages (same distinctive words or phrases)
- A unique metaphor, image, or narrative detail that appears in both texts
- Highly specific plot details that could not be independently invented (same names, same events,
  same distinctive sequence of choices)

Every argument MUST include verbatim excerpts from BOTH texts. If the excerpts only show that
both texts use the same idea but with different words, do not make that argument.
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
