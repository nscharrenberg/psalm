from __future__ import annotations

import difflib
import re
from typing import Literal

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument, ArgumentBatch
from psalm.models.result import ArgumentationLog, JurorVote, ValidationResult

_AUTHENTICITY_THRESHOLD = 0.75


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def is_proof_authentic(excerpt: str, full_text: str) -> bool:
    """Deterministic, no-LLM check: does `excerpt` genuinely appear in `full_text`?

    Structural fix for a Judge that, when handed the full text alongside an excerpt, would
    "notice" unrelated discrepancies elsewhere in the document and reject arguments based on
    content they never cited. A plain string/fuzzy check has no such wandering attention: it
    only ever compares the one excerpt against the one text it's asked about.
    """
    normalized_excerpt = _normalize(excerpt)
    normalized_text = _normalize(full_text)
    if not normalized_excerpt:
        return False
    if normalized_excerpt in normalized_text:
        return True
    matcher = difflib.SequenceMatcher(None, normalized_excerpt, normalized_text, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return (matched / len(normalized_excerpt)) >= _AUTHENTICITY_THRESHOLD


class _StabilityDecision(BaseModel):
    stability_detected: bool
    reasoning: str


class _TiebreakDecision(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str


_PROSECUTION_VALIDATION_PROMPT = """\
You are a judge validating a prosecution argument in a copyright case governed by EU copyright law.
The cited proofs have already been verified as authentic (they genuinely appear in the source and
target text) — you do not need to and cannot re-check that; you are not shown the full text.

Reject the argument (is_valid=false) ONLY if the cited proofs contradict the claim they are
offered to support — e.g. a claim of similarity is not backed by proofs that actually correspond,
or an unrelated or opposite relationship is presented as if it supports the claim.

Do NOT reject for weak, interpretive, idea-level, or thematic reasoning, and do NOT reject merely
because a proof does not by itself sufficiently "prove" or "establish" the claim — argument
strength and sufficiency are for the opposing side to challenge, not grounds for you to reject.
"""

_DEFENSE_VALIDATION_PROMPT = """\
You are a judge validating a defense argument in a copyright case governed by EU copyright law.
The cited proofs have already been verified as authentic (they genuinely appear in the source and
target text) — you do not need to and cannot re-check that; you are not shown the full text.

Reject the argument (is_valid=false) ONLY if the cited proofs contradict the claim they are
offered to support. In particular: if the claim asserts the texts are distinct or independently
created, an identical (or near-identical) passage in both texts is evidence of similarity, not
distinctness — such a proof undermines rather than supports the claim and must be rejected.

Defense arguments may challenge prosecution claims as legally insufficient (unprotectable ideas,
genre conventions), show differences in specific expression, argue independent creation, or make
affirmative claims about the texts' distinctiveness. They are not required to demonstrate
similarity — that is the prosecution's burden. Do NOT reject for weak or interpretive reasoning —
that is the prosecution's job to challenge, not yours to discard.
"""


class Judge(BaseAgent):
    @property
    def role(self) -> str:
        return "judge"

    async def validate_argument(
        self,
        argument: Argument,
        source_text: str,
        target_text: str,
        role: str = "prosecution",
    ) -> ValidationResult:
        for proof in argument.proofs:
            if not is_proof_authentic(proof.source_excerpt, source_text):
                return ValidationResult(
                    is_valid=False,
                    rejection_reason=(
                        "The cited source excerpt does not genuinely appear in the source "
                        f'text: "{proof.source_excerpt}"'
                    ),
                )
            if not is_proof_authentic(proof.target_excerpt, target_text):
                return ValidationResult(
                    is_valid=False,
                    rejection_reason=(
                        "The cited target excerpt does not genuinely appear in the target "
                        f'text: "{proof.target_excerpt}"'
                    ),
                )

        structured_llm = self._llm.with_structured_output(ValidationResult)
        validation_prompt = (
            _DEFENSE_VALIDATION_PROMPT if role == "defense" else _PROSECUTION_VALIDATION_PROMPT
        )
        proofs_text = "\n".join(
            f"  Source: '{p.source_excerpt}'\n  Target: '{p.target_excerpt}'\n"
            f"  Relevance: {p.relevance}"
            for p in argument.proofs
        )
        prompt = [
            {"role": "system", "content": validation_prompt},
            {
                "role": "user",
                "content": (
                    f"Argument claim: {argument.claim}\n"
                    f"Dimension: {argument.dimension}\n"
                    f"Proofs (already verified authentic):\n{proofs_text}"
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

    async def validate_batch_completeness(self, batch: ArgumentBatch) -> bool:
        if batch.no_further_arguments:
            return True  # pydantic validator already enforced closing_statement is present
        return bool(batch.arguments)

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
            f"Round {r.round}: {len(r.prosecution_arguments)} prosecution arguments, "
            f"{len(r.defense_counters)} defense counters, "
            f"{len(r.defense_arguments)} defense arguments, "
            f"{len(r.prosecution_counters)} prosecution counters"
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
