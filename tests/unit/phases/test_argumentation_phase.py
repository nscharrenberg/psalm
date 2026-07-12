from unittest.mock import AsyncMock, MagicMock

import pytest

from psalm.dimensions import CHARACTER
from psalm.exceptions import PSALMAgentError
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import Argument, ArgumentBatch, Proof
from psalm.models.result import ArgumentationLog
from psalm.phases.argumentation import ArgumentationPhase
from tests.conftest import bound_event_sink, drain_events


def _make_arg(dimension: str = "character", round: int = 1, role: str = "prosecutor") -> Argument:
    return Argument(
        claim="Test claim.",
        dimension=dimension,
        proofs=[Proof(source_excerpt="src", target_excerpt="tgt", relevance="rel")],
        agent_role=role,
        round=round,
    )


def _make_batch(arguments: list[Argument] | None = None) -> ArgumentBatch:
    if arguments:
        return ArgumentBatch(arguments=arguments)
    return ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further to add.")


@pytest.fixture
def mock_prosecutor():
    p = MagicMock()
    p.gather_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="prosecutor")]))
    p.gather_counter_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="prosecutor")]))
    p.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    return p


@pytest.fixture
def mock_defense():
    d = MagicMock()
    d.gather_counter_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="defense")]))
    d.gather_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="defense")]))
    d.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    return d


@pytest.fixture
def mock_judge():
    j = MagicMock()
    j.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    j.detect_stability = AsyncMock(return_value=False)
    j.validate_batch_completeness = AsyncMock(return_value=True)
    return j


@pytest.fixture
def argumentation_phase(mock_prosecutor, mock_defense, mock_judge):
    config = DebateConfig(
        dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1
    )
    return ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)


@pytest.fixture
def case_input():
    return CaseInput(source_text="source text", target_text="target text", dimensions=[CHARACTER])


async def test_run_returns_argumentation_log(argumentation_phase, case_input):
    result = await argumentation_phase.run(case_input)
    assert isinstance(result, ArgumentationLog)


async def test_round_has_four_argument_sets(argumentation_phase, case_input):
    result = await argumentation_phase.run(case_input)
    assert len(result.rounds) >= 1
    r = result.rounds[0]
    assert hasattr(r, "prosecution_arguments")
    assert hasattr(r, "defense_counters")
    assert hasattr(r, "defense_arguments")
    assert hasattr(r, "prosecution_counters")


async def test_all_four_agent_methods_called(argumentation_phase, case_input, mock_prosecutor, mock_defense):
    await argumentation_phase.run(case_input)
    mock_prosecutor.gather_arguments.assert_called()
    mock_defense.gather_counter_arguments.assert_called()
    mock_defense.gather_arguments.assert_called()
    mock_prosecutor.gather_counter_arguments.assert_called()


async def test_stop_when_both_sides_empty(mock_judge):
    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=5, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    await phase.run(case_input)
    assert mock_prosecutor.gather_arguments.call_count == 1


async def test_continues_when_only_one_side_empty(mock_judge):
    call_count = 0

    async def prosecution_with_falloff(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_batch([_make_arg(role="prosecutor")])
        return _make_batch()

    async def defense_argues_every_round(*args, **kwargs):
        return _make_batch([_make_arg(role="defense", round=kwargs["round"])])

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_with_falloff)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(side_effect=defense_argues_every_round)
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")

    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=3, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    await phase.run(case_input)
    # both_empty requires ALL four steps empty; defense_arguments stays non-empty every
    # round, so the debate continues through round 3 (max_rounds).
    assert mock_prosecutor.gather_arguments.call_count == 3


async def test_continues_when_step_two_nonempty_but_steps_one_and_three_empty(mock_judge):
    async def prosecution_first_round_only(*args, **kwargs):
        if kwargs["round"] == 1:
            return _make_batch([_make_arg(role="prosecutor", round=1)])
        return _make_batch()

    async def defense_counters_every_round(*args, **kwargs):
        return _make_batch([_make_arg(role="defense", round=kwargs["round"])])

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_first_round_only)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(side_effect=defense_counters_every_round)
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")

    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=3, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    await phase.run(case_input)
    assert mock_prosecutor.gather_arguments.call_count == 3
    assert mock_defense.gather_counter_arguments.call_count == 3


async def test_closing_statement_recorded_in_round(mock_judge):
    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="The prosecution rests.")
    )
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    result = await phase.run(case_input)
    assert len(result.rounds) == 1
    assert result.rounds[0].prosecution_closing_statement == "The prosecution rests."


async def test_completeness_retry_triggers_on_ambiguous_batch(mock_judge):
    call_count = 0

    async def ambiguous_then_valid(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ArgumentBatch()  # empty, no_further_arguments=False — ambiguous
        return _make_batch([_make_arg(role="prosecutor")])

    completeness_calls = 0

    async def completeness_side_effect(batch):
        nonlocal completeness_calls
        completeness_calls += 1
        return completeness_calls > 1

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=ambiguous_then_valid)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)
    mock_judge.validate_batch_completeness = AsyncMock(side_effect=completeness_side_effect)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    await phase.run(case_input)
    assert call_count == 2  # retried once before succeeding


async def test_completeness_retry_exhausted_raises(mock_judge):
    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(return_value=ArgumentBatch())  # always ambiguous
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)
    mock_judge.validate_batch_completeness = AsyncMock(return_value=False)  # never satisfied

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with pytest.raises(PSALMAgentError) as exc_info:
        await phase.run(case_input)
    assert exc_info.value.code == "PSALM-A004"


