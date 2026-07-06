from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.dimensions.base import Dimension
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument


class _ArgumentList(BaseModel):
    arguments: list[Argument]


_SYSTEM_PROMPT = """\
You are a legal prosecutor in a copyright infringement case governed by EU copyright law.
Your goal is to argue that the target text infringes the source's copyright.

PRIORITIZE these argument types (strongest first):
1. Near-verbatim or closely paraphrased passages — the same distinctive words or phrases appear
   in both texts, even with minor substitutions.
2. A unique metaphor, image, or narrative detail that appears in both texts.
3. Highly specific plot details that could not be independently invented — same names, same
   events, same distinctive sequence of choices.

If none of the above exist, present weaker arguments based on structural similarities,
shared character archetypes, genre conventions, or abstract themes — be aware the defense will
challenge those as legally unprotectable ideas under EU law. Make the argument anyway: the
debate must proceed and the defense will rebut.

Every argument must include relevant passages from both texts. Quote as closely as possible to
the original; close approximations are acceptable. You MUST produce at least one argument —
if strong evidence is absent, make the best case available so the debate can proceed.
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
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
                    f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
                    f"Dimensions to analyze: {', '.join(d.name for d in dimensions)}\n"
                    f"Round: {round}{rebuttal_section}\n\n"
                    "Provide arguments with relevant passages from both texts."
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
