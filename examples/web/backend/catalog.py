from __future__ import annotations

import os

from presets import PRESETS
from schemas import (
    CatalogResponse,
    DimensionPayload,
    EvaluationStrategyPayload,
    PresetPayload,
    ProviderPresetPayload,
    SubDimensionPayload,
)

from psalm.dimensions import (
    CHARACTER,
    CITATIONS,
    NARRATIVE_VOICE,
    PARODY_SATIRE,
    PASTICHE,
    PLOT,
    SCENE_SEQUENCE,
    SCENES_A_FAIRE,
    WORLD_BUILDING,
    WRITING_STYLE,
)
from psalm.dimensions.base import Dimension
from psalm.models.config import EvaluationStrategy

_ALL_DIMENSIONS: list[Dimension] = [
    CHARACTER, PLOT, WORLD_BUILDING, SCENE_SEQUENCE, WRITING_STYLE, NARRATIVE_VOICE,
    SCENES_A_FAIRE, CITATIONS, PASTICHE, PARODY_SATIRE,
]

_DIMENSION_BY_NAME: dict[str, Dimension] = {d.name: d for d in _ALL_DIMENSIONS}


def resolve_dimensions(names: list[str]) -> list[Dimension]:
    dimensions = []
    for name in names:
        dimension = _DIMENSION_BY_NAME.get(name)
        if dimension is None:
            valid = ", ".join(sorted(_DIMENSION_BY_NAME))
            raise ValueError(f"Unknown dimension: '{name}'. Valid: {valid}")
        dimensions.append(dimension)
    return dimensions

_EVALUATION_STRATEGY_LABELS: dict[EvaluationStrategy, tuple[str, str]] = {
    EvaluationStrategy.FULLY_SEPARATE: (
        "Fully separate (default)",
        "Each dimension runs its own independent argumentation and deliberation pipeline.",
    ),
    EvaluationStrategy.SHARED_ARG_PER_DIM_DELIBERATION: (
        "Shared argumentation, per-dimension deliberation",
        "One argumentation pass covers all dimensions together; each dimension is deliberated separately.",
    ),
    EvaluationStrategy.SHARED_ALL: (
        "Fully shared",
        "One argumentation pass and one deliberation pass cover all dimensions together.",
    ),
}

_PROVIDER_PRESETS = [
    {"id": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1"},
    {"id": "azure-openai", "label": "Azure OpenAI", "base_url": ""},
    {"id": "together", "label": "Together.ai", "base_url": "https://api.together.xyz/v1"},
    {"id": "groq", "label": "Groq", "base_url": "https://api.groq.com/openai/v1"},
    {"id": "custom", "label": "Local / Custom", "base_url": ""},
]

_ENV_STATUS_KEYS = [
    "PSALM_API_KEY", "PSALM_BASE_URL", "PSALM_MODEL", "PSALM_TEMPERATURE",
    "PSALM_PROSECUTOR_API_KEY", "PSALM_DEFENSE_API_KEY", "PSALM_JUDGE_API_KEY",
    "PSALM_JURY_API_KEY",
]


def _dimension_payload(dim: Dimension) -> DimensionPayload:
    return DimensionPayload(
        name=dim.name,
        dimension_type=dim.dimension_type,
        importance=dim.importance.value,
        description=dim.description,
        sub_dimensions=[
            SubDimensionPayload(name=sd.name, description=sd.description, importance=sd.importance.value)
            for sd in dim.sub_dimensions
        ],
    )


def build_catalog() -> CatalogResponse:
    return CatalogResponse(
        dimensions=[_dimension_payload(d) for d in _ALL_DIMENSIONS],
        presets=[PresetPayload(**p) for p in PRESETS],
        evaluation_strategies=[
            EvaluationStrategyPayload(value=strategy.value, label=label, description=description)
            for strategy, (label, description) in _EVALUATION_STRATEGY_LABELS.items()
        ],
        provider_presets=[ProviderPresetPayload(**p) for p in _PROVIDER_PRESETS],
        env_status={key: bool(os.getenv(key, "")) for key in _ENV_STATUS_KEYS},
    )
