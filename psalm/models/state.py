from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from psalm.models.evidence import Argument
from psalm.models.result import ArgumentationLog


class ArgumentationState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_text: str
    target_text: str
    dimensions: list[str]
    max_rounds: int
    current_round: int = 0
    arguments: list[Argument] = Field(default_factory=list)
    counter_arguments: list[Argument] = Field(default_factory=list)
    cross_examination_triggered: bool = False
    stability_detected: bool = False
    message_queue: list[dict[str, Any]] = Field(default_factory=list)
    argumentation_log: dict[str, Any] | None = None
    pending_prosecution_arguments: list[dict[str, Any]] = Field(default_factory=list)
    validated_prosecution_arguments: list[dict[str, Any]] = Field(default_factory=list)
    pending_defense_arguments: list[dict[str, Any]] = Field(default_factory=list)


class DeliberationState(BaseModel):
    argumentation_log: ArgumentationLog
    max_rounds: int
    current_round: int = 0
    discussion_messages: list[dict[str, str]] = Field(default_factory=list)
    vote_history: list[dict[str, Any]] = Field(default_factory=list)
    consensus_reached: bool = False
    final_verdict: str | None = None
    voting_strategy_applied: str | None = None
