# tests/unit/test_builder.py
from unittest.mock import AsyncMock, patch

import pytest

from psalm.builder import PSALM
from psalm.exceptions import PSALMConfigError, PSALMValidationError


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
        .with_dimensions(["character"])
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
