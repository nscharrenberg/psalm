from __future__ import annotations
from pydantic import BaseModel, Field, field_validator

_VALID_DIMENSIONS = {"character", "world-building", "plot"}
_VALID_VOTING_STRATEGIES = {"simple_majority", "trust_weighted", "judge_tiebreaker"}


class AgentConfig(BaseModel):
    base_url: str
    api_key: str
    org_id: str | None = None
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None
    timeout_seconds: int = 180

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"temperature must be in [0.0, 2.0], got {v}")
        return v


class DebateConfig(BaseModel):
    rounds: int = 5
    time_limit_seconds: int = 180
    dimensions: list[str] = Field(default_factory=lambda: ["character", "world-building", "plot"])
    voting_strategies: list[str] = Field(default_factory=lambda: ["simple_majority", "trust_weighted", "judge_tiebreaker"])

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: list[str]) -> list[str]:
        for dim in v:
            if dim not in _VALID_DIMENSIONS:
                raise ValueError(f"Unknown dimension: '{dim}'. Valid: {_VALID_DIMENSIONS}")
        return v

    @field_validator("voting_strategies")
    @classmethod
    def validate_voting_strategies(cls, v: list[str]) -> list[str]:
        for strategy in v:
            if strategy not in _VALID_VOTING_STRATEGIES:
                raise ValueError(f"Unknown strategy: '{strategy}'. Valid: {_VALID_VOTING_STRATEGIES}")
        if v and v[-1] != "judge_tiebreaker":
            raise ValueError("judge_tiebreaker must be last in the voting strategy chain")
        return v
