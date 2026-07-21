from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from psalm.dimensions import CHARACTER, PLOT, WORLD_BUILDING
from psalm.dimensions.base import Dimension
from psalm.exceptions import PSALMConfigError


class EvaluationStrategy(str, Enum):
    SHARED_ARG_PER_DIM_DELIBERATION = "shared_arg_per_dim_deliberation"
    FULLY_SEPARATE                  = "fully_separate"
    SHARED_ALL                      = "shared_all"

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


class ExecutionConfig(BaseModel):
    max_concurrent_llm_calls: int = 8
    max_retries: int = 3
    backoff_factor: float = 2.0

    @field_validator("max_concurrent_llm_calls", "max_retries")
    @classmethod
    def validate_positive_int(cls, v: int, info) -> int:
        if v < 1:
            raise PSALMConfigError(
                code="PSALM-C008",
                message=f"{info.field_name} must be >= 1, got {v}.",
                context={"field": info.field_name, "value": v},
                suggestion="Set a value of 1 or greater.",
            )
        return v

    @field_validator("backoff_factor")
    @classmethod
    def validate_backoff_factor(cls, v: float) -> float:
        if v <= 0:
            raise PSALMConfigError(
                code="PSALM-C008",
                message=f"backoff_factor must be > 0, got {v}.",
                context={"field": "backoff_factor", "value": v},
                suggestion="Set a positive value (e.g. 2.0).",
            )
        return v


class DebateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argumentation_rounds: int = 3
    deliberation_rounds: int = 2
    time_limit_seconds: int = 180
    dimensions: list[Dimension] = Field(
        default_factory=lambda: [CHARACTER, PLOT, WORLD_BUILDING]
    )
    voting_strategies: list[str] = Field(
        default_factory=lambda: ["simple_majority", "trust_weighted", "judge_tiebreaker"]
    )
    evaluation_strategy: EvaluationStrategy = EvaluationStrategy.FULLY_SEPARATE
    guilty_threshold: float = 0.5

    @field_validator("voting_strategies")
    @classmethod
    def validate_voting_strategies(cls, v: list[str]) -> list[str]:
        for strategy in v:
            if strategy not in _VALID_VOTING_STRATEGIES:
                raise PSALMConfigError(
                    code="PSALM-C004",
                    message=f"Unknown voting strategy: '{strategy}'.",
                    context={"strategy": strategy, "valid": sorted(_VALID_VOTING_STRATEGIES)},
                    suggestion=(
                        'Use one of: "simple_majority", "trust_weighted", "judge_tiebreaker".'
                    ),
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
    dimensions: list[Dimension] = Field(
        default_factory=lambda: [CHARACTER, PLOT, WORLD_BUILDING]
    )
