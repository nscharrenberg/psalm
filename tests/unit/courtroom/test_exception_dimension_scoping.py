from unittest.mock import AsyncMock, MagicMock

import pytest

from psalm.courtroom.default import DefaultCourtroom
from psalm.dimensions import CHARACTER, SCENES_A_FAIRE
from psalm.models.config import CaseInput, DebateConfig, EvaluationStrategy
from psalm.models.result import DebateLog, ArgumentationLog


@pytest.fixture
def mock_argumentation_phase():
    phase = MagicMock()
    phase.run = AsyncMock(return_value=ArgumentationLog(rounds=[]))
    return phase


@pytest.fixture
def mock_deliberation_phases():
    phases = []
    for _ in range(2):
        p = MagicMock()
        p.run = AsyncMock(
            return_value=("Not Guilty", DebateLog(rounds=[], final_voting_strategy_applied="unanimous"), 0.2)
        )
        phases.append(p)
    return phases


async def test_infringement_dimension_gets_exception_dims_injected(mock_argumentation_phase, mock_deliberation_phases):
    config = DebateConfig(
        dimensions=[CHARACTER, SCENES_A_FAIRE],
        evaluation_strategy=EvaluationStrategy.FULLY_SEPARATE,
    )
    courtroom = DefaultCourtroom(mock_argumentation_phase, mock_deliberation_phases, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER, SCENES_A_FAIRE])

    await courtroom.run(case_input)

    scoped_inputs = [call.args[0] for call in mock_argumentation_phase.run.call_args_list]
    character_call = next(ci for ci in scoped_inputs if ci.dimensions[0].name == "character")
    assert {d.name for d in character_call.dimensions} == {"character", "scenes-a-faire"}


async def test_exception_dimension_runs_standalone(mock_argumentation_phase, mock_deliberation_phases):
    config = DebateConfig(
        dimensions=[CHARACTER, SCENES_A_FAIRE],
        evaluation_strategy=EvaluationStrategy.FULLY_SEPARATE,
    )
    courtroom = DefaultCourtroom(mock_argumentation_phase, mock_deliberation_phases, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER, SCENES_A_FAIRE])

    await courtroom.run(case_input)

    scoped_inputs = [call.args[0] for call in mock_argumentation_phase.run.call_args_list]
    exception_call = next(ci for ci in scoped_inputs if ci.dimensions[0].name == "scenes-a-faire")
    assert [d.name for d in exception_call.dimensions] == ["scenes-a-faire"]


async def test_dimension_verdicts_carry_dimension_type(mock_argumentation_phase, mock_deliberation_phases):
    config = DebateConfig(
        dimensions=[CHARACTER, SCENES_A_FAIRE],
        evaluation_strategy=EvaluationStrategy.FULLY_SEPARATE,
    )
    courtroom = DefaultCourtroom(mock_argumentation_phase, mock_deliberation_phases, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER, SCENES_A_FAIRE])

    result = await courtroom.run(case_input)

    by_name = {dv.dimension: dv.dimension_type for dv in result.dimension_verdicts}
    assert by_name["character"] == "infringement"
    assert by_name["scenes-a-faire"] == "exception"
