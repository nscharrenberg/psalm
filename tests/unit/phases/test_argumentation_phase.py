from unittest.mock import AsyncMock, MagicMock

import pytest

from psalm.dimensions import CHARACTER
from psalm.exceptions import PSALMAgentError
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import Argument, ArgumentBatch, Proof
from psalm.models.result import ArgumentationLog
from psalm.phases.argumentation import ArgumentationPhase


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
    return p


@pytest.fixture
def mock_defense():
    d = MagicMock()
    d.gather_counter_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="defense")]))
    d.gather_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="defense")]))
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
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
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
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(side_effect=defense_argues_every_round)

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
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(side_effect=defense_counters_every_round)
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())

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
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
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
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
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
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)
    mock_judge.validate_batch_completeness = AsyncMock(return_value=False)  # never satisfied

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with pytest.raises(PSALMAgentError) as exc_info:
        await phase.run(case_input)
    assert exc_info.value.code == "PSALM-A004"
