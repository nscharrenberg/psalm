from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.prosecutor import Prosecutor
from psalm.dimensions import CHARACTER, SCENES_A_FAIRE


@pytest.fixture
def prosecutor(agent_config):
    return Prosecutor(config=agent_config)


async def test_gather_arguments_returns_batch(prosecutor, sample_argument, agent_config):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(
            arguments=[sample_argument], no_further_arguments=False, closing_statement=None
        )
    )

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=[CHARACTER],
            round=1,
        )

    assert len(result.arguments) == 1
    assert result.arguments[0].agent_role == "prosecutor"
    assert result.arguments[0].dimension == "character"
    assert result.no_further_arguments is False


def test_prosecutor_prompt_prioritizes_expression_over_idea_arguments():
    # Prosecutor should prioritize expression-level arguments but is allowed to make weaker
    # idea/genre/archetype arguments so the debate can proceed — defense will rebut them.
    from psalm.agents.prosecutor import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "prioritize" in prompt or "strongest" in prompt
    assert "archetype" in prompt or "theme" in prompt or "genre" in prompt
    assert "debate must proceed" in prompt  # weaker args still allowed to proceed


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
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

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
    assert "Eye color is a generic trait" in user_content or "defense" in user_content.lower()


async def test_gather_arguments_retries_on_failure(prosecutor, sample_argument):
    call_count = 0

    async def failing_then_success(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("temporary failure")
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = AsyncMock()
    mock_chain.ainvoke = failing_then_success

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_arguments("src", "tgt", [CHARACTER], 1)

    assert call_count == 3
    assert len(result.arguments) == 1


async def test_prosecutor_gather_counter_arguments(prosecutor, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_counter_arguments(
            source_text="src",
            target_text="tgt",
            dimensions=[CHARACTER],
            defense_arguments=[sample_counter_argument],
            round=1,
        )
    assert len(result.arguments) == 1
    assert result.arguments[0].agent_role == "prosecutor"


async def test_prosecutor_counter_prompt_mentions_defense_args(prosecutor, sample_argument, sample_counter_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_counter_argument], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Eye color is a generic trait" in user_content or "defense" in user_content.lower()


async def test_prosecutor_prompt_includes_sub_dimension_context(agent_config, sample_argument):
    from psalm.agents.prosecutor import Prosecutor
    prosecutor = Prosecutor(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_arguments("src", "tgt", [CHARACTER], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Identity & Properties" in user_content
    assert "CRITICAL" in user_content or "HIGH" in user_content


def test_prosecutor_system_prompt_no_self_censorship():
    from psalm.agents.prosecutor import _SYSTEM_PROMPT
    assert "be aware the defense will challenge" not in _SYSTEM_PROMPT
    assert "surface" in _SYSTEM_PROMPT.lower() or "all" in _SYSTEM_PROMPT.lower()


def test_prosecutor_system_prompt_forbids_padding_and_guesswork():
    from psalm.agents.prosecutor import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "including generic or weak ones" not in prompt
    assert "unambiguous" in prompt
    assert "guess" in prompt or "speculative" in prompt
    assert "no_further_arguments" in prompt


async def test_prosecutor_prompt_separates_infringement_and_exception_dimensions(agent_config, sample_argument):
    prosecutor = Prosecutor(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_arguments("src", "tgt", [CHARACTER, SCENES_A_FAIRE], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "PRIMARY DIMENSION (must argue): character" in user_content
    assert "AVAILABLE EXCEPTION TOOLS" in user_content
    assert "scenes-a-faire" in user_content


async def test_prosecutor_retry_hint_appears_in_prompt(agent_config, sample_argument):
    prosecutor = Prosecutor(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_arguments(
            "src", "tgt", [CHARACTER], 1, retry_hint="You must either argue or declare done."
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "You must either argue or declare done." in user_content


async def test_gather_arguments_returns_no_further_arguments(prosecutor):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(
            arguments=[],
            no_further_arguments=True,
            closing_statement="No further unambiguous similarities remain.",
        )
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_arguments("src", "tgt", [CHARACTER], 1)

    assert result.arguments == []
    assert result.no_further_arguments is True
    assert result.closing_statement == "No further unambiguous similarities remain."


async def test_deliver_closing_argument_returns_string(prosecutor, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(statement="The evidence clearly shows the target text infringes.")
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.deliver_closing_argument(
            source_text="src",
            target_text="tgt",
            dimensions=[CHARACTER],
            prosecution_arguments=[sample_argument],
            prosecution_counters=[],
            defense_counters=[sample_counter_argument],
            defense_arguments=[],
        )
    assert result == "The evidence clearly shows the target text infringes."


async def test_deliver_closing_argument_prompt_includes_case_history(prosecutor, sample_argument, sample_counter_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(statement="Closing.")

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.deliver_closing_argument(
            source_text="src",
            target_text="tgt",
            dimensions=[CHARACTER],
            prosecution_arguments=[sample_argument],
            prosecution_counters=[],
            defense_counters=[sample_counter_argument],
            defense_arguments=[],
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Both characters share unique physical traits." in user_content
    assert "Eye color is a generic trait not protected by copyright." in user_content
