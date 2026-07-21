# tests/integration/test_argumentation_phase.py
from unittest.mock import AsyncMock

import pytest

from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.prosecutor import Prosecutor
from psalm.dimensions import CHARACTER
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import ArgumentBatch
from psalm.models.result import ValidationResult
from psalm.phases.argumentation import ArgumentationPhase


@pytest.fixture
def case_input():
    return CaseInput(
        source_text="The wizard had bright blue eyes and wore a silver cloak.",
        target_text="The sorcerer possessed azure irises and donned a grey mantle.",
        dimensions=[CHARACTER],
    )


@pytest.fixture
def mock_prosecutor(agent_config, sample_argument):
    prosecutor = AsyncMock(spec=Prosecutor)
    prosecutor.gather_arguments = AsyncMock(return_value=ArgumentBatch(arguments=[sample_argument]))
    prosecutor.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="No rebuttal needed.")
    )
    prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    return prosecutor


@pytest.fixture
def mock_defense(agent_config, sample_counter_argument):
    defense = AsyncMock(spec=Defense)
    defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(arguments=[sample_counter_argument])
    )
    defense.gather_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="The defense rests.")
    )
    defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    return defense


@pytest.fixture
def mock_judge(agent_config):
    judge = AsyncMock(spec=Judge)
    judge.validate_argument = AsyncMock(
        return_value=ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
    )
    judge.detect_stability = AsyncMock(return_value=False)
    judge.validate_batch_completeness = AsyncMock(return_value=True)
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
    # When judge rejects everything, a round is only recorded if it carries at least one
    # argument OR at least one closing statement.
    mock_judge.validate_argument = AsyncMock(
        return_value=ValidationResult(
            reasoning="No excerpts were provided.", is_valid=False, rejection_reason="No excerpts.",
        )
    )
    mock_defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing to counter.")
    )
    config = DebateConfig(argumentation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    for round_rec in log.rounds:
        assert (
            round_rec.prosecution_arguments != []
            or round_rec.defense_counters != []
            or round_rec.defense_arguments != []
            or round_rec.prosecution_counters != []
            or round_rec.prosecution_closing_statement is not None
            or round_rec.defense_counter_closing_statement is not None
            or round_rec.defense_closing_statement is not None
            or round_rec.prosecution_counter_closing_statement is not None
        )


async def test_stability_terminates_early(mock_prosecutor, mock_defense, mock_judge, case_input):
    mock_judge.detect_stability = AsyncMock(return_value=True)
    config = DebateConfig(argumentation_rounds=5)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    assert len(log.rounds) == 1


async def test_empty_round_stops_loop(mock_prosecutor, mock_defense, mock_judge, case_input):
    mock_prosecutor.gather_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")
    )
    mock_defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing to counter.")
    )
    config = DebateConfig(argumentation_rounds=5)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    await phase.run(case_input)
    assert mock_prosecutor.gather_arguments.call_count == 1


async def test_closing_statement_rounds_are_recorded(mock_prosecutor, mock_defense, mock_judge, case_input, sample_argument):
    # A round where prosecution declares done but later rounds resume must be recorded
    # (not silently dropped) — the closing statement itself is round content.
    call_count = 0

    async def prosecution_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ArgumentBatch(no_further_arguments=True, closing_statement="Nothing yet.")
        return ArgumentBatch(arguments=[sample_argument])

    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_side_effect)
    mock_defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing to counter.")
    )
    config = DebateConfig(argumentation_rounds=3)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    assert len(log.rounds) >= 1
    assert log.rounds[0].prosecution_closing_statement == "Nothing yet."


async def test_defense_is_always_called_regardless_of_prosecution(
    mock_prosecutor, mock_defense, mock_judge, case_input
):
    mock_prosecutor.gather_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")
    )
    mock_defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing to counter.")
    )
    config = DebateConfig(argumentation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    await phase.run(case_input)
    assert mock_defense.gather_counter_arguments.called, "defense was never called"
