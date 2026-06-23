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
    config = DebateConfig(rounds=2)
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


async def test_invalid_arguments_excluded(mock_prosecutor, mock_defense, mock_judge, case_input, sample_argument):
    mock_judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=False, rejection_reason="No excerpts."))
    config = DebateConfig(rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    # All arguments rejected by judge — rounds exist but args lists empty
    for round_rec in log.rounds:
        assert round_rec.arguments == []


async def test_stability_terminates_early(mock_prosecutor, mock_defense, mock_judge, case_input, sample_argument):
    mock_judge.detect_stability = AsyncMock(return_value=True)
    config = DebateConfig(rounds=5)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    # Should terminate after 1 round due to stability
    assert len(log.rounds) == 1
