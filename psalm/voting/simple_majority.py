from __future__ import annotations
from collections import Counter
from typing import Any
from psalm.models.result import JurorVote
from psalm.voting.base import VoteResult, VotingStrategy


class SimpleMajorityVoting(VotingStrategy):
    async def apply(self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None) -> VoteResult:
        counts = Counter(v.vote for v in votes)
        if not counts:
            return VoteResult(is_tie=True)
        top_verdict, top_count = counts.most_common(1)[0]
        # Tie: another verdict has the same count
        is_tie = sum(1 for c in counts.values() if c == top_count) > 1
        if is_tie:
            return VoteResult(is_tie=True)
        return VoteResult(verdict=top_verdict, is_tie=False)
