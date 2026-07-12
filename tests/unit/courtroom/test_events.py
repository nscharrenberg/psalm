from unittest.mock import AsyncMock

import pytest

from psalm.courtroom.default import DefaultCourtroom
from psalm.dimensions import CHARACTER
from psalm.events.types import DimensionStarted, DimensionVerdictReached, FinalVerdictReached
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.result import ArgumentationLog, DebateLog, RoundArguments
from tests.conftest import bound_event_sink, drain_events


@pytest.fixture
def mock_argumentation_phase():
    phase = AsyncMock()
    phase.run = AsyncMock(return_value=ArgumentationLog(rounds=[
        RoundArguments(
            round=1, prosecution_arguments=[], defense_counters=[],
            defense_arguments=[], prosecution_counters=[],
        ),
    ]))
    return phase


@pytest.fixture
def mock_deliberation_phase():
    phase = AsyncMock()
    phase.run = AsyncMock(return_value=(
        "Guilty", DebateLog(rounds=[], final_voting_strategy_applied="unanimous"), 0.8,
    ))
    return phase


async def test_run_single_dimension_emits_dimension_lifecycle_events(
    mock_argumentation_phase, mock_deliberation_phase
):
    config = DebateConfig(dimensions=[CHARACTER])
    courtroom = DefaultCourtroom(mock_argumentation_phase, [mock_deliberation_phase], config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with bound_event_sink() as sink:
        await courtroom.run(case_input)
        events = await drain_events(sink)

    started = [e for e in events if isinstance(e, DimensionStarted)]
    reached = [e for e in events if isinstance(e, DimensionVerdictReached)]
    final = [e for e in events if isinstance(e, FinalVerdictReached)]
    assert len(started) == 1
    assert started[0].dimension == CHARACTER.name
    assert started[0].dimension_type == "infringement"
    assert len(reached) == 1
    assert reached[0].dimension == CHARACTER.name
    assert reached[0].verdict == "Guilty"
    assert len(final) == 1


async def test_final_verdict_reached_carries_full_result(mock_argumentation_phase, mock_deliberation_phase):
    config = DebateConfig(dimensions=[CHARACTER])
    courtroom = DefaultCourtroom(mock_argumentation_phase, [mock_deliberation_phase], config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with bound_event_sink() as sink:
        result = await courtroom.run(case_input)
        events = await drain_events(sink)

    final = [e for e in events if isinstance(e, FinalVerdictReached)]
    assert len(final) == 1
    assert final[0].result == result
