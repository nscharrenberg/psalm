from psalm.dimensions.base import Importance, SimilarityScore
from psalm.events.types import (
    AgentCallFailed,
    AgentCallRetrying,
    ArgumentationRoundStarted,
    ArgumentationStabilityChecked,
    ArgumentBatchCompletenessRetry,
    ArgumentRejected,
    ArgumentSubmitted,
    ArgumentValidated,
    ClosingArgumentDelivered,
    ClosingStatementDelivered,
    DeliberationRoundStarted,
    DimensionStarted,
    DimensionVerdictReached,
    EventAdapter,
    FinalVerdictReached,
    JurorVoteCast,
    JuryConsensusChecked,
    JuryDiscussionMessage,
    RunFailed,
    RunStarted,
    VotingStrategyApplied,
)
from psalm.models.evidence import Argument, Proof
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
    DimensionScore,
    DimensionVerdict,
    PSALMResult,
    ResultMetadata,
)


def _sample_argument() -> Argument:
    return Argument(
        claim="Test claim.",
        dimension="character",
        proofs=[Proof(source_excerpt="src", target_excerpt="tgt", relevance="rel")],
        agent_role="prosecutor",
        round=1,
    )


def _sample_result() -> PSALMResult:
    return PSALMResult(
        verdict="Guilty",
        rationale="Because.",
        dimension_verdicts=[
            DimensionVerdict(
                dimension="character",
                importance=Importance.HIGH,
                verdict="Guilty",
                weighted_score=0.8,
                argumentation_log=ArgumentationLog(rounds=[]),
                debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
            )
        ],
        metadata=ResultMetadata(
            duration_seconds=1.0,
            argumentation_rounds_used=1,
            deliberation_rounds_used=1,
            voting_strategy_applied="unanimous",
        ),
    )


def test_run_started_defaults():
    e = RunStarted(dimensions=["character"], evaluation_strategy="fully_separate",
                    source_length=10, target_length=12)
    assert e.category == "lifecycle"
    assert e.type == "run_started"


def test_run_failed_defaults():
    e = RunFailed(code="PSALM-A003", message="boom", context={})
    assert e.category == "lifecycle"
    assert e.type == "run_failed"


def test_dimension_started_defaults():
    e = DimensionStarted(dimension_type="infringement", importance="high")
    assert e.category == "lifecycle"
    assert e.type == "dimension_started"


def test_argumentation_round_started_defaults():
    e = ArgumentationRoundStarted(round=1)
    assert e.category == "argumentation"
    assert e.type == "argumentation_round_started"


def test_argument_submitted_defaults():
    e = ArgumentSubmitted(round=1, role="prosecution", kind="argument", argument=_sample_argument())
    assert e.category == "argumentation"
    assert e.type == "argument_submitted"
    assert e.argument.claim == "Test claim."


def test_argument_validated_defaults():
    e = ArgumentValidated(round=1, role="prosecution", argument=_sample_argument())
    assert e.type == "argument_validated"


def test_argument_rejected_defaults():
    e = ArgumentRejected(round=1, role="prosecution", argument=_sample_argument(), reason="No proof.")
    assert e.type == "argument_rejected"
    assert e.reason == "No proof."


def test_closing_statement_delivered_defaults():
    e = ClosingStatementDelivered(round=1, role="defense", statement="Resting.")
    assert e.type == "closing_statement_delivered"


def test_argumentation_stability_checked_defaults():
    e = ArgumentationStabilityChecked(round=2, stability_detected=True)
    assert e.type == "argumentation_stability_checked"


def test_closing_argument_delivered_defaults():
    e = ClosingArgumentDelivered(role="prosecution", statement="Final words.")
    assert e.type == "closing_argument_delivered"


def test_argument_batch_completeness_retry_defaults():
    e = ArgumentBatchCompletenessRetry(round=1, role="prosecution", attempt=1, max_attempts=3)
    assert e.category == "argumentation"
    assert e.type == "argument_batch_completeness_retry"


def test_deliberation_round_started_defaults():
    e = DeliberationRoundStarted(round=1)
    assert e.category == "deliberation"
    assert e.type == "deliberation_round_started"


def test_juror_vote_cast_defaults():
    e = JurorVoteCast(
        round=1, juror_id="juror-0", vote="Guilty", rationale="Strong evidence.",
        dimension_scores=[DimensionScore(sub_dimension="x", score=SimilarityScore.CLEAR, reasoning="r")],
    )
    assert e.type == "juror_vote_cast"
    assert e.dimension_scores[0].sub_dimension == "x"


def test_jury_consensus_checked_defaults():
    e = JuryConsensusChecked(round=1, is_unanimous=True, top_verdict="Guilty")
    assert e.type == "jury_consensus_checked"


def test_jury_discussion_message_defaults():
    e = JuryDiscussionMessage(round=2, juror_id="juror-0", message="I think...")
    assert e.type == "jury_discussion_message"


def test_voting_strategy_applied_defaults():
    e = VotingStrategyApplied(strategy_name="SimpleMajorityVoting", is_tie=False, verdict="Guilty")
    assert e.category == "deliberation"
    assert e.type == "voting_strategy_applied"


def test_dimension_verdict_reached_defaults():
    e = DimensionVerdictReached(
        dimension_type="infringement", importance="high", verdict="Guilty", weighted_score=0.8,
    )
    assert e.category == "verdict"
    assert e.type == "dimension_verdict_reached"


def test_final_verdict_reached_defaults():
    e = FinalVerdictReached(result=_sample_result())
    assert e.category == "verdict"
    assert e.type == "final_verdict_reached"
    assert e.result.verdict == "Guilty"


def test_agent_call_retrying_defaults():
    e = AgentCallRetrying(role="prosecutor", attempt=1, max_attempts=3, backoff_seconds=2.0, error="boom")
    assert e.category == "agent"
    assert e.type == "agent_call_retrying"


def test_agent_call_failed_defaults():
    e = AgentCallFailed(role="prosecutor", attempts=3, code="PSALM-A003", error="boom")
    assert e.category == "agent"
    assert e.type == "agent_call_failed"


def test_event_adapter_resolves_correct_subclass_from_dump():
    original = ArgumentRejected(round=1, role="prosecution", argument=_sample_argument(), reason="No proof.")
    restored = EventAdapter.validate_python(original.model_dump())
    assert isinstance(restored, ArgumentRejected)
    assert restored.reason == "No proof."


def test_event_adapter_resolves_final_verdict_reached():
    original = FinalVerdictReached(result=_sample_result())
    restored = EventAdapter.validate_python(original.model_dump())
    assert isinstance(restored, FinalVerdictReached)
    assert restored.result.verdict == "Guilty"
