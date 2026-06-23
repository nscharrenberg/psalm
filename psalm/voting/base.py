from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from psalm.models.result import JurorVote


class VoteResult(BaseModel):
    verdict: str | None = None
    is_tie: bool = False


class VotingStrategy(ABC):
    @abstractmethod
    async def apply(
        self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None
    ) -> VoteResult: ...
