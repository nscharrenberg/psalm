from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.prosecutor import Prosecutor


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
            dimensions=["character"],
            round=1,
        )

    assert len(result) == 1
    assert result[0].agent_role == "prosecutor"
    assert result[0].dimension == "character"


async def test_gather_arguments_role():
    from psalm.models.config import AgentConfig
    config = AgentConfig(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    prosecutor = Prosecutor(config=config)
    assert prosecutor.role == "prosecutor"


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
        result = await prosecutor.gather_arguments("src", "tgt", ["character"], 1)

    assert call_count == 3
    assert len(result) == 1
