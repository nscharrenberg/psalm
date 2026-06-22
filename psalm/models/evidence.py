from __future__ import annotations
from pydantic import BaseModel, field_validator

_VALID_AGENT_ROLES = {"prosecutor", "defense"}


class Proof(BaseModel):
    source_excerpt: str
    target_excerpt: str
    relevance: str


class Argument(BaseModel):
    claim: str
    dimension: str
    proofs: list[Proof]
    agent_role: str
    round: int

    @field_validator("proofs")
    @classmethod
    def validate_proofs(cls, v: list[Proof]) -> list[Proof]:
        if not v:
            raise ValueError("An argument must have at least one proof")
        return v

    @field_validator("agent_role")
    @classmethod
    def validate_agent_role(cls, v: str) -> str:
        if v not in _VALID_AGENT_ROLES:
            raise ValueError(f"agent_role must be one of {_VALID_AGENT_ROLES}, got '{v}'")
        return v
