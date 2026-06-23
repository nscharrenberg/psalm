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
You are a judge validating an attorney's argument in a copyright case.
Check: (1) does the argument have at least one proof with actual verbatim excerpts from both texts?
(2) are the excerpts genuinely from the provided texts? (3) is the reasoning relevant to the dimension?
Respond with is_valid and rejection_reason if invalid.
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
            f"  Source: '{p.source_excerpt}'\n  Target: '{p.target_excerpt}'\n  Relevance: {p.relevance}"
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
        prompt = [
            {"role": "system", "content": "You are a judge deciding if cross-examination is warranted. Cross-examine only when there are genuine discrepancies or alternative interpretations worth exploring."},
            {"role": "user", "content": f"Arguments:\n{args_text}\n\nCounter-arguments:\n{counter_text}\n\nShould cross-examination occur?"},
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
            f"Round {r.round}: {len(r.arguments)} arguments, {len(r.counter_arguments)} counter-arguments"
            for r in argumentation_log.rounds
        )
        prompt = [
            {"role": "system", "content": "You are a judge casting a tiebreaker vote in a copyright case. Base your decision on the totality of the evidence and arguments."},
            {"role": "user", "content": f"Jury votes (tied):\n{votes_text}\n\nArgumentation summary:\n{rounds_text}\n\nCast your tiebreaker verdict."},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.verdict
        except Exception:
            return "Undecided"  # safe fallback
