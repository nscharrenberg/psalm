# tests/unit/test_builder.py
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from psalm.agents.base import _RunExecution
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


async def test_ping_llm_retries_transient_failures_then_succeeds():
    from psalm.models.config import AgentConfig

    config = AgentConfig(**_agent_kwargs())
    execution = _RunExecution(max_concurrent_llm_calls=8, max_retries=3, backoff_factor=2.0)
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[ConnectionError("transient"), ConnectionError("transient"), None]
    )
    with (
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        patch("psalm.builder.asyncio.sleep", new=AsyncMock()),
    ):
        await PSALM()._ping_llm(config, "juror-0", execution)
    assert mock_llm.ainvoke.call_count == 3


async def test_ping_llm_raises_psalm_c006_after_exhausting_retries():
    from psalm.models.config import AgentConfig

    config = AgentConfig(**_agent_kwargs())
    execution = _RunExecution(max_concurrent_llm_calls=8, max_retries=3, backoff_factor=2.0)
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=ConnectionError("persistent"))
    with (
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        patch("psalm.builder.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(PSALMConfigError) as exc_info:
            await PSALM()._ping_llm(config, "juror-1", execution)
    assert exc_info.value.code == "PSALM-C006"
    assert exc_info.value.cause is not None
    assert mock_llm.ainvoke.call_count == 3


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
    from unittest.mock import AsyncMock, patch

    from psalm.models.result import ArgumentationLog, DebateLog, RoundArguments

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

    from psalm.models.result import ArgumentationLog, DebateLog, RoundArguments

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


async def test_with_event_listener_registers_callback():
    builder = PSALM().with_event_listener(lambda e: None)
    assert len(builder._event_listeners) == 1


async def test_evaluate_and_aevaluate_unaffected_when_no_listeners_registered():
    courtroom = await _build_psalm()
    assert courtroom._event_listeners == []


async def test_aevaluate_forwards_events_to_registered_listener():
    from psalm.events.types import FinalVerdictReached
    from psalm.models.result import ArgumentationLog, DebateLog, RoundArguments

    received = []
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_dimensions([CHARACTER])
        .with_event_listener(received.append)
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        courtroom = await builder.build()

    arg_log = ArgumentationLog(rounds=[
        RoundArguments(
            round=1, prosecution_arguments=[], defense_counters=[],
            defense_arguments=[], prosecution_counters=[],
        )
    ])
    debate_log = DebateLog(rounds=[], final_voting_strategy_applied="unanimous")

    with patch.object(courtroom._courtroom._argumentation_phase, "run", AsyncMock(return_value=arg_log)):
        with patch.object(courtroom._courtroom._deliberation_phases[0], "run",
                          AsyncMock(return_value=("Not Guilty", debate_log, 0.1))):
            result = await courtroom.aevaluate("source text here", "target text here")

    assert isinstance(result, PSALMResult)
    assert len(received) > 0
    final_events = [e for e in received if isinstance(e, FinalVerdictReached)]
    assert len(final_events) == 1
    assert final_events[0].result == result


async def test_astream_evaluate_yields_final_verdict_reached_with_result():
    from psalm.events.types import FinalVerdictReached
    from psalm.models.result import ArgumentationLog, DebateLog, RoundArguments

    courtroom = await _build_psalm()
    arg_log = ArgumentationLog(rounds=[
        RoundArguments(
            round=1, prosecution_arguments=[], defense_counters=[],
            defense_arguments=[], prosecution_counters=[],
        )
    ])
    debate_log = DebateLog(rounds=[], final_voting_strategy_applied="unanimous")

    collected = []
    with patch.object(courtroom._courtroom._argumentation_phase, "run", AsyncMock(return_value=arg_log)):
        with patch.object(courtroom._courtroom._deliberation_phases[0], "run",
                          AsyncMock(return_value=("Not Guilty", debate_log, 0.1))):
            async for event in courtroom.astream_evaluate("source text here", "target text here"):
                collected.append(event)

    final_events = [e for e in collected if isinstance(e, FinalVerdictReached)]
    assert len(final_events) == 1
    assert final_events[0].result.verdict == "Not Guilty"


async def test_astream_evaluate_identical_texts_emits_full_event_sequence():
    from psalm.events.types import DimensionVerdictReached, FinalVerdictReached, RunStarted

    courtroom = await _build_psalm()
    text = "The wizard had blue eyes."
    collected = []
    async for event in courtroom.astream_evaluate(text, text):
        collected.append(event)

    assert any(isinstance(e, RunStarted) for e in collected)
    assert any(isinstance(e, DimensionVerdictReached) for e in collected)
    final_events = [e for e in collected if isinstance(e, FinalVerdictReached)]
    assert len(final_events) == 1
    assert final_events[0].result.verdict == "Guilty"


async def test_astream_evaluate_raises_on_empty_source():
    courtroom = await _build_psalm()
    with pytest.raises(PSALMValidationError):
        async for _event in courtroom.astream_evaluate("", "target"):
            pass


def test_with_execution_stores_config():
    builder = PSALM().with_execution(max_concurrent_llm_calls=4, max_retries=5, backoff_factor=3.0)
    assert builder._execution_config.max_concurrent_llm_calls == 4
    assert builder._execution_config.max_retries == 5
    assert builder._execution_config.backoff_factor == 3.0


def test_default_execution_config():
    builder = PSALM()
    assert builder._execution_config.max_concurrent_llm_calls == 8
    assert builder._execution_config.max_retries == 3
    assert builder._execution_config.backoff_factor == 2.0
    assert builder._execution_config.max_requests_per_minute == 60
    assert builder._execution_config.max_tokens_per_minute == 40000
    assert builder._execution_config.retry_after_fallback_seconds is None


def test_with_execution_stores_rate_limit_fields():
    builder = PSALM().with_execution(
        max_requests_per_minute=10, max_tokens_per_minute=1000, retry_after_fallback_seconds=5.0,
    )
    assert builder._execution_config.max_requests_per_minute == 10
    assert builder._execution_config.max_tokens_per_minute == 1000
    assert builder._execution_config.retry_after_fallback_seconds == 5.0


async def test_build_applies_configured_rate_limit_settings():
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_execution(
            max_requests_per_minute=15, max_tokens_per_minute=2000, retry_after_fallback_seconds=3.0,
        )
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        courtroom = await builder.build()
    execution = courtroom._courtroom._argumentation_phase._prosecutor._execution
    assert execution.max_requests_per_minute == 15
    assert execution.max_tokens_per_minute == 2000
    assert execution.retry_after_fallback_seconds == 3.0
    assert execution.rate_limiter() is not None


async def test_build_shares_one_semaphore_across_prosecutor_and_jury():
    courtroom = await _build_psalm()
    prosecutor_execution = courtroom._courtroom._argumentation_phase._prosecutor._execution
    juror_execution = courtroom._courtroom._deliberation_phases[0]._jury[0]._execution
    judge_execution = courtroom._courtroom._deliberation_phases[0]._judge._execution
    assert prosecutor_execution.semaphore() is juror_execution.semaphore()
    assert prosecutor_execution.semaphore() is judge_execution.semaphore()


async def test_build_applies_configured_execution_settings():
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_execution(max_concurrent_llm_calls=2, max_retries=1, backoff_factor=1.5)
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        courtroom = await builder.build()
    execution = courtroom._courtroom._argumentation_phase._prosecutor._execution
    assert execution.max_retries == 1
    assert execution.backoff_factor == 1.5
    assert execution.max_concurrent_llm_calls == 2


async def test_ping_llm_uses_execution_max_retries():
    from psalm.models.config import AgentConfig

    config = AgentConfig(**_agent_kwargs())
    execution = _RunExecution(max_concurrent_llm_calls=8, max_retries=2, backoff_factor=1.0)
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=ConnectionError("persistent"))
    with (
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        patch("psalm.builder.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(PSALMConfigError):
            await PSALM()._ping_llm(config, "juror-1", execution)
    assert mock_llm.ainvoke.call_count == 2


def test_evaluate_sync_works_across_separate_event_loops_with_contended_cap():
    # Regression test: the build-time connectivity ping and the sync evaluate() path run in
    # TWO SEPARATE event loops (evaluate() calls asyncio.run() internally). If the semaphore
    # were created once at build() time and reused, it would bind to the build loop the first
    # time it actually blocks (which happens whenever ping/eval contends the configured cap)
    # and then raise "bound to a different event loop" when used from evaluate()'s fresh loop.
    #
    # NOTE on why this test drives *real* contention instead of only patching whole methods
    # with AsyncMock: an AsyncMock coroutine completes without ever yielding control back to
    # the event loop, so gathering N of them never actually interleaves — every "concurrent"
    # call fully acquires-and-releases the semaphore before the next one starts, and the
    # semaphore never truly contends (never gets to `locked()`), so it never binds to a loop
    # and the original bug can't reproduce. Both loops below therefore include an explicit
    # `await asyncio.sleep(0)` while holding the semaphore, so overlapping callers genuinely
    # queue on it, matching the real "jury size / cap contention" scenario from the bug report.
    from psalm.models.result import ArgumentationLog, DebateLog, RoundArguments

    async def _yielding_ainvoke(*_args, **_kwargs):
        await asyncio.sleep(0)
        return None

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=_yielding_ainvoke)

    async def _build():
        builder = (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs(n=6))
            .with_dimensions([CHARACTER])
            .with_execution(max_concurrent_llm_calls=2, max_retries=1, backoff_factor=1.0)
        )
        # Mock only the network boundary (not _ping_llm itself) so the real ping code path
        # runs and genuinely contends the semaphore: 9 pingers (prosecutor, defense, judge,
        # 6 jurors) against a cap of 2.
        with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
            return await builder.build()

    courtroom = asyncio.run(_build())

    arg_log = ArgumentationLog(rounds=[
        RoundArguments(
            round=1, prosecution_arguments=[], defense_counters=[],
            defense_arguments=[], prosecution_counters=[],
        )
    ])
    debate_log = DebateLog(rounds=[], final_voting_strategy_applied="unanimous")
    execution = courtroom._courtroom._deliberation_phases[0]._jury[0]._execution

    async def _contend_semaphore(*_args, **_kwargs):
        # Simulate 6 jurors concurrently trying to call their LLM during deliberation, in
        # evaluate()'s fresh loop, again contending the cap of 2.
        async def _hold():
            async with execution.semaphore():
                await asyncio.sleep(0)

        await asyncio.gather(*[_hold() for _ in range(6)])
        return "Not Guilty", debate_log, 0.1

    with patch.object(courtroom._courtroom._argumentation_phase, "run", AsyncMock(return_value=arg_log)):
        with patch.object(courtroom._courtroom._deliberation_phases[0], "run", _contend_semaphore):
            result = courtroom.evaluate("source text here", "target text here")

    assert result.verdict is not None
