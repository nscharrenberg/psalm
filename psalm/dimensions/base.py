from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Importance(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


_IMPORTANCE_MULTIPLIERS: dict[Importance, float] = {
    Importance.LOW:      0.5,
    Importance.MEDIUM:   1.0,
    Importance.HIGH:     1.5,
    Importance.CRITICAL: 2.0,
}


class SimilarityScore(str, Enum):
    NONE     = "none"
    GENERIC  = "generic"
    POSSIBLE = "possible"
    CLEAR    = "clear"


_SCORE_VALUES: dict[SimilarityScore, int] = {
    SimilarityScore.NONE:     0,
    SimilarityScore.GENERIC:  1,
    SimilarityScore.POSSIBLE: 2,
    SimilarityScore.CLEAR:    3,
}


class SubDimension(BaseModel):
    name: str
    description: str
    importance: Importance = Importance.MEDIUM


class Dimension(BaseModel):
    name: str
    description: str
    sub_dimensions: list[SubDimension]
    importance: Importance = Importance.MEDIUM
