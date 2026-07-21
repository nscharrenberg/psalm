import json

import pytest

from psalm.dimensions.base import Importance
from psalm.models.evidence import Argument, Proof
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
    DimensionVerdict,
    JurorVote,
    PSALMResult,
    ResultMetadata,
    RoundArguments,
    RoundDeliberation,
    ValidationResult,
)


@pytest.fixture
def proof():
    return Proof(
        source_excerpt="The wizard had blue eyes.",
        target_excerpt="The sorcerer had azure eyes.",
        relevance="Both share distinctive eye color.",
    )


@pytest.fixture
def argument(proof):
    return Argument(
        claim="Shared traits.",
        dimension="character",
        proofs=[proof],
        agent_role="prosecutor",
        round=1,
    )


@pytest.fixture
def minimal_result(argument):
    round_args = RoundArguments(
        round=1,
        prosecution_arguments=[argument],
        defense_counters=[],
        defense_arguments=[],
        prosecution_counters=[],
    )
    arg_log = ArgumentationLog(rounds=[round_args])
    vote = JurorVote(juror_id="juror-0", vote="Guilty", rationale="Strong evidence.")
    round_delib = RoundDeliberation(
        round=1,
        discussion_messages=[{"juror_id": "juror-0", "message": "I believe this is infringing."}],
        votes=[vote],
        aggregated_result="Guilty",
    )
    debate_log = DebateLog(rounds=[round_delib], final_voting_strategy_applied="simple_majority")
    metadata = ResultMetadata(
        duration_seconds=12.5,
        argumentation_rounds_used=1,
        deliberation_rounds_used=1,
        voting_strategy_applied="simple_majority",
    )
    dv = DimensionVerdict(
        dimension="character",
        importance=Importance.HIGH,
        verdict="Guilty",
        weighted_score=0.8,
        argumentation_log=arg_log,
        debate_log=debate_log,
    )
    return PSALMResult(
        verdict="Guilty",
        rationale="The target text substantially copies character traits.",
        dimension_verdicts=[dv],
        metadata=metadata,
    )


def test_validation_result_valid():
    r = ValidationResult(is_valid=True)
    assert r.rejection_reason is None


def test_validation_result_invalid():
    r = ValidationResult(is_valid=False, rejection_reason="No relevant excerpts provided.")
    assert r.rejection_reason == "No relevant excerpts provided."


def test_psalm_result_verdict(minimal_result):
    assert minimal_result.verdict == "Guilty"


def test_psalm_result_to_dict(minimal_result):
    d = minimal_result.to_dict()
    assert isinstance(d, dict)
    assert d["verdict"] == "Guilty"
    assert "dimension_verdicts" in d


def test_psalm_result_to_json(minimal_result):
    j = minimal_result.to_json()
    parsed = json.loads(j)
    assert parsed["verdict"] == "Guilty"


def test_result_metadata_defaults():
    m = ResultMetadata(
        duration_seconds=1.0,
        argumentation_rounds_used=1,
        deliberation_rounds_used=1,
        voting_strategy_applied="simple_majority",
    )
    assert m.agent_failures == []


def _make_arg(dimension: str = "character", round: int = 1, role: str = "prosecutor") -> Argument:
    return Argument(
        claim="A test claim.",
        dimension=dimension,
        proofs=[Proof(source_excerpt="src", target_excerpt="tgt", relevance="rel")],
        agent_role=role,
        round=round,
    )


def test_argumentation_log_closing_arguments_default_none():
    from psalm.models.result import ArgumentationLog
    log = ArgumentationLog(rounds=[])
    assert log.prosecution_closing_argument is None
    assert log.defense_closing_argument is None


def test_argumentation_log_accepts_closing_arguments():
    from psalm.models.result import ArgumentationLog
    log = ArgumentationLog(
        rounds=[],
        prosecution_closing_argument="The prosecution's closing argument.",
        defense_closing_argument="The defense's closing argument.",
    )
    assert log.prosecution_closing_argument == "The prosecution's closing argument."
    assert log.defense_closing_argument == "The defense's closing argument."


