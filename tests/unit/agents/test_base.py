import asyncio
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
def test_agent(agent_config, run_execution):
    return _TestAgent(config=agent_config, execution=run_execution)


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


async def test_call_llm_respects_semaphore_cap(agent_config):
    from psalm.agents.base import _RunExecution

    execution = _RunExecution(semaphore=asyncio.Semaphore(1), max_retries=3, backoff_factor=2.0)
    agent = _TestAgent(config=agent_config, execution=execution)

    in_flight = 0
    max_in_flight = 0

    async def fake_ainvoke(messages):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return "ok"

    with patch.object(type(agent._llm), "ainvoke", new=AsyncMock(side_effect=fake_ainvoke)):
        await asyncio.gather(
            agent._call_llm([{"role": "user", "content": "a"}]),
            agent._call_llm([{"role": "user", "content": "b"}]),
        )

    assert max_in_flight == 1


async def test_call_llm_honors_configurable_max_retries(agent_config):
    from psalm.agents.base import _RunExecution
    from psalm.exceptions import PSALMAgentError

    execution = _RunExecution(semaphore=asyncio.Semaphore(8), max_retries=1, backoff_factor=2.0)
    agent = _TestAgent(config=agent_config, execution=execution)

    with patch.object(type(agent._llm), "ainvoke", new=AsyncMock(side_effect=Exception("boom"))) as mock_ainvoke:
        with patch("psalm.agents.base.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            with pytest.raises(PSALMAgentError):
                await agent._call_llm([{"role": "user", "content": "hi"}])

    assert mock_ainvoke.call_count == 1
    mock_sleep.assert_not_called()


async def test_call_llm_backoff_is_within_full_jitter_bounds(agent_config):
    from psalm.agents.base import _RunExecution

    execution = _RunExecution(semaphore=asyncio.Semaphore(8), max_retries=3, backoff_factor=2.0)
    agent = _TestAgent(config=agent_config, execution=execution)

    recorded_sleeps = []

    async def fake_sleep(seconds):
        recorded_sleeps.append(seconds)

    with patch.object(
        type(agent._llm), "ainvoke",
        new=AsyncMock(side_effect=[Exception("boom"), Exception("boom"), "ok"]),
    ):
        with patch("psalm.agents.base.asyncio.sleep", new=fake_sleep):
            await agent._call_llm([{"role": "user", "content": "hi"}])

    assert len(recorded_sleeps) == 2
    assert 0 <= recorded_sleeps[0] <= 1.0  # backoff_factor**0 == 1
    assert 0 <= recorded_sleeps[1] <= 2.0  # backoff_factor**1 == 2
