from unittest.mock import AsyncMock, MagicMock

import pytest

from psalm.dimensions import CHARACTER
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import Argument, Proof
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


@pytest.fixture
def mock_prosecutor():
    p = MagicMock()
    p.gather_arguments = AsyncMock(return_value=[_make_arg(role="prosecutor")])
    p.gather_counter_arguments = AsyncMock(return_value=[_make_arg(role="prosecutor")])
    return p


@pytest.fixture
def mock_defense():
    d = MagicMock()
    d.gather_counter_arguments = AsyncMock(return_value=[_make_arg(role="defense")])
    d.gather_arguments = AsyncMock(return_value=[_make_arg(role="defense")])
    return d


@pytest.fixture
def mock_judge():
    j = MagicMock()
    j.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    j.detect_stability = AsyncMock(return_value=False)
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
    mock_prosecutor.gather_arguments = AsyncMock(return_value=[])
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=[])
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=[])
    mock_defense.gather_arguments = AsyncMock(return_value=[])
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=5, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    result = await phase.run(case_input)
    # Should stop after round 1 (both sides empty) — not run all 5 rounds
    assert mock_prosecutor.gather_arguments.call_count == 1


async def test_continues_when_only_one_side_empty(mock_judge):
    call_count = 0

    async def prosecution_with_falloff(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [_make_arg(role="prosecutor")]
        return []

    async def defense_argues_every_round(*args, **kwargs):
        return [_make_arg(role="defense", round=kwargs["round"])]

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_with_falloff)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=[])
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=[])
    mock_defense.gather_arguments = AsyncMock(side_effect=defense_argues_every_round)

    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=3, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    result = await phase.run(case_input)
    # Defense kept arguing every round even though prosecution went empty after round 1 —
    # both_empty requires ALL four steps empty, so defense_arguments being non-empty keeps
    # the debate going through round 3 (max_rounds), not stopping early at round 2.
    assert mock_prosecutor.gather_arguments.call_count == 3


async def test_continues_when_step_two_nonempty_but_steps_one_and_three_empty(mock_judge):
    # Discriminates the OLD 2-field both_empty check (prosecution_arguments +
    # defense_arguments only) from the NEW 4-field check (adds defense_counters and
    # prosecution_counters). From round 2 onward, step 1 (prosecution_arguments) and
    # step 3 (defense_arguments) are BOTH empty for that round, but step 2
    # (defense_counters) is non-empty every round. Under the old 2-field check this
    # would incorrectly compute both_empty=True at round 2 and stop early. Under the
    # new 4-field check, the non-empty defense_counters keeps both_empty False, so the
    # debate continues through all 3 rounds.
    async def prosecution_first_round_only(*args, **kwargs):
        if kwargs["round"] == 1:
            return [_make_arg(role="prosecutor", round=1)]
        return []

    async def defense_counters_every_round(*args, **kwargs):
        return [_make_arg(role="defense", round=kwargs["round"])]

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_first_round_only)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=[])
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(side_effect=defense_counters_every_round)
    mock_defense.gather_arguments = AsyncMock(return_value=[])

    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=3, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    result = await phase.run(case_input)
    # If both_empty only checked steps 1 and 3, the phase would have stopped after
    # round 2 (2 calls). The 4-field check keeps it going through round 3.
    assert mock_prosecutor.gather_arguments.call_count == 3
    assert mock_defense.gather_counter_arguments.call_count == 3