def test_rejected_argument_model():
    from psalm.models.result import RejectedArgument
    ra = RejectedArgument(argument=_make_arg(), rejection_reason="Passage was fabricated.")
    assert ra.rejection_reason == "Passage was fabricated."
    assert ra.argument.dimension == "character"


def test_round_arguments_rejected_arguments_default_empty():
    from psalm.models.result import RoundArguments
    ra = RoundArguments(
        round=1,
        prosecution_arguments=[],
        defense_counters=[],
        defense_arguments=[],
        prosecution_counters=[],
    )
    assert ra.prosecution_rejected_arguments == []
    assert ra.defense_counter_rejected_arguments == []
    assert ra.defense_rejected_arguments == []
    assert ra.prosecution_counter_rejected_arguments == []


def test_round_arguments_accepts_rejected_arguments():
    from psalm.models.result import RejectedArgument, RoundArguments
    rejected = RejectedArgument(argument=_make_arg(), rejection_reason="Fabricated excerpt.")
    ra = RoundArguments(
        round=1,
        prosecution_arguments=[],
        prosecution_rejected_arguments=[rejected],
        defense_counters=[],
        defense_arguments=[],
        prosecution_counters=[],
    )
    assert len(ra.prosecution_rejected_arguments) == 1
    assert ra.prosecution_rejected_arguments[0].rejection_reason == "Fabricated excerpt."


def test_round_arguments_has_four_fields():
    from psalm.models.result import RoundArguments
    ra = RoundArguments(
        round=1,
        prosecution_arguments=[_make_arg(role="prosecutor")],
        defense_counters=[_make_arg(role="defense")],
        defense_arguments=[_make_arg(role="defense")],
        prosecution_counters=[_make_arg(role="prosecutor")],
    )
    assert len(ra.prosecution_arguments) == 1
    assert len(ra.defense_counters) == 1
    assert len(ra.defense_arguments) == 1
    assert len(ra.prosecution_counters) == 1


def test_round_arguments_old_fields_are_gone():
    from psalm.models.result import RoundArguments
    ra = RoundArguments(
        round=1,
        prosecution_arguments=[],
        defense_counters=[],
        defense_arguments=[],
        prosecution_counters=[],
    )
    assert not hasattr(ra, "arguments")
    assert not hasattr(ra, "counter_arguments")


def test_dimension_score_model():
    from psalm.dimensions.base import SimilarityScore
    from psalm.models.result import DimensionScore
    ds = DimensionScore(
        sub_dimension="Identity & Properties",
        score=SimilarityScore.CLEAR,
        reasoning="Both characters share identical eye color descriptions.",
    )
    assert ds.sub_dimension == "Identity & Properties"
    assert ds.score == SimilarityScore.CLEAR
    assert ds.reasoning


def test_juror_vote_has_dimension_scores():
    from psalm.dimensions.base import SimilarityScore
    from psalm.models.result import DimensionScore, JurorVote
    vote = JurorVote(
        juror_id="juror-0",
        vote="Guilty",
        rationale="Strong evidence.",
        dimension_scores=[
            DimensionScore(
                sub_dimension="Identity & Properties",
                score=SimilarityScore.CLEAR,
                reasoning="Identical traits.",
            )
        ],
    )
    assert len(vote.dimension_scores) == 1
    assert vote.dimension_scores[0].score == SimilarityScore.CLEAR


def test_juror_vote_dimension_scores_defaults_to_empty():
    from psalm.models.result import JurorVote
    vote = JurorVote(juror_id="juror-0", vote="Not Guilty", rationale="No evidence.")
    assert vote.dimension_scores == []


def test_dimension_verdict_model(minimal_argumentation_log, minimal_debate_log):
    from psalm.models.result import DimensionVerdict
    dv = DimensionVerdict(
        dimension="character",
        importance=Importance.HIGH,
        verdict="Guilty",
        weighted_score=0.75,
        argumentation_log=minimal_argumentation_log,
        debate_log=minimal_debate_log,
    )
    assert dv.dimension == "character"
    assert dv.verdict == "Guilty"
    assert dv.weighted_score == 0.75


