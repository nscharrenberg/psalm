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
You are a defense attorney in a copyright infringement case governed by EU copyright law.
Challenge the prosecutor's arguments AND make proactive affirmative claims about the texts.

PRIMARY TOOLS for countering prosecution arguments:

1. IDEA-EXPRESSION DICHOTOMY (most powerful): Under EU copyright law, only specific creative
   expression is protected — not ideas, themes, concepts, or genre conventions. When the
   prosecution argues that both texts share a character type, theme, setting, or plot device,
   explicitly name this as an unprotectable idea and explain why it is not infringement.
   Examples to challenge: "both characters are liars", "both experience betrayal",
   "both set in an industrial city", "both have a mentor figure".

2. LACK OF EXPRESSION-LEVEL SIMILARITY: Even where concepts overlap, show that the specific
   wording, imagery, and narrative choices differ — different words, different details,
   different emotional register.

3. INDEPENDENT CREATION: Show that the claimed similarities are genre conventions or common
   literary devices that any author could independently create without access to the source.

AFFIRMATIVE ARGUMENTS — you may also proactively argue why the texts are distinct:
- Point to specific passages where the writing styles, structures, or narrative choices
  diverge significantly, even if the prosecution has not raised those passages.
- Highlight distinctive elements in each text that have no counterpart in the other.
- Argue that the overall creative expression is so different that no reasonable reader
  would confuse the two works.

For each prosecution argument, decide: does it rest on an unprotectable idea (challenge as
legally insufficient) or on specific expression (challenge on the merits)?
Every argument must include relevant passages from both texts. Quote as closely as possible
to the original; close approximations are acceptable. You MUST produce at least one argument.
"""


class Defense(BaseAgent):
    @property
    def role(self) -> str:
        return "defense"

    async def gather_counter_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[Dimension],
        prosecutor_arguments: list[Argument],
        round: int,
    ) -> list[Argument]:
        structured_llm = self._llm.with_structured_output(_ArgumentList)
        args_text = "\n".join(
            f"- [{a.dimension}] {a.claim} (proofs: {len(a.proofs)})"
            for a in prosecutor_arguments
        )
        if prosecutor_arguments:
            instruction = (
                "Counter each prosecution argument by identifying weaknesses (unprotectable "
                "ideas, lack of expression-level similarity, independent creation). "
                "Additionally, make at least one affirmative argument about why the texts are "
                "independently created — cite specific passages where the expression and "
                "creative choices diverge. You MUST produce at least one argument."
            )
        else:
            instruction = (
                "The prosecution has not yet raised any arguments. Make affirmative arguments "
                "about why the target text does NOT infringe the source — highlight specific "
                "passages where the wording, imagery, and creative choices are independently "
                "created. The prosecution will counter your arguments in the next round. "
                "You MUST produce at least one argument."
            )
        sub_dim_block = _format_sub_dimensions(dimensions)
        content = (
            f"SOURCE TEXT:\n{source_text}\n\n"
            f"TARGET TEXT:\n{target_text}\n\n"
            f"Prosecutor's arguments:\n{args_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}\n\n"
            f"{instruction}"
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
                a.model_copy(update={"round": round, "agent_role": "defense"})
                for a in result.arguments
            ]
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

    async def gather_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[Dimension],
        round: int,
    ) -> list[Argument]:
        """Step 3: Defense makes independent affirmative arguments (no prosecution args to counter)."""
        structured_llm = self._llm.with_structured_output(_ArgumentList)
        sub_dim_block = _format_sub_dimensions(dimensions)
        content = (
            f"SOURCE TEXT:\n{source_text}\n\n"
            f"TARGET TEXT:\n{target_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}\n\n"
            "Make affirmative arguments about why the target text does NOT infringe the "
            "source. Address each HIGH and CRITICAL sub-dimension. Highlight specific passages "
            "where the wording, imagery, and creative choices are distinctly different. "
            "You MUST produce at least one argument."
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
                a.model_copy(update={"round": round, "agent_role": "defense"})
                for a in result.arguments
            ]
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Defense failed to produce affirmative arguments.",
                context={"role": self.role, "round": round},
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc
