from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from pydantic import BaseModel
from psalm.models.result import JurorVote

if TYPE_CHECKING:
    from psalm.agents.judge import Judge


class VoteResult(BaseModel):
    verdict: str | None = None
    is_tie: bool = False


class VotingStrategy(ABC):
    @abstractmethod
    async def apply(self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None) -> VoteResult: ...
