import json

import pytest

from psalm.models.evidence import Argument, Proof
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
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
    return PSALMResult(
        verdict="Guilty",
        rationale="The target text substantially copies character traits.",
        argumentation_log=arg_log,
        debate_log=debate_log,
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
    assert "argumentation_log" in d


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