async def test_rejected_arguments_recorded_with_reason():
    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="prosecutor")]))
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    mock_judge = MagicMock()
    mock_judge.validate_argument = AsyncMock(
        return_value=MagicMock(is_valid=False, rejection_reason="Passage does not appear in either text.")
    )
    mock_judge.detect_stability = AsyncMock(return_value=False)
    mock_judge.validate_batch_completeness = AsyncMock(return_value=True)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    result = await phase.run(case_input)
    assert len(result.rounds) == 1
    r = result.rounds[0]
    # The rejected argument must not appear as a validated argument...
    assert r.prosecution_arguments == []
    # ...but must be recorded in the audit trail with the Judge's stated reason.
    assert len(r.prosecution_rejected_arguments) == 1
    assert r.prosecution_rejected_arguments[0].rejection_reason == "Passage does not appear in either text."
    assert r.prosecution_rejected_arguments[0].argument.agent_role == "prosecutor"


async def test_closing_arguments_delivered_once_regardless_of_round_count(mock_prosecutor, mock_defense, mock_judge):
    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=3, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    result = await phase.run(case_input)

    mock_prosecutor.deliver_closing_argument.assert_called_once()
    mock_defense.deliver_closing_argument.assert_called_once()
    assert result.prosecution_closing_argument == "Prosecution closing argument."
    assert result.defense_closing_argument == "Defense closing argument."


async def test_closing_arguments_delivered_even_when_round_loop_stops_immediately(mock_judge):
    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=5, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    result = await phase.run(case_input)

    # Both sides declared nothing further immediately (round loop stops after round 1), but a
    # dedicated closing argument must still be delivered — even an empty debate gets closing
    # statements, like a real trial.
    mock_prosecutor.deliver_closing_argument.assert_called_once()
    mock_defense.deliver_closing_argument.assert_called_once()
    assert result.prosecution_closing_argument == "Prosecution closing argument."
    assert result.defense_closing_argument == "Defense closing argument."


async def test_prosecution_argue_emits_round_started_and_argument_submitted(argumentation_phase, case_input):
    from psalm.events.types import ArgumentationRoundStarted, ArgumentSubmitted

    with bound_event_sink() as sink:
        await argumentation_phase.run(case_input)
        events = await drain_events(sink)

    round_started = [e for e in events if isinstance(e, ArgumentationRoundStarted)]
    submitted = [e for e in events if isinstance(e, ArgumentSubmitted)]
    assert len(round_started) >= 1
    assert round_started[0].round == 1
    assert any(e.role == "prosecution" and e.kind == "argument" for e in submitted)
    assert any(e.role == "defense" and e.kind == "counter" for e in submitted)
    assert any(e.role == "defense" and e.kind == "argument" for e in submitted)
    assert any(e.role == "prosecution" and e.kind == "counter" for e in submitted)


async def test_judge_validate_emits_argument_validated(argumentation_phase, case_input):
    from psalm.events.types import ArgumentValidated

    with bound_event_sink() as sink:
        await argumentation_phase.run(case_input)
        events = await drain_events(sink)

    validated = [e for e in events if isinstance(e, ArgumentValidated)]
    assert any(e.role == "prosecution" for e in validated)
    assert any(e.role == "defense" for e in validated)


async def test_judge_validate_emits_argument_rejected(mock_prosecutor, mock_defense, mock_judge, case_input):
    from psalm.events.types import ArgumentRejected

    mock_judge.validate_argument = AsyncMock(
        return_value=MagicMock(is_valid=False, rejection_reason="No excerpts.")
    )
    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)

    with bound_event_sink() as sink:
        await phase.run(case_input)
        events = await drain_events(sink)

    rejected = [e for e in events if isinstance(e, ArgumentRejected)]
    assert len(rejected) >= 1
    assert rejected[0].reason == "No excerpts."
    assert rejected[0].role in {"prosecution", "defense"}


async def test_check_next_round_emits_stability_checked(mock_prosecutor, mock_defense, mock_judge, case_input):
    from psalm.events.types import ArgumentationStabilityChecked

    mock_judge.detect_stability = AsyncMock(return_value=True)
    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=5, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)

    with bound_event_sink() as sink:
        await phase.run(case_input)
        events = await drain_events(sink)

    checked = [e for e in events if isinstance(e, ArgumentationStabilityChecked)]
    assert len(checked) == 1
    assert checked[0].round == 1
    assert checked[0].stability_detected is True


async def test_closing_arguments_emit_closing_argument_delivered(argumentation_phase, case_input):
    from psalm.events.types import ClosingArgumentDelivered

    with bound_event_sink() as sink:
        await argumentation_phase.run(case_input)
        events = await drain_events(sink)

    delivered = [e for e in events if isinstance(e, ClosingArgumentDelivered)]
    assert any(e.role == "prosecution" and e.statement == "Prosecution closing argument." for e in delivered)
    assert any(e.role == "defense" and e.statement == "Defense closing argument." for e in delivered)


async def test_completeness_retry_emits_argument_batch_completeness_retry(mock_judge):
    from psalm.events.types import ArgumentBatchCompletenessRetry

    call_count = 0

    async def ambiguous_then_valid(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ArgumentBatch()
        return _make_batch([_make_arg(role="prosecutor")])

    completeness_calls = 0

    async def completeness_side_effect(batch):
        nonlocal completeness_calls
        completeness_calls += 1
        return completeness_calls > 1

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=ambiguous_then_valid)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)
    mock_judge.validate_batch_completeness = AsyncMock(side_effect=completeness_side_effect)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with bound_event_sink() as sink:
        await phase.run(case_input)
        events = await drain_events(sink)

    retries = [e for e in events if isinstance(e, ArgumentBatchCompletenessRetry)]
    assert len(retries) == 1
    assert retries[0].role == "prosecution"
    assert retries[0].attempt == 1
    assert retries[0].max_attempts == 3
