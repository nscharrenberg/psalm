from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.prosecutor import Prosecutor
from psalm.dimensions import CHARACTER


@pytest.fixture
def prosecutor(agent_config):
    return Prosecutor(config=agent_config)


async def test_gather_arguments_returns_list(prosecutor, sample_argument, agent_config):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(arguments=[sample_argument]))

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=[CHARACTER],
            round=1,
        )

    assert len(result) == 1
    assert result[0].agent_role == "prosecutor"
    assert result[0].dimension == "character"


def test_prosecutor_prompt_prioritizes_expression_over_idea_arguments():
    # Prosecutor should prioritize expression-level arguments but is allowed to make weaker
    # idea/genre/archetype arguments so the debate can proceed — defense will rebut them.
    from psalm.agents.prosecutor import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "prioritize" in prompt or "strongest" in prompt
    assert "archetype" in prompt or "theme" in prompt or "genre" in prompt
    assert "unprotectable" in prompt  # should still know the defense will challenge weak args


async def test_gather_arguments_role():
    from psalm.models.config import AgentConfig
    config = AgentConfig(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    prosecutor = Prosecutor(config=config)
    assert prosecutor.role == "prosecutor"


async def test_prosecutor_includes_prior_defense_arguments_in_prompt(prosecutor, sample_argument, sample_counter_argument):
    # In rounds 2+, the prosecutor must receive prior defense counter-arguments so it can rebut
    # them — not just re-argue the same points ignoring what the defense said.
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument])

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        await prosecutor.gather_arguments(
            source_text="src",
            target_text="tgt",
            dimensions=[CHARACTER],
            round=2,
            prior_defense_arguments=[sample_counter_argument],
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    # Prior defense counter-argument content must appear in the prompt
    assert "Eye color is a generic trait" in user_content or "defense" in user_content.lower()


async def test_gather_arguments_retries_on_failure(prosecutor, sample_argument):
    call_count = 0

    async def failing_then_success(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("temporary failure")
        return MagicMock(arguments=[sample_argument])

    mock_chain = AsyncMock()
    mock_chain.ainvoke = failing_then_success

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_arguments("src", "tgt", [CHARACTER], 1)

    assert call_count == 3
    assert len(result) == 1


async def test_prosecutor_gather_counter_arguments(prosecutor, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(arguments=[sample_argument]))
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_counter_arguments(
            source_text="src",
            target_text="tgt",
            dimensions=[CHARACTER],
            defense_arguments=[sample_counter_argument],
            round=1,
        )
    assert len(result) == 1
    assert result[0].agent_role == "prosecutor"


async def test_prosecutor_counter_prompt_mentions_defense_args(prosecutor, sample_argument, sample_counter_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument])

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_counter_argument], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Eye color is a generic trait" in user_content or "defense" in user_content.lower()
