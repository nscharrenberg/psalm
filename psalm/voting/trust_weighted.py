from __future__ import annotations
from collections import defaultdict
from typing import Any
from psalm.models.result import JurorVote
from psalm.voting.base import VoteResult, VotingStrategy


def _weight(rationale: str) -> float:
    return float(len(rationale.split()))


class TrustWeightedVoting(VotingStrategy):
    async def apply(self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None) -> VoteResult:
        weights: dict[str, float] = defaultdict(float)
        for v in votes:
            weights[v.vote] += _weight(v.rationale)

        if not weights:
            return VoteResult(is_tie=True)

        sorted_verdicts = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top_verdict, top_weight = sorted_verdicts[0]

        is_tie = len(sorted_verdicts) > 1 and sorted_verdicts[1][1] == top_weight
        if is_tie:
            return VoteResult(is_tie=True)
        return VoteResult(verdict=top_verdict, is_tie=False)
