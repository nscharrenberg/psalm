from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from psalm.exceptions import PSALMRuntimeError


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


class ClosingStatement(BaseModel):
    round: int
    statement: str


class ArgumentBatch(BaseModel):
    arguments: list[Argument] = Field(default_factory=list)
    no_further_arguments: bool = False
    closing_statement: str | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> "ArgumentBatch":
        if self.no_further_arguments and self.arguments:
            # Some models conflate "no_further_arguments" (intended: zero arguments) with
            # "this is my final/complete batch" and set the flag alongside real arguments.
            # Real, substantive arguments are the stronger signal of intent — trust them and
            # normalize the flag rather than discarding genuinely useful output over a
            # mislabeled boolean. closing_statement (if any) is left as informational context.
            self.no_further_arguments = False
        if self.no_further_arguments and not self.closing_statement:
            raise PSALMRuntimeError(
                code="PSALM-R004",
                message="closing_statement is required when no_further_arguments=True.",
                context={"no_further_arguments": self.no_further_arguments},
                suggestion=(
                    "Provide a one-sentence closing_statement explaining why there is nothing "
                    "further to argue."
                ),
            )
        return self

