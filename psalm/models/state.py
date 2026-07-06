from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from psalm.dimensions.base import Dimension
from psalm.models.evidence import Argument
from psalm.models.result import ArgumentationLog


class ArgumentationState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_text: str
    target_text: str
    dimensions: list[Dimension]
    max_rounds: int
    current_round: int = 0
    stability_detected: bool = False
    message_queue: list[dict[str, Any]] = Field(default_factory=list)
    argumentation_log: dict[str, Any] | None = None

    # Step 1 — prosecution affirmative arguments
    pending_prosecution_arguments: list[dict[str, Any]] = Field(default_factory=list)
    validated_prosecution_arguments: list[dict[str, Any]] = Field(default_factory=list)
    prosecution_arguments: list[Argument] = Field(default_factory=list)

    # Step 2 — defense counters to prosecution
    pending_defense_counters: list[dict[str, Any]] = Field(default_factory=list)
    validated_defense_counters: list[dict[str, Any]] = Field(default_factory=list)
    defense_counters: list[Argument] = Field(default_factory=list)

    # Step 3 — defense affirmative arguments
    pending_defense_arguments: list[dict[str, Any]] = Field(default_factory=list)
    validated_defense_arguments: list[dict[str, Any]] = Field(default_factory=list)
    defense_arguments: list[Argument] = Field(default_factory=list)

    # Step 4 — prosecution counters to defense
    pending_prosecution_counters: list[dict[str, Any]] = Field(default_factory=list)
    validated_prosecution_counters: list[dict[str, Any]] = Field(default_factory=list)
    prosecution_counters: list[Argument] = Field(default_factory=list)


class DeliberationState(BaseModel):
    argumentation_log: ArgumentationLog
    max_rounds: int
    current_dimension: Dimension
    current_round: int = 0
    discussion_messages: list[dict[str, str]] = Field(default_factory=list)
    vote_history: list[dict[str, Any]] = Field(default_factory=list)
    consensus_reached: bool = False
    final_verdict: str | None = None
    voting_strategy_applied: str | None = None
    current_round_votes: list[dict[str, Any]] = Field(default_factory=list)
    debate_log: dict[str, Any] | None = None
    weighted_score: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)
