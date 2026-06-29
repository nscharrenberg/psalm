from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument
from psalm.models.result import ArgumentationLog, JurorVote, ValidationResult


class _CrossExamDecision(BaseModel):
    should_cross_examine: bool
    reasoning: str


class _StabilityDecision(BaseModel):
    stability_detected: bool
    reasoning: str


class _TiebreakDecision(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str


_VALIDATION_PROMPT = """\
You are a judge validating an attorney's argument in a copyright case governed by EU copyright law.
Reject the argument (is_valid=false) if ANY of the following criteria fails:

(1) The argument includes at least one proof with actual verbatim excerpts from both texts.
(2) The excerpts are genuinely from the provided texts, not paraphrased or invented.
(3) The reasoning is relevant to the claimed dimension.
(4) MOST IMPORTANT — the argument demonstrates similarity in PROTECTED CREATIVE EXPRESSION,
    not merely in ideas, themes, concepts, or genre conventions.

For criterion (4), REJECT arguments that only show:
- Shared character types or personality traits: "both protagonists are liars / traumatized /
  isolated" — being a liar is an idea, not protected expression.
- Shared plot devices or themes: "both experience betrayal", "both have a mentor figure".
- Shared settings or genre elements: "both set in an industrial city", "both feature a clock
  tower", "both have a dark underworld" — these are genre conventions, not protected.
- Physical marks that differ in specifics: "one has a scar, one has a tattoo" — different
  objects with different origins are not similar expression.
- Traits expressed in OPPOSITE ways: if one character's face betrays them and the other's does
  not, that is contrast, not similarity — reject as misleading.

ACCEPT arguments that show:
- Near-verbatim or closely paraphrased text: the same distinctive words or phrases appear in
  both texts (even with minor substitutions).
- A unique metaphor, image, or simile that appears in both texts with similar wording.
- Highly specific plot details that are distinctively similar beyond coincidence.

If the proofs only show the same IDEA expressed in different words, set is_valid=false and
state the rejection_reason clearly.
"""


class Judge(BaseAgent):
    @property
    def role(self) -> str:
        return "judge"

    async def validate_argument(
        self, argument: Argument, source_text: str, target_text: str
    ) -> ValidationResult:
        structured_llm = self._llm.with_structured_output(ValidationResult)
        proofs_text = "\n".join(
            f"  Source: '{p.source_excerpt}'\n  Target: '{p.target_excerpt}'\n"
            f"  Relevance: {p.relevance}"
            for p in argument.proofs
        )
        prompt = [
            {"role": "system", "content": _VALIDATION_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Argument claim: {argument.claim}\n"
                    f"Dimension: {argument.dimension}\n"
                    f"Proofs:\n{proofs_text}\n\n"
                    f"Full source text:\n{source_text}\n\n"
                    f"Full target text:\n{target_text}"
                ),
            },
        ]
        try:
            return await self._call_structured(structured_llm, prompt)
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Judge failed to validate argument.",
                context={"role": self.role, "claim": argument.claim},
                suggestion="Check LLM supports structured output.",
                cause=exc,
            ) from exc

    async def should_cross_examine(
        self, arguments: list[Argument], counter_arguments: list[Argument]
    ) -> bool:
        structured_llm = self._llm.with_structured_output(_CrossExamDecision)
        args_text = "\n".join(f"- [{a.dimension}] {a.claim}" for a in arguments)
        counter_text = "\n".join(f"- [{a.dimension}] {a.claim}" for a in counter_arguments)
        system_content = (
            "You are a judge deciding if cross-examination is warranted. Cross-examine only "
            "when there are genuine discrepancies or alternative interpretations worth exploring."
        )
        user_content = (
            f"Arguments:\n{args_text}\n\nCounter-arguments:\n{counter_text}\n\n"
            "Should cross-examination occur?"
        )
        prompt = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.should_cross_examine
        except Exception:
            return False  # safe fallback — phase continues

    async def detect_stability(
        self, current_arguments: list[Argument], previous_arguments: list[Argument]
    ) -> bool:
        if not previous_arguments:
            return False
        current_claims = {a.claim for a in current_arguments}
        previous_claims = {a.claim for a in previous_arguments}
        return current_claims == previous_claims

    async def tiebreak(
        self, votes: list[JurorVote], argumentation_log: ArgumentationLog
    ) -> Literal["Guilty", "Not Guilty", "Undecided"]:
        structured_llm = self._llm.with_structured_output(_TiebreakDecision)
        votes_text = "\n".join(f"- {v.juror_id}: {v.vote} — {v.rationale}" for v in votes)
        rounds_text = "\n".join(
            f"Round {r.round}: {len(r.arguments)} arguments, "
            f"{len(r.counter_arguments)} counter-arguments"
            for r in argumentation_log.rounds
        )
        system_content = (
            "You are a judge casting a tiebreaker vote in a copyright case. Base your "
            "decision on the totality of the evidence and arguments."
        )
        user_content = (
            f"Jury votes (tied):\n{votes_text}\n\nArgumentation summary:\n{rounds_text}\n\n"
            "Cast your tiebreaker verdict."
        )
        prompt = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.verdict
        except Exception:
            return "Undecided"  # safe fallback
