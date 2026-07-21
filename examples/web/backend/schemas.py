from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SubDimensionPayload(BaseModel):
    name: str
    description: str
    importance: str


class DimensionPayload(BaseModel):
    name: str
    dimension_type: str
    importance: str
    description: str
    sub_dimensions: list[SubDimensionPayload]


class PresetPayload(BaseModel):
    id: str
    label: str
    source_text: str
    target_text: str


class EvaluationStrategyPayload(BaseModel):
    value: str
    label: str
    description: str


class ProviderPresetPayload(BaseModel):
    id: str
    label: str
    base_url: str


class CatalogResponse(BaseModel):
    dimensions: list[DimensionPayload]
    presets: list[PresetPayload]
    evaluation_strategies: list[EvaluationStrategyPayload]
    provider_presets: list[ProviderPresetPayload]
    env_status: dict[str, bool]


class AgentConfigRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None


class JurorConfigRequest(AgentConfigRequest):
    seed: int | None = None


class TrialConfigRequest(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str]
    evaluation_strategy: str = "fully_separate"
    argumentation_rounds: int = 3
    deliberation_rounds: int = 2
    time_limit_seconds: int = 120
    max_concurrent_llm_calls: int = Field(default=8, ge=1)
    max_retries: int = Field(default=3, ge=1)
    prosecutor: AgentConfigRequest = AgentConfigRequest()
    defense: AgentConfigRequest = AgentConfigRequest()
    judge: AgentConfigRequest = AgentConfigRequest()
    jury: list[JurorConfigRequest] = [
        JurorConfigRequest(), JurorConfigRequest(), JurorConfigRequest(),
    ]


class TrialSummary(BaseModel):
    id: str
    created_at: str
    status: str
    source_text_preview: str
    target_text_preview: str
    verdict: str | None = None
    error_message: str | None = None


class TrialDetail(TrialSummary):
    config_summary: dict[str, Any]
    result: dict[str, Any] | None = None
