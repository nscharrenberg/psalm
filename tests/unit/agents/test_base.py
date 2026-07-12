from unittest.mock import AsyncMock, patch

import pytest

from psalm.agents.base import BaseAgent
from psalm.events.types import AgentCallFailed, AgentCallRetrying
from psalm.exceptions import PSALMAgentError
from tests.conftest import bound_event_sink, drain_events


class _TestAgent(BaseAgent):
    @property
    def role(self) -> str:
        return "test-agent"


@pytest.fixture
def test_agent(agent_config):
    return _TestAgent(config=agent_config)


async def test_call_llm_emits_retrying_then_succeeds(test_agent):
    with bound_event_sink() as sink:
        with patch.object(type(test_agent._llm), "ainvoke", new=AsyncMock(side_effect=[Exception("boom"), Exception("boom"), "ok"])):
            with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock(return_value=None)):
                result = await test_agent._call_llm([{"role": "user", "content": "hi"}])
        events = await drain_events(sink)

    assert result == "ok"
    retrying = [e for e in events if isinstance(e, AgentCallRetrying)]
    assert len(retrying) == 2
    assert retrying[0].attempt == 1
    assert retrying[1].attempt == 2
    assert all(e.max_attempts == 3 and e.role == "test-agent" for e in retrying)


async def test_call_llm_emits_failed_after_retries_exhausted(test_agent):
    with bound_event_sink() as sink:
        with patch.object(type(test_agent._llm), "ainvoke", new=AsyncMock(side_effect=Exception("persistent failure"))):
            with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock(return_value=None)):
                with pytest.raises(PSALMAgentError):
                    await test_agent._call_llm([{"role": "user", "content": "hi"}])
        events = await drain_events(sink)

    failed = [e for e in events if isinstance(e, AgentCallFailed)]
    assert len(failed) == 1
    assert failed[0].attempts == 3
    assert failed[0].code == "PSALM-A003"
    assert failed[0].role == "test-agent"
    retrying = [e for e in events if isinstance(e, AgentCallRetrying)]
    assert len(retrying) == 2


async def test_call_structured_emits_retrying_then_succeeds(test_agent):
    structured_llm = AsyncMock()
    structured_llm.ainvoke = AsyncMock(side_effect=[Exception("boom"), "ok"])

    with bound_event_sink() as sink:
        with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock(return_value=None)):
            result = await test_agent._call_structured(structured_llm, [{"role": "user", "content": "hi"}])
        events = await drain_events(sink)

    assert result == "ok"
    retrying = [e for e in events if isinstance(e, AgentCallRetrying)]
    assert len(retrying) == 1
    assert retrying[0].attempt == 1
