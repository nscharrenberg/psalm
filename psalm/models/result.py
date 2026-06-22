from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel
from psalm.models.evidence import Argument


class ValidationResult(BaseModel):
    is_valid: bool
    rejection_reason: str | None = None


class RoundArguments(BaseModel):
    round: int
    arguments: list[Argument]
    counter_arguments: list[Argument]


class ArgumentationLog(BaseModel):
    rounds: list[RoundArguments]


class JurorVote(BaseModel):
    juror_id: str
    vote: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str


class RoundDeliberation(BaseModel):
    round: int
    discussion_messages: list[dict[str, str]]
    votes: list[JurorVote]
    aggregated_result: str | None = None


class DebateLog(BaseModel):
    rounds: list[RoundDeliberation]
    final_voting_strategy_applied: str


class ResultMetadata(BaseModel):
    duration_seconds: float
    argumentation_rounds_used: int
    deliberation_rounds_used: int
    voting_strategy_applied: str
    agent_failures: list[dict[str, Any]] = []


class PSALMResult(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str
    argumentation_log: ArgumentationLog
    debate_log: DebateLog
    metadata: ResultMetadata

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)
