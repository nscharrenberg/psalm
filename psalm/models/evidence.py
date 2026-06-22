from __future__ import annotations
from pydantic import BaseModel, field_validator


class Proof(BaseModel):
    source_excerpt: str
    target_excerpt: str
    relevance: str


class Argument(BaseModel):
    claim: str
    proofs: list[Proof]

    @field_validator("proofs")
    @classmethod
    def validate_proofs(cls, v: list[Proof]) -> list[Proof]:
        if not v:
            raise ValueError("Argument must contain at least one proof.")
        return v