def test_psalm_result_has_dimension_verdicts(minimal_argumentation_log, minimal_debate_log):
    from psalm.models.result import DimensionVerdict, PSALMResult, ResultMetadata
    dv = DimensionVerdict(
        dimension="character",
        importance=Importance.HIGH,
        verdict="Guilty",
        weighted_score=0.8,
        argumentation_log=minimal_argumentation_log,
        debate_log=minimal_debate_log,
    )
    result = PSALMResult(
        verdict="Guilty",
        rationale="Strong similarities in character.",
        dimension_verdicts=[dv],
        metadata=ResultMetadata(
            duration_seconds=1.0,
            argumentation_rounds_used=1,
            deliberation_rounds_used=1,
            voting_strategy_applied="simple_majority",
        ),
    )
    assert len(result.dimension_verdicts) == 1
    assert not hasattr(result, "argumentation_log")
    assert not hasattr(result, "debate_log")


def test_psalm_result_to_dict_contains_dimension_verdicts(minimal_argumentation_log, minimal_debate_log):
    from psalm.models.result import DimensionVerdict, PSALMResult, ResultMetadata
    dv = DimensionVerdict(
        dimension="character",
        importance=Importance.HIGH,
        verdict="Guilty",
        weighted_score=0.8,
        argumentation_log=minimal_argumentation_log,
        debate_log=minimal_debate_log,
    )
    result = PSALMResult(
        verdict="Guilty",
        rationale="r.",
        dimension_verdicts=[dv],
        metadata=ResultMetadata(
            duration_seconds=1.0,
            argumentation_rounds_used=1,
            deliberation_rounds_used=1,
            voting_strategy_applied="simple_majority",
        ),
    )
    d = result.to_dict()
    assert "dimension_verdicts" in d
    assert "argumentation_log" not in d
    assert "debate_log" not in d


def test_dimension_verdict_defaults_to_infringement_type(minimal_argumentation_log, minimal_debate_log):
    from psalm.models.result import DimensionVerdict
    dv = DimensionVerdict(
        dimension="character",
        importance=Importance.HIGH,
        verdict="Guilty",
        weighted_score=0.75,
        argumentation_log=minimal_argumentation_log,
        debate_log=minimal_debate_log,
    )
    assert dv.dimension_type == "infringement"


def test_dimension_verdict_accepts_exception_type(minimal_argumentation_log, minimal_debate_log):
    from psalm.models.result import DimensionVerdict
    dv = DimensionVerdict(
        dimension="scenes-a-faire",
        dimension_type="exception",
        importance=Importance.MEDIUM,
        verdict="Not Guilty",
        weighted_score=0.2,
        argumentation_log=minimal_argumentation_log,
        debate_log=minimal_debate_log,
    )
    assert dv.dimension_type == "exception"


def test_round_arguments_closing_statements_default_none():
    from psalm.models.result import RoundArguments
    ra = RoundArguments(
        round=1,
        prosecution_arguments=[],
        defense_counters=[],
        defense_arguments=[],
        prosecution_counters=[],
    )
    assert ra.prosecution_closing_statement is None
    assert ra.defense_counter_closing_statement is None
    assert ra.defense_closing_statement is None
    assert ra.prosecution_counter_closing_statement is None


def test_round_arguments_accepts_closing_statements():
    from psalm.models.result import RoundArguments
    ra = RoundArguments(
        round=1,
        prosecution_arguments=[],
        prosecution_closing_statement="The prosecution rests.",
        defense_counters=[],
        defense_counter_closing_statement="No counters to offer.",
        defense_arguments=[],
        defense_closing_statement="The defense rests.",
        prosecution_counters=[],
        prosecution_counter_closing_statement="No rebuttal needed.",
    )
    assert ra.prosecution_closing_statement == "The prosecution rests."
    assert ra.defense_counter_closing_statement == "No counters to offer."
    assert ra.defense_closing_statement == "The defense rests."
    assert ra.prosecution_counter_closing_statement == "No rebuttal needed."


def test_dimension_score_field_order():
    from psalm.models.result import DimensionScore
    assert list(DimensionScore.model_fields) == ["sub_dimension", "reasoning", "score"]


def test_juror_vote_field_order():
    from psalm.models.result import JurorVote
    assert list(JurorVote.model_fields) == [
        "juror_id", "dimension", "dimension_scores", "rationale", "vote",
    ]
