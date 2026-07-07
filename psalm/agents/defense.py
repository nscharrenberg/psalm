from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.dimensions.base import Dimension
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument, ArgumentBatch


class _ClosingArgument(BaseModel):
    statement: str


def _format_case_history(
    defense_counters: list[Argument],
    defense_arguments: list[Argument],
    prosecution_arguments: list[Argument],
    prosecution_counters: list[Argument],
) -> str:
    lines: list[str] = []
    own_args = defense_counters + defense_arguments
    opposing_args = prosecution_arguments + prosecution_counters

    lines.append("YOUR SIDE'S SURVIVING ARGUMENTS (defense):")
    if own_args:
        for arg in own_args:
            lines.append(f"  - [{arg.dimension}] {arg.claim}")
            for p in arg.proofs:
                lines.append(f'      Source: "{p.source_excerpt}"')
                lines.append(f'      Target: "{p.target_excerpt}"')
    else:
        lines.append("  (none survived judge validation)")

    lines.append("OPPOSING SIDE'S SURVIVING ARGUMENTS (prosecution):")
    if opposing_args:
        for arg in opposing_args:
            lines.append(f"  - [{arg.dimension}] {arg.claim}")
            for p in arg.proofs:
                lines.append(f'      Source: "{p.source_excerpt}"')
                lines.append(f'      Target: "{p.target_excerpt}"')
    else:
        lines.append("  (none survived judge validation)")

    return "\n".join(lines)


def _format_sub_dimensions(dimensions: list[Dimension]) -> str:
    lines: list[str] = []
    infringement_dims = [d for d in dimensions if d.dimension_type == "infringement"]
    exception_dims = [d for d in dimensions if d.dimension_type == "exception"]

    # When no infringement dimension is present, the exception dimension(s) are the sole
    # subject of this pipeline's own verdict and must be argued directly — not treated as
    # optional tools for a dimension that isn't in the room.
    mandatory_dims = infringement_dims or exception_dims
    optional_dims = exception_dims if infringement_dims else []

    for dim in mandatory_dims:
        lines.append(f"\nPRIMARY DIMENSION (must argue): {dim.name} — {dim.description}")
        lines.append(
            "Sub-dimensions (argue ALL marked HIGH or CRITICAL where factually supportable):"
        )
        for sd in dim.sub_dimensions:
            lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")

    for dim in optional_dims:
        lines.append(
            f"\nAVAILABLE EXCEPTION TOOLS (optional, cite only if relevant): "
            f"{dim.name} — {dim.description}"
        )
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

Only assert claims backed by clear, unambiguous textual evidence. If no such evidence exists for
a prosecution argument or a sub-dimension, do not argue it — omit it. Never present a guess,
inference, or possibility as if it were a settled fact. Quote as closely as possible to the
original; close approximations of the wording are acceptable, but the underlying claim must be
certain, not speculative.

For each prosecution argument, decide: does it rest on an unprotectable idea (challenge as
legally insufficient) or on specific expression (challenge on the merits)?

If you have nothing further that meets this bar — for this call, across every prosecution
argument and sub-dimension you were asked to address — set no_further_arguments=True and provide
a one-sentence closing_statement explaining why. Do not pad with a weak or speculative claim just
to appear productive.
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
        retry_hint: str | None = None,
    ) -> ArgumentBatch:
        structured_llm = self._llm.with_structured_output(ArgumentBatch)
        args_text = "\n".join(
            f"- [{a.dimension}] {a.claim} (proofs: {len(a.proofs)})"
            for a in prosecutor_arguments
        )
        if prosecutor_arguments:
            instruction = (
                "Counter each prosecution argument where you have clear grounds (unprotectable "
                "ideas, lack of expression-level similarity, independent creation). "
                "Additionally, you may make an affirmative argument about why the texts are "
                "independently created — cite specific passages where the expression and "
                "creative choices diverge. If no clear grounds exist anywhere, declare "
                "no_further_arguments."
            )
        else:
            instruction = (
                "The prosecution has not yet raised any arguments. You may make affirmative "
                "arguments about why the target text does NOT infringe the source — highlight "
                "specific passages where the wording, imagery, and creative choices are "
                "independently created. If no clear, unambiguous grounds exist, declare "
                "no_further_arguments."
            )
        sub_dim_block = _format_sub_dimensions(dimensions)
        retry_section = f"\n\n{retry_hint}" if retry_hint else ""
        content = (
            f"SOURCE TEXT:\n{source_text}\n\n"
            f"TARGET TEXT:\n{target_text}\n\n"
            f"Prosecutor's arguments:\n{args_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}\n\n"
            f"{instruction}{retry_section}"
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            arguments = [
                a.model_copy(update={"round": round, "agent_role": "defense"})
                for a in result.arguments
            ]
            return ArgumentBatch(
                arguments=arguments,
                no_further_arguments=result.no_further_arguments,
                closing_statement=result.closing_statement,
            )
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
        retry_hint: str | None = None,
    ) -> ArgumentBatch:
        """Step 3: Defense makes independent affirmative arguments (no prosecution args to counter)."""
        structured_llm = self._llm.with_structured_output(ArgumentBatch)
        sub_dim_block = _format_sub_dimensions(dimensions)
        retry_section = f"\n\n{retry_hint}" if retry_hint else ""
        content = (
            f"SOURCE TEXT:\n{source_text}\n\n"
            f"TARGET TEXT:\n{target_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}\n\n"
            "Make affirmative arguments about why the target text does NOT infringe the "
            "source, for each HIGH and CRITICAL sub-dimension where clear, unambiguous evidence "
            "exists. Highlight specific passages where the wording, imagery, and creative "
            "choices are distinctly different. If no such evidence exists anywhere, declare "
            f"no_further_arguments.{retry_section}"
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            arguments = [
                a.model_copy(update={"round": round, "agent_role": "defense"})
                for a in result.arguments
            ]
            return ArgumentBatch(
                arguments=arguments,
                no_further_arguments=result.no_further_arguments,
                closing_statement=result.closing_statement,
            )
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

    async def deliver_closing_argument(
        self,
        dimensions: list[Dimension],
        defense_counters: list[Argument],
        defense_arguments: list[Argument],
        prosecution_arguments: list[Argument],
        prosecution_counters: list[Argument],
    ) -> str:
        """Delivered once, after the round loop ends, regardless of how the debate went.

        Deliberately has no access to the raw source/target text — only to arguments that
        already survived judge validation — so it cannot introduce comparisons the Judge
        never had a chance to check.
        """
        structured_llm = self._llm.with_structured_output(_ClosingArgument)
        case_history = _format_case_history(
            defense_counters, defense_arguments, prosecution_arguments, prosecution_counters
        )
        dim_names = ", ".join(d.name for d in dimensions)
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Dimensions: {dim_names}\n\n"
                    f"{case_history}\n\n"
                    "The argumentation rounds are complete. Deliver your closing argument using "
                    "ONLY the surviving arguments and proofs listed above — you do not have "
                    "access to the full source or target text here, and must not invent or "
                    "recall passages beyond what is quoted above. Summarize the strongest "
                    "surviving evidence for non-infringement, address the prosecution's "
                    "strongest surviving points, and make your final case to the jury. If your "
                    "side has no surviving arguments, say so plainly rather than introducing "
                    "new claims."
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.statement
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Defense failed to deliver a closing argument.",
                context={"role": self.role, "dimensions": [d.name for d in dimensions]},
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc
