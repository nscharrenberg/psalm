from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.dimensions.base import Dimension
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument


class _ArgumentList(BaseModel):
    arguments: list[Argument]


def _format_sub_dimensions(dimensions: list[Dimension]) -> str:
    lines: list[str] = []
    for dim in dimensions:
        lines.append(
            f"\nDimension: {dim.name} — {dim.description}"
        )
        lines.append("Sub-dimensions (argue ALL marked HIGH or CRITICAL):")
        for sd in dim.sub_dimensions:
            lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")
    return "\n".join(lines)


_SYSTEM_PROMPT = """\
You are a legal prosecutor in a copyright infringement case governed by EU copyright law.
Your goal is to argue that the target text infringes the source's copyright.

Surface ALL similarities between the texts — the court filters; you argue.

PRIORITIZE these argument types (strongest first):
1. Near-verbatim or closely paraphrased passages — the same distinctive words or phrases appear
   in both texts, even with minor substitutions.
2. A unique metaphor, image, or narrative detail that appears in both texts.
3. Highly specific plot details that could not be independently invented — same names, same
   events, same distinctive sequence of choices.
4. Structural or expression-level similarities (genre conventions, shared archetypes) — present
   these even if the defense may rebut them. The debate must proceed.

You MUST produce at least one argument per HIGH and CRITICAL sub-dimension where any similarity
exists — including generic or weak ones. Every argument must include relevant passages from both
texts. Quote as closely as possible to the original; close approximations are acceptable.
"""


class Prosecutor(BaseAgent):
    @property
    def role(self) -> str:
        return "prosecutor"

    async def gather_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[Dimension],
        round: int,
        prior_defense_arguments: list[Argument] | None = None,
    ) -> list[Argument]:
        structured_llm = self._llm.with_structured_output(_ArgumentList)
        rebuttal_section = ""
        if prior_defense_arguments:
            rebuttals = "\n".join(
                f"- [{a.dimension}] {a.claim}" for a in prior_defense_arguments
            )
            rebuttal_section = (
                f"\n\nDefense counter-arguments from prior rounds (rebut these directly):\n"
                f"{rebuttals}\n"
                "Address these challenges in your arguments — explain why the defense is wrong "
                "or present new evidence they did not counter."
            )
        sub_dim_block = _format_sub_dimensions(dimensions)
        content = (
            f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
            f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}{rebuttal_section}\n\n"
            "Provide arguments with relevant passages from both texts. "
            "For each HIGH and CRITICAL sub-dimension, produce at least one argument."
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": content,
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
                context={"role": self.role, "round": round, "dimensions": [d.name for d in dimensions]},
                suggestion=(
                    "Check the LLM model supports structured output and the prompt is not too "
                    "long."
                ),
                cause=exc,
            ) from exc

    async def gather_counter_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[Dimension],
        defense_arguments: list[Argument],
        round: int,
    ) -> list[Argument]:
        """Step 4: Prosecution counters defense's affirmative arguments."""
        structured_llm = self._llm.with_structured_output(_ArgumentList)
        dim_names = ", ".join(d.name for d in dimensions)
        defense_text = "\n".join(
            f"- [{a.dimension}] {a.claim}" for a in defense_arguments
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
                    f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
                    f"Dimensions: {dim_names}\nRound: {round}\n\n"
                    f"Defense affirmative arguments to rebut:\n{defense_text}\n\n"
                    "Counter each defense argument: show why their claimed differences are "
                    "insufficient to rule out infringement, or present additional similarities "
                    "the defense ignored. You MUST produce at least one argument."
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
                message="Prosecutor failed to counter defense arguments.",
                context={"role": self.role, "round": round, "dimensions": [d.name for d in dimensions]},
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc
