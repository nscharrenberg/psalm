from __future__ import annotations

from pydantic import BaseModel


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
