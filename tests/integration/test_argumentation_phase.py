# tests/integration/test_argumentation_phase.py
from unittest.mock import AsyncMock

import pytest

from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.prosecutor import Prosecutor
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.result import ValidationResult
from psalm.phases.argumentation import ArgumentationPhase


@pytest.fixture
def case_input():
    return CaseInput(
        source_text="The wizard had bright blue eyes and wore a silver cloak.",
        target_text="The sorcerer possessed azure irises and donned a grey mantle.",
        dimensions=["character"],
    )


@pytest.fixture
def mock_prosecutor(agent_config, sample_argument):
    prosecutor = AsyncMock(spec=Prosecutor)
    prosecutor.gather_arguments = AsyncMock(return_value=[sample_argument])
    return prosecutor


@pytest.fixture
def mock_defense(agent_config, sample_counter_argument):
    defense = AsyncMock(spec=Defense)
    defense.gather_counter_arguments = AsyncMock(return_value=[sample_counter_argument])
    return defense


@pytest.fixture
def mock_judge(agent_config):
    judge = AsyncMock(spec=Judge)
    judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=True))
    judge.should_cross_examine = AsyncMock(return_value=False)
    judge.detect_stability = AsyncMock(return_value=False)
    return judge


@pytest.fixture
def argumentation_phase(mock_prosecutor, mock_defense, mock_judge):
    config = DebateConfig(argumentation_rounds=2)
    return ArgumentationPhase(
        prosecutor=mock_prosecutor,
        defense=mock_defense,
        judge=mock_judge,
        config=config,
    )


async def test_argumentation_phase_runs(argumentation_phase, case_input):
    log = await argumentation_phase.run(case_input)
    assert log is not None
    assert len(log.rounds) > 0


async def test_argumentation_phase_calls_prosecutor(argumentation_phase, case_input, mock_prosecutor):
    await argumentation_phase.run(case_input)
    assert mock_prosecutor.gather_arguments.called


async def test_argumentation_phase_calls_defense(argumentation_phase, case_input, mock_defense):
    await argumentation_phase.run(case_input)
    assert mock_defense.gather_counter_arguments.called


async def test_argumentation_phase_validates_arguments(argumentation_phase, case_input, mock_judge):
    await argumentation_phase.run(case_input)
    assert mock_judge.validate_argument.called


async def test_invalid_arguments_excluded(mock_prosecutor, mock_defense, mock_judge, case_input):
    # When judge rejects everything, rounds are empty and should be excluded from the log.
    mock_judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=False, rejection_reason="No excerpts."))
    mock_defense.gather_counter_arguments = AsyncMock(return_value=[])
    config = DebateConfig(argumentation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    # Completely empty rounds must be excluded from the log
    for round_rec in log.rounds:
        assert round_rec.arguments != [] or round_rec.counter_arguments != []


async def test_stability_terminates_early(mock_prosecutor, mock_defense, mock_judge, case_input):
    mock_judge.detect_stability = AsyncMock(return_value=True)
    config = DebateConfig(argumentation_rounds=5)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    # Should terminate after 1 round due to stability
    assert len(log.rounds) == 1


async def test_empty_round_stops_loop(mock_prosecutor, mock_defense, mock_judge, case_input):
    # When a round produces 0 prosecution AND 0 defense arguments, the loop must stop —
    # continuing would just repeat identical empty LLM calls (pure stochasticity waste).
    mock_prosecutor.gather_arguments = AsyncMock(return_value=[])
    mock_defense.gather_counter_arguments = AsyncMock(return_value=[])
    config = DebateConfig(argumentation_rounds=5)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    _ = await phase.run(case_input)
    # Must stop after first empty round, not run all 5 rounds
    assert mock_prosecutor.gather_arguments.call_count == 1


async def test_empty_rounds_excluded_from_log(mock_prosecutor, mock_defense, mock_judge, case_input, sample_argument, sample_counter_argument):
    # Rounds that produced nothing should not appear in the log.
    # Simulate: round 1 empty, round 2 has content.
    call_count = 0

    async def prosecution_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return [] if call_count == 1 else [sample_argument]

    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_side_effect)
    mock_defense.gather_counter_arguments = AsyncMock(return_value=[])
    config = DebateConfig(argumentation_rounds=3)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    # The empty round 1 must not appear in the log
    for round_rec in log.rounds:
        assert round_rec.arguments != [] or round_rec.counter_arguments != []


async def test_defense_is_always_called_regardless_of_prosecution(
    mock_prosecutor, mock_defense, mock_judge, case_input
):
    # Defense must be called in every round — even when prosecution produces no valid arguments —
    # so it can make affirmative arguments about the texts' independence.
    mock_prosecutor.gather_arguments = AsyncMock(return_value=[])
    mock_defense.gather_counter_arguments = AsyncMock(return_value=[])
    config = DebateConfig(argumentation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    await phase.run(case_input)
    assert mock_defense.gather_counter_arguments.called, "defense was never called"
