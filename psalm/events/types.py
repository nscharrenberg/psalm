from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, TypeAdapter

from psalm.events.base import PSALMEvent
from psalm.models.evidence import Argument
from psalm.models.result import DimensionScore, PSALMResult

# --- lifecycle ---


class RunStarted(PSALMEvent):
    category: Literal["lifecycle"] = "lifecycle"
    type: Literal["run_started"] = "run_started"
    dimensions: list[str]
    evaluation_strategy: str
    source_length: int
    target_length: int


class RunFailed(PSALMEvent):
    category: Literal["lifecycle"] = "lifecycle"
    type: Literal["run_failed"] = "run_failed"
    code: str
    message: str
    context: dict = Field(default_factory=dict)


class DimensionStarted(PSALMEvent):
    category: Literal["lifecycle"] = "lifecycle"
    type: Literal["dimension_started"] = "dimension_started"
    dimension_type: str
    importance: str


# --- argumentation ---


class ArgumentationRoundStarted(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argumentation_round_started"] = "argumentation_round_started"
    round: int


class ArgumentSubmitted(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argument_submitted"] = "argument_submitted"
    round: int
    role: Literal["prosecution", "defense"]
    kind: Literal["argument", "counter"]
    argument: Argument


class ArgumentValidated(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argument_validated"] = "argument_validated"
    round: int
    role: str
    argument: Argument


class ArgumentRejected(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argument_rejected"] = "argument_rejected"
    round: int
    role: str
    argument: Argument
    reason: str


class ClosingStatementDelivered(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["closing_statement_delivered"] = "closing_statement_delivered"
    round: int
    role: str
    statement: str


class ArgumentationStabilityChecked(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argumentation_stability_checked"] = "argumentation_stability_checked"
    round: int
    stability_detected: bool


class ClosingArgumentDelivered(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["closing_argument_delivered"] = "closing_argument_delivered"
    role: str
    statement: str


class ArgumentBatchCompletenessRetry(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argument_batch_completeness_retry"] = "argument_batch_completeness_retry"
    round: int
    role: str
    attempt: int
    max_attempts: int


# --- deliberation ---


class DeliberationRoundStarted(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["deliberation_round_started"] = "deliberation_round_started"
    round: int


class JurorVoteCast(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["juror_vote_cast"] = "juror_vote_cast"
    round: int
    juror_id: str
    vote: str
    rationale: str
    dimension_scores: list[DimensionScore] = Field(default_factory=list)


class JuryConsensusChecked(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["jury_consensus_checked"] = "jury_consensus_checked"
    round: int
    is_unanimous: bool
    top_verdict: str | None = None


class JuryDiscussionMessage(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["jury_discussion_message"] = "jury_discussion_message"
    round: int
    juror_id: str
    message: str


class VotingStrategyApplied(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["voting_strategy_applied"] = "voting_strategy_applied"
    strategy_name: str
    is_tie: bool
    verdict: str | None = None


# --- verdict ---


class DimensionVerdictReached(PSALMEvent):
    category: Literal["verdict"] = "verdict"
    type: Literal["dimension_verdict_reached"] = "dimension_verdict_reached"
    dimension_type: str
    importance: str
    verdict: str
    weighted_score: float


class FinalVerdictReached(PSALMEvent):
    category: Literal["verdict"] = "verdict"
    type: Literal["final_verdict_reached"] = "final_verdict_reached"
    result: PSALMResult


# --- agent ---


class AgentCallRetrying(PSALMEvent):
    category: Literal["agent"] = "agent"
    type: Literal["agent_call_retrying"] = "agent_call_retrying"
    role: str
    attempt: int
    max_attempts: int
    backoff_seconds: float
    error: str


class AgentCallFailed(PSALMEvent):
    category: Literal["agent"] = "agent"
    type: Literal["agent_call_failed"] = "agent_call_failed"
    role: str
    attempts: int
    code: str
    error: str


Event = Annotated[
    Union[
        RunStarted, RunFailed, DimensionStarted,
        ArgumentationRoundStarted, ArgumentSubmitted, ArgumentValidated, ArgumentRejected,
        ClosingStatementDelivered, ArgumentationStabilityChecked, ClosingArgumentDelivered,
        ArgumentBatchCompletenessRetry,
        DeliberationRoundStarted, JurorVoteCast, JuryConsensusChecked, JuryDiscussionMessage,
        VotingStrategyApplied,
        DimensionVerdictReached, FinalVerdictReached,
        AgentCallRetrying, AgentCallFailed,
    ],
    Field(discriminator="type"),
]

EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)
