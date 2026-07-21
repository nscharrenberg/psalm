from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.dimensions.base import Dimension
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument, ArgumentBatch


class _ClosingArgument(BaseModel):
    statement: str


def _format_case_history(
    prosecution_arguments: list[Argument],
    prosecution_counters: list[Argument],
    defense_counters: list[Argument],
    defense_arguments: list[Argument],
) -> str:
    lines: list[str] = []
    own_args = prosecution_arguments + prosecution_counters
    opposing_args = defense_counters + defense_arguments

    lines.append("YOUR SIDE'S SURVIVING ARGUMENTS (prosecution):")
    if own_args:
        for arg in own_args:
            lines.append(f"  - [{arg.dimension}] {arg.claim}")
            for p in arg.proofs:
                lines.append(f'      Source: "{p.source_excerpt}"')
                lines.append(f'      Target: "{p.target_excerpt}"')
    else:
        lines.append("  (none survived judge validation)")

    lines.append("OPPOSING SIDE'S SURVIVING ARGUMENTS (defense):")
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
You are a legal prosecutor in a copyright infringement case governed by EU copyright law.
Your goal is to argue that the target text infringes the source's copyright.

Surface all genuine similarities between the texts — the court filters; you argue.

PRIORITIZE these argument types (strongest first):
1. Near-verbatim or closely paraphrased passages — the same distinctive words or phrases appear
   in both texts, even with minor substitutions.
2. A unique metaphor, image, or narrative detail that appears in both texts.
3. Highly specific plot details that could not be independently invented — same names, same
   events, same distinctive sequence of choices.
4. Structural or expression-level similarities (genre conventions, shared archetypes) — the
   debate must proceed even when only weaker signals exist, but never fabricate a signal that
   isn't there.

Only assert claims backed by clear, unambiguous textual evidence. If no such evidence exists for
a sub-dimension, do not argue it — omit it. Never present a guess, inference, or possibility as
if it were a settled fact. Quote as closely as possible to the original; close approximations of
the wording are acceptable, but the underlying claim of similarity must be certain, not
speculative.

For each argument, identify the specific textual proof first, then state the claim that proof
supports — not the other way around.

If you have nothing further that meets this bar — for this call, across every sub-dimension you
were asked to address — set no_further_arguments=True and provide a one-sentence
closing_statement explaining why (e.g. "All HIGH and CRITICAL sub-dimensions have been argued
with the available evidence" or "No further unambiguous similarities remain in the text"). Do
not pad with a weak or speculative claim just to appear productive.
If you are rebutting defense arguments from prior rounds, directly address their challenge.
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
        retry_hint: str | None = None,
    ) -> ArgumentBatch:
        structured_llm = self._llm.with_structured_output(ArgumentBatch)
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
        retry_section = f"\n\n{retry_hint}" if retry_hint else ""
        content = (
            f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
            f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}{rebuttal_section}{retry_section}\n\n"
            "Provide arguments with relevant passages from both texts, for every sub-dimension "
            "where clear, unambiguous evidence exists. If none exists anywhere, declare "
            "no_further_arguments."
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            arguments = [
                a.model_copy(update={"round": round, "agent_role": "prosecutor"})
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
                message="Prosecutor failed to return valid structured arguments.",
                context={
                    "role": self.role,
                    "round": round,
                    "dimensions": [d.name for d in dimensions],
                },
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
        retry_hint: str | None = None,
    ) -> ArgumentBatch:
        """Step 4: Prosecution counters defense's affirmative arguments."""
        structured_llm = self._llm.with_structured_output(ArgumentBatch)
        dim_names = ", ".join(d.name for d in dimensions)
        defense_text = "\n".join(
            f"- [{a.dimension}] {a.claim}" for a in defense_arguments
        )
        retry_section = f"\n\n{retry_hint}" if retry_hint else ""
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
                    f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
                    f"Dimensions: {dim_names}\nRound: {round}\n\n"
                    f"Defense affirmative arguments to rebut:\n{defense_text}\n\n"
                    "Counter each defense argument only where you have clear, unambiguous "
                    "grounds: show why their claimed differences are insufficient to rule out "
                    "infringement, or present additional similarities the defense ignored. If "
                    f"no such grounds exist, declare no_further_arguments.{retry_section}"
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            arguments = [
                a.model_copy(update={"round": round, "agent_role": "prosecutor"})
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
                message="Prosecutor failed to counter defense arguments.",
                context={
                    "role": self.role,
                    "round": round,
                    "dimensions": [d.name for d in dimensions],
                },
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc

    async def deliver_closing_argument(
        self,
        dimensions: list[Dimension],
        prosecution_arguments: list[Argument],
        prosecution_counters: list[Argument],
        defense_counters: list[Argument],
        defense_arguments: list[Argument],
    ) -> str:
        """Delivered once, after the round loop ends, regardless of how the debate went.

        Deliberately has no access to the raw source/target text — only to arguments that
        already survived judge validation — so it cannot introduce comparisons the Judge
        never had a chance to check.
        """
        structured_llm = self._llm.with_structured_output(_ClosingArgument)
        case_history = _format_case_history(
            prosecution_arguments, prosecution_counters, defense_counters, defense_arguments
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
                    "surviving evidence for infringement, address the defense's strongest "
                    "surviving points, and make your final case to the jury. If your side has "
                    "no surviving arguments, say so plainly rather than introducing new claims."
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
                message="Prosecutor failed to deliver a closing argument.",
                context={"role": self.role, "dimensions": [d.name for d in dimensions]},
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc
