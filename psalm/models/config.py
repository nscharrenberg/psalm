from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from psalm.exceptions import PSALMConfigError

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
            raise PSALMConfigError(
                code="PSALM-C007",
                message=f"temperature must be in [0.0, 2.0], got {v}.",
                context={"value": v, "valid_range": [0.0, 2.0]},
                suggestion="Set a value within the valid range.",
            )
        return v


class DebateConfig(BaseModel):
    rounds: int = 5
    time_limit_seconds: int = 180
    dimensions: list[str] = Field(default_factory=lambda: ["character", "world-building", "plot"])
    voting_strategies: list[str] = Field(
        default_factory=lambda: ["simple_majority", "trust_weighted", "judge_tiebreaker"]
    )

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: list[str]) -> list[str]:
        for dim in v:
            if dim not in _VALID_DIMENSIONS:
                raise PSALMConfigError(
                    code="PSALM-C003",
                    message=f"Unknown dimension: '{dim}'.",
                    context={"dimension": dim, "valid": sorted(_VALID_DIMENSIONS)},
                    suggestion='Use one of: "character", "world-building", "plot".',
                )
        return v

    @field_validator("voting_strategies")
    @classmethod
    def validate_voting_strategies(cls, v: list[str]) -> list[str]:
        for strategy in v:
            if strategy not in _VALID_VOTING_STRATEGIES:
                raise PSALMConfigError(
                    code="PSALM-C004",
                    message=f"Unknown voting strategy: '{strategy}'.",
                    context={"strategy": strategy, "valid": sorted(_VALID_VOTING_STRATEGIES)},
                    suggestion='Use one of: "simple_majority", "trust_weighted", "judge_tiebreaker".',
                )
        if v and v[-1] != "judge_tiebreaker":
            raise PSALMConfigError(
                code="PSALM-C005",
                message="judge_tiebreaker must be the final strategy in the voting chain.",
                context={"strategies": v},
                suggestion="Move judge_tiebreaker to the last position.",
            )
        return v


class CaseInput(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str] = Field(default_factory=lambda: ["character", "world-building", "plot"])
