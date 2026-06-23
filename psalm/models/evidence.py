from __future__ import annotations

from pydantic import BaseModel, field_validator

from psalm.exceptions import PSALMConfigError, PSALMRuntimeError

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
            raise PSALMRuntimeError(
                code="PSALM-R003",
                message="Argument must have at least one proof.",
                context={},
                suggestion="Ensure the agent provides source/target excerpts with each claim.",
            )
        return v

    @field_validator("agent_role")
    @classmethod
    def validate_agent_role(cls, v: str) -> str:
        if v not in _VALID_AGENT_ROLES:
            raise PSALMConfigError(
                code="PSALM-C001",
                message=f"Invalid agent_role: '{v}'.",
                context={"agent_role": v, "valid": sorted(_VALID_AGENT_ROLES)},
                suggestion='agent_role must be "prosecutor" or "defense".',
            )
        return v
