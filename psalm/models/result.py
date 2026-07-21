from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from psalm.dimensions.base import Importance, SimilarityScore
from psalm.models.evidence import Argument


class ValidationResult(BaseModel):
    is_valid: bool
    rejection_reason: str | None = None


class RejectedArgument(BaseModel):
    argument: Argument
    rejection_reason: str


class RoundArguments(BaseModel):
    round: int
    prosecution_arguments: list[Argument]
    prosecution_rejected_arguments: list[RejectedArgument] = Field(default_factory=list)
    prosecution_closing_statement: str | None = None
    defense_counters: list[Argument]
    defense_counter_rejected_arguments: list[RejectedArgument] = Field(default_factory=list)
    defense_counter_closing_statement: str | None = None
    defense_arguments: list[Argument]
    defense_rejected_arguments: list[RejectedArgument] = Field(default_factory=list)
    defense_closing_statement: str | None = None
    prosecution_counters: list[Argument]
    prosecution_counter_rejected_arguments: list[RejectedArgument] = Field(default_factory=list)
    prosecution_counter_closing_statement: str | None = None


class ArgumentationLog(BaseModel):
    rounds: list[RoundArguments]
    prosecution_closing_argument: str | None = None
    defense_closing_argument: str | None = None


class DimensionScore(BaseModel):
    sub_dimension: str
    reasoning: str
    score: SimilarityScore


class JurorVote(BaseModel):
    juror_id: str
    dimension: str | None = None
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    rationale: str
    vote: Literal["Guilty", "Not Guilty", "Undecided"]


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
    agent_failures: list[dict[str, Any]] = Field(default_factory=list)


class DimensionVerdict(BaseModel):
    dimension: str
    dimension_type: Literal["infringement", "exception"] = "infringement"
    importance: Importance
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    weighted_score: float
    argumentation_log: ArgumentationLog
    debate_log: DebateLog


class PSALMResult(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str
    dimension_verdicts: list[DimensionVerdict]
    metadata: ResultMetadata

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)
