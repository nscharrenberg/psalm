from __future__ import annotations

from typing import Any

from psalm.exceptions import PSALMConfigError
from psalm.models.result import ArgumentationLog, JurorVote
from psalm.voting.base import VoteResult, VotingStrategy


class JudgeTiebreakerVoting(VotingStrategy):
    async def apply(
        self,
        votes: list[JurorVote],
        judge: Any,
        argumentation_log: ArgumentationLog | None = None,
        dimension: Any = None,
    ) -> VoteResult:
        if judge is None:
            raise PSALMConfigError(
                code="PSALM-C005",
                message="JudgeTiebreakerVoting requires a Judge instance.",
                context={},
                suggestion="Ensure .with_judge(...) is called on the builder before .build().",
            )
        verdict = await judge.tiebreak(votes, argumentation_log, dimension=dimension)
        return VoteResult(verdict=verdict, is_tie=False)
