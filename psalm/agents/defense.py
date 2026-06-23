from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument


class _ArgumentList(BaseModel):
    arguments: list[Argument]


_SYSTEM_PROMPT = """\
You are a defense attorney in a copyright infringement case governed by EU copyright law.
Challenge the prosecutor's arguments by providing counter-evidence showing the target text does
not infringe. Focus on: (1) alternative interpretations, (2) lack of substantial similarity in
protected elements, (3) elements that are generic, unprotectable, or independently created.
Every counter-argument MUST include at least one proof with verbatim excerpts from both texts.
"""


class Defense(BaseAgent):
    @property
    def role(self) -> str:
        return "defense"

    async def gather_counter_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[str],
        prosecutor_arguments: list[Argument],
        round: int,
    ) -> list[Argument]:
        structured_llm = self._llm.with_structured_output(_ArgumentList)
        args_text = "\n".join(
            f"- [{a.dimension}] {a.claim} (proofs: {len(a.proofs)})"
            for a in prosecutor_arguments
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE TEXT:\n{source_text}\n\n"
                    f"TARGET TEXT:\n{target_text}\n\n"
                    f"Prosecutor's arguments:\n{args_text}\n\n"
                    f"Dimensions: {', '.join(dimensions)}\nRound: {round}\n\n"
                    "Provide counter-arguments with verbatim proof excerpts from both texts."
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.arguments
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Defense failed to return valid structured counter-arguments.",
                context={"role": self.role, "round": round},
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc
