# tests/unit/test_builder.py
from unittest.mock import AsyncMock, patch

import pytest

from psalm.builder import PSALM
from psalm.dimensions import CHARACTER, PLOT
from psalm.exceptions import PSALMConfigError, PSALMValidationError
from psalm.models.config import EvaluationStrategy
from psalm.models.result import DimensionVerdict, PSALMResult


def _agent_kwargs():
    return {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o"}


def _jury_configs(n=3):
    return [
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model": "gpt-4o",
            "seed": i,
        }
        for i in range(n)
    ]


async def _build_psalm():
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_dimensions([CHARACTER])
        .with_debate(argumentation_rounds=2, deliberation_rounds=1, time_limit_seconds=60)
        .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        return await builder.build()


async def test_build_returns_courtroom():
    courtroom = await _build_psalm()
    assert courtroom is not None


async def test_build_raises_without_prosecutor():
    builder = (
        PSALM()
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
    )
    with pytest.raises(PSALMConfigError) as exc_info:
        with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
            await builder.build()
    assert "PSALM-C001" in str(exc_info.value)


async def test_build_raises_with_small_jury():
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs(n=2))
    )
    with pytest.raises(PSALMConfigError) as exc_info:
        with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
            await builder.build()
    assert "PSALM-C002" in str(exc_info.value)


async def test_build_raises_on_llm_ping_failure():
    from psalm.exceptions import PSALMConfigError as _E
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(
        side_effect=_E(code="PSALM-C006", message="LLM ping failed.", context={})
    )):
        with pytest.raises(PSALMConfigError) as exc_info:
            await builder.build()
    assert "PSALM-C006" in str(exc_info.value)


async def test_evaluate_raises_on_empty_source():
    courtroom = await _build_psalm()
    with pytest.raises(PSALMValidationError) as exc_info:
        courtroom.evaluate(source_text="", target_text="some text")
    assert "PSALM-V001" in str(exc_info.value)


async def test_evaluate_raises_on_empty_target():
    courtroom = await _build_psalm()
    with pytest.raises(PSALMValidationError) as exc_info:
        courtroom.evaluate(source_text="some text", target_text="")
    assert "PSALM-V002" in str(exc_info.value)


async def test_with_evaluation_strategy_sets_strategy():
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_evaluation_strategy(EvaluationStrategy.SHARED_ALL)
    )
    assert builder._debate_config.evaluation_strategy == EvaluationStrategy.SHARED_ALL


async def test_default_evaluation_strategy_is_fully_separate():
    builder = PSALM()
    assert builder._debate_config.evaluation_strategy == EvaluationStrategy.FULLY_SEPARATE


async def test_evaluate_returns_psalm_result_with_dimension_verdicts():
    from unittest.mock import AsyncMock, MagicMock, patch
    from psalm.models.result import DebateLog, ArgumentationLog, RoundArguments

    courtroom = await _build_psalm()

    arg_log = ArgumentationLog(rounds=[
        RoundArguments(
            round=1,
            prosecution_arguments=[],
            defense_counters=[],
            defense_arguments=[],
            prosecution_counters=[],
        )
    ])
    debate_log = DebateLog(rounds=[], final_voting_strategy_applied="unanimous")

    with patch.object(courtroom._courtroom._argumentation_phase, "run", AsyncMock(return_value=arg_log)):
        with patch.object(courtroom._courtroom._deliberation_phases[0], "run",
                          AsyncMock(return_value=("Not Guilty", debate_log, 0.1))):
            result = await courtroom.aevaluate("source text here", "target text here")

    assert isinstance(result, PSALMResult)
    assert len(result.dimension_verdicts) >= 1
    assert isinstance(result.dimension_verdicts[0], DimensionVerdict)


async def test_shared_all_argumentation_rounds_not_multiplied_per_dimension():
    """Under SHARED_ALL, every DimensionVerdict shares the same ArgumentationLog
    instance (one argumentation phase run reused across dimensions). The reported
    argumentation_rounds_used must count that shared log once, not once per
    dimension."""
    from unittest.mock import AsyncMock, patch
    from psalm.models.result import DebateLog, ArgumentationLog, RoundArguments

    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_dimensions([CHARACTER, PLOT])
        .with_debate(argumentation_rounds=2, deliberation_rounds=1, time_limit_seconds=60)
        .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
        .with_evaluation_strategy(EvaluationStrategy.SHARED_ALL)
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        courtroom = await builder.build()

    arg_log = ArgumentationLog(rounds=[
        RoundArguments(
            round=1,
            prosecution_arguments=[],
            defense_counters=[],
            defense_arguments=[],
            prosecution_counters=[],
        )
    ])
    debate_log = DebateLog(rounds=[], final_voting_strategy_applied="unanimous")

    # Only one deliberation phase exists for SHARED_ALL; it is reused for both dimensions.
    assert len(courtroom._courtroom._deliberation_phases) == 1

    with patch.object(courtroom._courtroom._argumentation_phase, "run", AsyncMock(return_value=arg_log)):
        with patch.object(courtroom._courtroom._deliberation_phases[0], "run",
                          AsyncMock(return_value=("Not Guilty", debate_log, 0.1))):
            result = await courtroom.aevaluate("source text here", "target text here")

    assert len(result.dimension_verdicts) == 2
    # Both dimension verdicts reference the exact same ArgumentationLog object.
    assert result.dimension_verdicts[0].argumentation_log is result.dimension_verdicts[1].argumentation_log
    # Rounds must be counted once for the shared log, not once per dimension (2x).
    assert result.metadata.argumentation_rounds_used == 1


async def test_identical_texts_result_sets_dimension_type():
    courtroom = await _build_psalm()
    result = courtroom._identical_texts_result("some text")
    assert result.dimension_verdicts[0].dimension_type == "infringement"
