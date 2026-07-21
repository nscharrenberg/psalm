# Execution Concurrency & Rate-Limit Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** add a configurable, global concurrency cap and jittered/configurable retry backoff for every LLM call PSALM makes (including the build-time connectivity ping), and expose the two most actionable settings in the demo web app's trial config form.

**Architecture:** a new `ExecutionConfig` Pydantic model holds user-facing settings (`max_concurrent_llm_calls`, `max_retries`, `backoff_factor`). At `PSALM.build()` time, it's turned into a runtime `_RunExecution` object (holding a real `asyncio.Semaphore` — not serializable, so it can't live on the Pydantic model) that is threaded, as the *same instance*, into every agent (prosecutor, defense, judge, every juror) and the build-time ping path. `BaseAgent._call_llm`/`_call_structured` acquire that shared semaphore only around the live LLM call, and use full-jitter backoff on retry. No existing `asyncio.gather` call site changes — the cap is enforced one layer deeper.

**Tech Stack:** Python 3.14, Pydantic v2, `asyncio`, LangChain (`ChatOpenAI`); TypeScript/React/Mantine + FastAPI for the demo web app.

## Global Constraints

- The concurrency cap is a single global limit shared across every LLM call in a run (all roles, all dimensions, the build-time ping) — not scoped per-provider/per-API-key.
- `ExecutionConfig` defaults: `max_concurrent_llm_calls=8`, `max_retries=3`, `backoff_factor=2.0`. The last two exactly match today's hardcoded `_RETRY_ATTEMPTS`/`_BACKOFF_FACTOR`, so a caller who never touches this config sees unchanged retry *counts* (only jitter is new).
- `_RunExecution` (the dataclass holding the real `asyncio.Semaphore`) is defined in `psalm/agents/base.py`, not `psalm/builder.py` — `builder.py` already imports from `psalm.agents.*`, so defining it in `builder.py` would force a circular import back into `agents/base.py`.
- No existing `asyncio.gather` call site changes in `psalm/courtroom/default.py` or `psalm/phases/deliberation.py`. The cap lives inside `BaseAgent._call_llm`/`_call_structured`, acquired only around the live `ainvoke()` call and released before any backoff sleep.
- Backoff jitter is full jitter: `random.uniform(0, backoff_factor**attempt)`. Not configurable — an implementation detail, not a tuning knob.
- `backoff_factor` is SDK-only. It is not added to the web app's `TrialConfigRequest` schema or its trial config form — only `max_concurrent_llm_calls` and `max_retries` are surfaced there.
- `BaseAgent.__init__` and `Juror.__init__` gain a new required `execution: _RunExecution` parameter. This is treated as an internal, same-package signature change (not preserved for external compatibility) because `psalm/builder.py::_assemble` is the only production construction site for any agent class anywhere in the repository.
- New `ExecutionConfig` validation failures use error code `PSALM-C008` (the next unused `PSALM-C0xx` code; `C001`–`C002`, `C004`–`C007` are already in use, `C003` is unused but skipped to avoid ambiguity with any pre-existing convention).
- `DebateConfig` is not touched — execution settings are a separate top-level builder config (`PSALM().with_execution(...)`), matching the design decision to keep them out of `DebateConfig`.

---

## Task 1: `ExecutionConfig` model

**Files:**
- Modify: `psalm/models/config.py`
- Test: `tests/unit/models/test_config.py`

**Interfaces:**
- Produces: `psalm.models.config.ExecutionConfig` — a `BaseModel` with fields `max_concurrent_llm_calls: int = 8`, `max_retries: int = 3`, `backoff_factor: float = 2.0`. Raises `PSALMConfigError` (code `PSALM-C008`) via `field_validator`s if `max_concurrent_llm_calls < 1`, `max_retries < 1`, or `backoff_factor <= 0`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/models/test_config.py`:
```python
def test_execution_config_defaults():
    from psalm.models.config import ExecutionConfig
    config = ExecutionConfig()
    assert config.max_concurrent_llm_calls == 8
    assert config.max_retries == 3
    assert config.backoff_factor == 2.0


def test_execution_config_accepts_custom_values():
    from psalm.models.config import ExecutionConfig
    config = ExecutionConfig(max_concurrent_llm_calls=4, max_retries=5, backoff_factor=1.5)
    assert config.max_concurrent_llm_calls == 4
    assert config.max_retries == 5
    assert config.backoff_factor == 1.5


def test_execution_config_rejects_non_positive_max_concurrent_llm_calls():
    from psalm.models.config import ExecutionConfig
    with pytest.raises(PSALMConfigError) as exc_info:
        ExecutionConfig(max_concurrent_llm_calls=0)
    assert exc_info.value.code == "PSALM-C008"


def test_execution_config_rejects_non_positive_max_retries():
    from psalm.models.config import ExecutionConfig
    with pytest.raises(PSALMConfigError) as exc_info:
        ExecutionConfig(max_retries=0)
    assert exc_info.value.code == "PSALM-C008"


def test_execution_config_rejects_non_positive_backoff_factor():
    from psalm.models.config import ExecutionConfig
    with pytest.raises(PSALMConfigError) as exc_info:
        ExecutionConfig(backoff_factor=0.0)
    assert exc_info.value.code == "PSALM-C008"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/models/test_config.py -k execution_config -v`
Expected: FAIL with `ImportError: cannot import name 'ExecutionConfig'`

- [ ] **Step 3: Add `ExecutionConfig` to `psalm/models/config.py`**

Add this class after `AgentConfig` (before `class DebateConfig`) in `psalm/models/config.py`:
```python
class ExecutionConfig(BaseModel):
    max_concurrent_llm_calls: int = 8
    max_retries: int = 3
    backoff_factor: float = 2.0

    @field_validator("max_concurrent_llm_calls", "max_retries")
    @classmethod
    def validate_positive_int(cls, v: int, info) -> int:
        if v < 1:
            raise PSALMConfigError(
                code="PSALM-C008",
                message=f"{info.field_name} must be >= 1, got {v}.",
                context={"field": info.field_name, "value": v},
                suggestion="Set a value of 1 or greater.",
            )
        return v

    @field_validator("backoff_factor")
    @classmethod
    def validate_backoff_factor(cls, v: float) -> float:
        if v <= 0:
            raise PSALMConfigError(
                code="PSALM-C008",
                message=f"backoff_factor must be > 0, got {v}.",
                context={"field": "backoff_factor", "value": v},
                suggestion="Set a positive value (e.g. 2.0).",
            )
        return v
```
No new imports needed — `BaseModel`, `field_validator`, and `PSALMConfigError` are already imported at the top of this file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/models/test_config.py -v`
Expected: PASS (all tests in the file, including the 5 new ones and all pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add psalm/models/config.py tests/unit/models/test_config.py
git commit -m "feat: add ExecutionConfig model for concurrency/retry settings"
```

---

## Task 2: `_RunExecution`, `BaseAgent` semaphore + jitter + configurable retries, `Juror.__init__`

**Files:**
- Modify: `psalm/agents/base.py`
- Modify: `psalm/agents/juror.py:177-179`
- Modify: `tests/conftest.py`
- Modify: `tests/unit/agents/test_base.py`
- Modify: `tests/unit/agents/test_juror.py:11-13,288,293,321,326,377,383`
- Modify: `tests/unit/agents/test_prosecutor.py:9-11,47-51,134-136,168-169,187-191,208-209`
- Modify: `tests/unit/agents/test_defense.py:10-12,150-151,167-168,186-190,207-208`
- Modify: `tests/unit/agents/test_judge.py:10-12`

**Interfaces:**
- Consumes: `psalm.models.config.ExecutionConfig` (Task 1) — used only in the new `run_execution` test fixture, not by production code in this task.
- Produces: `psalm.agents.base._RunExecution` — a `@dataclass` with fields `semaphore: asyncio.Semaphore`, `max_retries: int`, `backoff_factor: float`. `BaseAgent.__init__(self, config: AgentConfig, execution: _RunExecution)`. `Juror.__init__(self, config: AgentConfig, juror_id: str, execution: _RunExecution)`. A new pytest fixture `run_execution` in `tests/conftest.py` returning a `_RunExecution` with `Semaphore(8)`, `max_retries=3`, `backoff_factor=2.0` — every later task's tests that construct any agent use this fixture.

This task changes a widely-used constructor signature. Every test in the repository that directly constructs a `Prosecutor`, `Defense`, `Judge`, or `Juror` breaks the moment `BaseAgent.__init__` requires `execution` — so this task must land the production change and fix every one of those call sites together; the suite cannot pass in between.

- [ ] **Step 1: Write the failing tests for the new mechanism**

Add `import asyncio` to the top of `tests/unit/agents/test_base.py` (alongside the existing `from unittest.mock import AsyncMock, patch` import), then append these three tests to the file:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_base.py -v`
Expected: FAIL — `TypeError: _TestAgent.__init__() got an unexpected keyword argument 'execution'` (the `_TestAgent(config=agent_config)` fixture at the top of the file doesn't accept `execution` yet)

- [ ] **Step 3: Add `_RunExecution` and update `BaseAgent`**

Replace the full contents of `psalm/agents/base.py` with:
```python
from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from psalm.events import AgentCallFailed, AgentCallRetrying, emit
from psalm.exceptions import PSALMAgentError
from psalm.models.config import AgentConfig


@dataclass
class _RunExecution:
    semaphore: asyncio.Semaphore
    max_retries: int
    backoff_factor: float


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, execution: _RunExecution) -> None:
        self._config = config
        self._execution = execution
        self._llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=SecretStr(config.api_key) if config.api_key else None,
            organization=config.org_id,
            model=config.model,
            temperature=config.temperature,
            max_completion_tokens=config.max_tokens,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            seed=config.seed,
            timeout=config.timeout_seconds,
        )

    @property
    @abstractmethod
    def role(self) -> str: ...

    async def _call_llm(self, messages: list[Any]) -> Any:
        max_retries = self._execution.max_retries
        for attempt in range(max_retries):
            try:
                async with self._execution.semaphore:
                    return await self._llm.ainvoke(messages)
            except Exception as exc:
                if attempt == max_retries - 1:
                    await emit(AgentCallFailed(
                        role=self.role, attempts=max_retries, code="PSALM-A003", error=str(exc),
                    ))
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=f"LLM retry limit reached after {max_retries} attempts.",
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": max_retries,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                backoff = self._execution.backoff_factor**attempt
                jittered = random.uniform(0, backoff)
                await emit(AgentCallRetrying(
                    role=self.role, attempt=attempt + 1, max_attempts=max_retries,
                    backoff_seconds=jittered, error=str(exc),
                ))
                await asyncio.sleep(jittered)
        raise RuntimeError("unreachable")

    async def _call_structured(self, structured_llm: Any, messages: list[Any]) -> Any:
        max_retries = self._execution.max_retries
        for attempt in range(max_retries):
            try:
                async with self._execution.semaphore:
                    return await structured_llm.ainvoke(messages)
            except Exception as exc:
                if attempt == max_retries - 1:
                    await emit(AgentCallFailed(
                        role=self.role, attempts=max_retries, code="PSALM-A003", error=str(exc),
                    ))
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=(
                            f"Structured LLM retry limit reached after {max_retries} attempts."
                        ),
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": max_retries,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                backoff = self._execution.backoff_factor**attempt
                jittered = random.uniform(0, backoff)
                await emit(AgentCallRetrying(
                    role=self.role, attempt=attempt + 1, max_attempts=max_retries,
                    backoff_seconds=jittered, error=str(exc),
                ))
                await asyncio.sleep(jittered)
        raise RuntimeError("unreachable")
```

- [ ] **Step 4: Update `Juror.__init__`**

In `psalm/agents/juror.py`, replace lines 177-179:
```python
    def __init__(self, config: AgentConfig, juror_id: str) -> None:
        super().__init__(config)
        self._juror_id = juror_id
```
with:
```python
    def __init__(self, config: AgentConfig, juror_id: str, execution: _RunExecution) -> None:
        super().__init__(config, execution)
        self._juror_id = juror_id
```
Add `_RunExecution` to this file's import from `psalm.agents.base`. Find the existing import line:
```python
from psalm.agents.base import BaseAgent
```
and replace it with:
```python
from psalm.agents.base import BaseAgent, _RunExecution
```

- [ ] **Step 5: Add the shared `run_execution` fixture to `tests/conftest.py`**

In `tests/conftest.py`, add `import asyncio` as the first import line (before `from contextlib import contextmanager`), and add `from psalm.agents.base import _RunExecution` to the existing block of `from psalm...` imports, placed before `from psalm.events.base import EventSink` (alphabetically, `psalm.agents` sorts before `psalm.events`). Then add this fixture immediately after the existing `agent_config` fixture (before the `debate_config` fixture):
```python
@pytest.fixture
def run_execution() -> _RunExecution:
    return _RunExecution(semaphore=asyncio.Semaphore(8), max_retries=3, backoff_factor=2.0)
```

- [ ] **Step 6: Update the `test_agent` fixture in `tests/unit/agents/test_base.py`**

Replace:
```python
@pytest.fixture
def test_agent(agent_config):
    return _TestAgent(config=agent_config)
```
with:
```python
@pytest.fixture
def test_agent(agent_config, run_execution):
    return _TestAgent(config=agent_config, execution=run_execution)
```

- [ ] **Step 7: Update every `Juror(...)` construction in `tests/unit/agents/test_juror.py`**

Replace line 11-13:
```python
@pytest.fixture
def juror(agent_config):
    return Juror(config=agent_config, juror_id="juror-0")
```
with:
```python
@pytest.fixture
def juror(agent_config, run_execution):
    return Juror(config=agent_config, juror_id="juror-0", execution=run_execution)
```

Replace line 288 and 293:
```python
async def test_juror_vote_accepts_dimension_parameter(agent_config, minimal_argumentation_log):
    from unittest.mock import AsyncMock, MagicMock, patch

    from psalm.agents.juror import Juror

    juror = Juror(config=agent_config, juror_id="juror-0")
```
with:
```python
async def test_juror_vote_accepts_dimension_parameter(agent_config, run_execution, minimal_argumentation_log):
    from unittest.mock import AsyncMock, MagicMock, patch

    from psalm.agents.juror import Juror

    juror = Juror(config=agent_config, juror_id="juror-0", execution=run_execution)
```

Replace line 321 and 326:
```python
async def test_juror_vote_prompt_includes_rubric_and_sub_dimensions(agent_config, minimal_argumentation_log):
    from unittest.mock import MagicMock, patch

    from psalm.agents.juror import Juror

    juror = Juror(config=agent_config, juror_id="juror-0")
```
with:
```python
async def test_juror_vote_prompt_includes_rubric_and_sub_dimensions(agent_config, run_execution, minimal_argumentation_log):
    from unittest.mock import MagicMock, patch

    from psalm.agents.juror import Juror

    juror = Juror(config=agent_config, juror_id="juror-0", execution=run_execution)
```

Replace line 377 and 383:
```python
async def test_juror_vote_all_dimensions_returns_list(agent_config, minimal_argumentation_log):
    from unittest.mock import AsyncMock, MagicMock, patch

    from psalm.agents.juror import Juror
    from psalm.models.result import JurorVote

    juror = Juror(config=agent_config, juror_id="juror-0")
```
with:
```python
async def test_juror_vote_all_dimensions_returns_list(agent_config, run_execution, minimal_argumentation_log):
    from unittest.mock import AsyncMock, MagicMock, patch

    from psalm.agents.juror import Juror
    from psalm.models.result import JurorVote

    juror = Juror(config=agent_config, juror_id="juror-0", execution=run_execution)
```

- [ ] **Step 8: Update every `Prosecutor(...)` construction in `tests/unit/agents/test_prosecutor.py`**

Replace line 9-11:
```python
@pytest.fixture
def prosecutor(agent_config):
    return Prosecutor(config=agent_config)
```
with:
```python
@pytest.fixture
def prosecutor(agent_config, run_execution):
    return Prosecutor(config=agent_config, execution=run_execution)
```

Replace lines 47-51:
```python
async def test_gather_arguments_role():
    from psalm.models.config import AgentConfig
    config = AgentConfig(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    prosecutor = Prosecutor(config=config)
    assert prosecutor.role == "prosecutor"
```
with:
```python
async def test_gather_arguments_role(run_execution):
    from psalm.models.config import AgentConfig
    config = AgentConfig(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    prosecutor = Prosecutor(config=config, execution=run_execution)
    assert prosecutor.role == "prosecutor"
```

Replace line 134 and 136:
```python
async def test_prosecutor_prompt_includes_sub_dimension_context(agent_config, sample_argument):
    from psalm.agents.prosecutor import Prosecutor
    prosecutor = Prosecutor(config=agent_config)
```
with:
```python
async def test_prosecutor_prompt_includes_sub_dimension_context(agent_config, run_execution, sample_argument):
    from psalm.agents.prosecutor import Prosecutor
    prosecutor = Prosecutor(config=agent_config, execution=run_execution)
```

Replace line 168 and 169:
```python
async def test_prosecutor_prompt_separates_infringement_and_exception_dimensions(agent_config, sample_argument):
    prosecutor = Prosecutor(config=agent_config)
```
with:
```python
async def test_prosecutor_prompt_separates_infringement_and_exception_dimensions(agent_config, run_execution, sample_argument):
    prosecutor = Prosecutor(config=agent_config, execution=run_execution)
```

Replace line 187 and 191:
```python
async def test_prosecutor_prompt_standalone_exception_dimension_is_mandatory(agent_config, sample_argument):
    # When an exception dimension runs its own standalone pipeline (no infringement dimension
    # present), it IS the subject of that pipeline's verdict and must be framed as mandatory —
    # not as an optional tool for a dimension that isn't even in the room.
    prosecutor = Prosecutor(config=agent_config)
```
with:
```python
async def test_prosecutor_prompt_standalone_exception_dimension_is_mandatory(agent_config, run_execution, sample_argument):
    # When an exception dimension runs its own standalone pipeline (no infringement dimension
    # present), it IS the subject of that pipeline's verdict and must be framed as mandatory —
    # not as an optional tool for a dimension that isn't even in the room.
    prosecutor = Prosecutor(config=agent_config, execution=run_execution)
```

Replace line 208 and 209:
```python
async def test_prosecutor_retry_hint_appears_in_prompt(agent_config, sample_argument):
    prosecutor = Prosecutor(config=agent_config)
```
with:
```python
async def test_prosecutor_retry_hint_appears_in_prompt(agent_config, run_execution, sample_argument):
    prosecutor = Prosecutor(config=agent_config, execution=run_execution)
```

- [ ] **Step 9: Update every `Defense(...)` construction in `tests/unit/agents/test_defense.py`**

Replace line 10-12:
```python
@pytest.fixture
def defense(agent_config):
    return Defense(config=agent_config)
```
with:
```python
@pytest.fixture
def defense(agent_config, run_execution):
    return Defense(config=agent_config, execution=run_execution)
```

Replace line 150 and 151:
```python
async def test_defense_counter_prompt_includes_sub_dimension_context(agent_config, sample_argument, sample_counter_argument):
    defense = Defense(config=agent_config)
```
with:
```python
async def test_defense_counter_prompt_includes_sub_dimension_context(agent_config, run_execution, sample_argument, sample_counter_argument):
    defense = Defense(config=agent_config, execution=run_execution)
```

Replace line 167 and 168:
```python
async def test_defense_prompt_separates_infringement_and_exception_dimensions(agent_config, sample_argument):
    defense = Defense(config=agent_config)
```
with:
```python
async def test_defense_prompt_separates_infringement_and_exception_dimensions(agent_config, run_execution, sample_argument):
    defense = Defense(config=agent_config, execution=run_execution)
```

Replace line 186 and 190:
```python
async def test_defense_prompt_standalone_exception_dimension_is_mandatory(agent_config, sample_argument):
    # When an exception dimension runs its own standalone pipeline (no infringement dimension
    # present), it IS the subject of that pipeline's verdict and must be framed as mandatory —
    # not as an optional tool for a dimension that isn't even in the room.
    defense = Defense(config=agent_config)
```
with:
```python
async def test_defense_prompt_standalone_exception_dimension_is_mandatory(agent_config, run_execution, sample_argument):
    # When an exception dimension runs its own standalone pipeline (no infringement dimension
    # present), it IS the subject of that pipeline's verdict and must be framed as mandatory —
    # not as an optional tool for a dimension that isn't even in the room.
    defense = Defense(config=agent_config, execution=run_execution)
```

Replace line 207 and 208:
```python
async def test_defense_retry_hint_appears_in_prompt(agent_config, sample_argument):
    defense = Defense(config=agent_config)
```
with:
```python
async def test_defense_retry_hint_appears_in_prompt(agent_config, run_execution, sample_argument):
    defense = Defense(config=agent_config, execution=run_execution)
```

- [ ] **Step 10: Update the `Judge(...)` construction in `tests/unit/agents/test_judge.py`**

Replace line 10-12:
```python
@pytest.fixture
def judge(agent_config):
    return Judge(config=agent_config)
```
with:
```python
@pytest.fixture
def judge(agent_config, run_execution):
    return Judge(config=agent_config, execution=run_execution)
```

- [ ] **Step 11: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/ tests/unit/models/test_config.py -v`
Expected: PASS (every test in `tests/unit/agents/test_base.py`, `test_juror.py`, `test_prosecutor.py`, `test_defense.py`, `test_judge.py`, plus Task 1's tests)

- [ ] **Step 12: Run the full suite to confirm nothing else broke**

Run: `python -m pytest tests/ -q`
Expected: `378 passed, 1 skipped`

**Note on the expected count:** the baseline this plan starts from is `370 passed, 1 skipped` (confirmed by running `python -m pytest tests/ -q` on a clean `v2` checkout before starting Task 1). Task 1 adds 5 new tests (`370 → 375`). Task 2 adds 3 new tests (`375 → 378`). Confirm the actual number Step 11 and Step 12 report matches your own running total as you complete each task — if the baseline you started from differs from 370, adjust the running total accordingly rather than treating `378` as a magic constant.

- [ ] **Step 13: Commit**

```bash
git add psalm/agents/base.py psalm/agents/juror.py tests/conftest.py tests/unit/agents/test_base.py tests/unit/agents/test_juror.py tests/unit/agents/test_prosecutor.py tests/unit/agents/test_defense.py tests/unit/agents/test_judge.py
git commit -m "feat: cap LLM call concurrency with a shared semaphore, add jitter and configurable retries"
```

---

## Task 3: Thread `_RunExecution` through the builder

**Files:**
- Modify: `psalm/builder.py`
- Modify: `tests/unit/test_builder.py`

**Interfaces:**
- Consumes: `psalm.models.config.ExecutionConfig` (Task 1), `psalm.agents.base._RunExecution` (Task 2), `BaseAgent`/`Juror` constructors now requiring `execution` (Task 2).
- Produces: `PSALM.with_execution(max_concurrent_llm_calls: int = 8, max_retries: int = 3, backoff_factor: float = 2.0) -> PSALM`. `PSALM._execution_config: ExecutionConfig` (defaults to `ExecutionConfig()`). `PSALM.build()` now constructs one `_RunExecution` per build and passes it to `_ping_all_llms`/`_assemble`.

- [ ] **Step 1: Write the failing tests**

Add `import asyncio` and `from psalm.agents.base import _RunExecution` to the top of `tests/unit/test_builder.py` (alongside the existing imports). Then append these tests to the file:
```python
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


async def test_build_shares_one_semaphore_across_prosecutor_and_jury():
    courtroom = await _build_psalm()
    prosecutor_execution = courtroom._courtroom._argumentation_phase._prosecutor._execution
    juror_execution = courtroom._courtroom._deliberation_phases[0]._jury[0]._execution
    judge_execution = courtroom._courtroom._deliberation_phases[0]._judge._execution
    assert prosecutor_execution.semaphore is juror_execution.semaphore
    assert prosecutor_execution.semaphore is judge_execution.semaphore


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
    assert execution.semaphore._value == 2


async def test_ping_llm_uses_execution_max_retries():
    from psalm.models.config import AgentConfig

    config = AgentConfig(**_agent_kwargs())
    execution = _RunExecution(semaphore=asyncio.Semaphore(8), max_retries=2, backoff_factor=1.0)
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=ConnectionError("persistent"))
    with (
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        patch("psalm.builder.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(PSALMConfigError):
            await PSALM()._ping_llm(config, "juror-1", execution)
    assert mock_llm.ainvoke.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_builder.py -v`
Expected: FAIL — `AttributeError: 'PSALM' object has no attribute '_execution_config'` and `TypeError: PSALM._ping_llm() missing 1 required positional argument: 'execution'` (from `test_ping_llm_retries_transient_failures_then_succeeds` / `test_ping_llm_raises_psalm_c006_after_exhausting_retries`, whose calls haven't been updated yet — that's Step 4 below)

- [ ] **Step 3: Wire `_RunExecution` through `psalm/builder.py`**

Add `import random` to the top-level imports (alongside the existing `import asyncio`, `import inspect`). Add a new import line:
```python
from psalm.agents.base import _RunExecution
```
placed before `from psalm.agents.defense import Defense` (alphabetically, `psalm.agents.base` sorts before `psalm.agents.defense`). Add `ExecutionConfig` to the existing import line:
```python
from psalm.models.config import AgentConfig, CaseInput, DebateConfig, EvaluationStrategy
```
becomes:
```python
from psalm.models.config import AgentConfig, CaseInput, DebateConfig, EvaluationStrategy, ExecutionConfig
```

Remove the module-level constants (no longer used):
```python
_PING_RETRY_ATTEMPTS = 3
_PING_BACKOFF_FACTOR = 2.0
```
and the comment block directly above them explaining the ping burst rationale (that rationale now lives in this plan's spec and Global Constraints instead).

In `PSALM.__init__`, add `self._execution_config: ExecutionConfig = ExecutionConfig()` right after `self._debate_config = DebateConfig()`.

Add this new method anywhere among the other `with_*` builder methods (e.g. directly after `with_voting`):
```python
    def with_execution(
        self,
        max_concurrent_llm_calls: int = 8,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> PSALM:
        self._execution_config = ExecutionConfig(
            max_concurrent_llm_calls=max_concurrent_llm_calls,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )
        return self
```

Replace `build`:
```python
    async def build(self) -> _BuiltPSALM:
        self._validate_config()
        await self._ping_all_llms()
        return self._assemble()
```
with:
```python
    async def build(self) -> _BuiltPSALM:
        self._validate_config()
        execution = _RunExecution(
            semaphore=asyncio.Semaphore(self._execution_config.max_concurrent_llm_calls),
            max_retries=self._execution_config.max_retries,
            backoff_factor=self._execution_config.backoff_factor,
        )
        await self._ping_all_llms(execution)
        return self._assemble(execution)
```

Replace `_ping_llm`:
```python
    async def _ping_llm(self, config: AgentConfig, role: str) -> None:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=SecretStr(config.api_key) if config.api_key else None,
            organization=config.org_id,
            model=config.model,
            max_completion_tokens=1,
        )
        last_exc: Exception | None = None
        for attempt in range(_PING_RETRY_ATTEMPTS):
            try:
                await llm.ainvoke([{"role": "user", "content": "ping"}])
                return
            except Exception as exc:
                last_exc = exc
                if attempt < _PING_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(_PING_BACKOFF_FACTOR**attempt)
        raise PSALMConfigError(
            code="PSALM-C006",
            message=f"LLM connection failed for agent '{role}'.",
            context={"role": role, "base_url": config.base_url, "model": config.model},
            suggestion="Check api_key, base_url, and network connectivity.",
            cause=last_exc,
        ) from last_exc
```
with:
```python
    async def _ping_llm(self, config: AgentConfig, role: str, execution: _RunExecution) -> None:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=SecretStr(config.api_key) if config.api_key else None,
            organization=config.org_id,
            model=config.model,
            max_completion_tokens=1,
        )
        last_exc: Exception | None = None
        for attempt in range(execution.max_retries):
            try:
                async with execution.semaphore:
                    await llm.ainvoke([{"role": "user", "content": "ping"}])
                return
            except Exception as exc:
                last_exc = exc
                if attempt < execution.max_retries - 1:
                    backoff = execution.backoff_factor**attempt
                    await asyncio.sleep(random.uniform(0, backoff))
        raise PSALMConfigError(
            code="PSALM-C006",
            message=f"LLM connection failed for agent '{role}'.",
            context={"role": role, "base_url": config.base_url, "model": config.model},
            suggestion="Check api_key, base_url, and network connectivity.",
            cause=last_exc,
        ) from last_exc
```

Replace `_ping_all_llms`:
```python
    async def _ping_all_llms(self) -> None:
        assert self._prosecutor_config is not None
        assert self._defense_config is not None
        assert self._judge_config is not None
        configs = [
            (self._prosecutor_config, "prosecutor"),
            (self._defense_config, "defense"),
            (self._judge_config, "judge"),
        ] + [(c, f"juror-{i}") for i, c in enumerate(self._jury_configs)]
        await asyncio.gather(*[self._ping_llm(cfg, role) for cfg, role in configs])
```
with:
```python
    async def _ping_all_llms(self, execution: _RunExecution) -> None:
        assert self._prosecutor_config is not None
        assert self._defense_config is not None
        assert self._judge_config is not None
        configs = [
            (self._prosecutor_config, "prosecutor"),
            (self._defense_config, "defense"),
            (self._judge_config, "judge"),
        ] + [(c, f"juror-{i}") for i, c in enumerate(self._jury_configs)]
        await asyncio.gather(*[self._ping_llm(cfg, role, execution) for cfg, role in configs])
```

Replace the start of `_assemble` (the signature and the four agent-construction lines only — the rest of the method, from `voting_strategies = [...]` onward, is unchanged):
```python
    def _assemble(self) -> _BuiltPSALM:
        assert self._prosecutor_config is not None
        assert self._defense_config is not None
        assert self._judge_config is not None
        prosecutor = Prosecutor(config=self._prosecutor_config)
        defense = Defense(config=self._defense_config)
        judge = Judge(config=self._judge_config)
        jury = [Juror(juror_id=f"juror-{i}", config=c) for i, c in enumerate(self._jury_configs)]
```
with:
```python
    def _assemble(self, execution: _RunExecution) -> _BuiltPSALM:
        assert self._prosecutor_config is not None
        assert self._defense_config is not None
        assert self._judge_config is not None
        prosecutor = Prosecutor(config=self._prosecutor_config, execution=execution)
        defense = Defense(config=self._defense_config, execution=execution)
        judge = Judge(config=self._judge_config, execution=execution)
        jury = [
            Juror(juror_id=f"juror-{i}", config=c, execution=execution)
            for i, c in enumerate(self._jury_configs)
        ]
```

- [ ] **Step 4: Update the two existing tests that call `_ping_llm` directly**

In `tests/unit/test_builder.py`, replace `test_ping_llm_retries_transient_failures_then_succeeds`:
```python
async def test_ping_llm_retries_transient_failures_then_succeeds():
    from psalm.models.config import AgentConfig

    config = AgentConfig(**_agent_kwargs())
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[ConnectionError("transient"), ConnectionError("transient"), None]
    )
    with (
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        patch("psalm.builder.asyncio.sleep", new=AsyncMock()),
    ):
        await PSALM()._ping_llm(config, "juror-0")
    assert mock_llm.ainvoke.call_count == 3
```
with:
```python
async def test_ping_llm_retries_transient_failures_then_succeeds():
    from psalm.models.config import AgentConfig

    config = AgentConfig(**_agent_kwargs())
    execution = _RunExecution(semaphore=asyncio.Semaphore(8), max_retries=3, backoff_factor=2.0)
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
```

Replace `test_ping_llm_raises_psalm_c006_after_exhausting_retries`:
```python
async def test_ping_llm_raises_psalm_c006_after_exhausting_retries():
    from psalm.models.config import AgentConfig

    config = AgentConfig(**_agent_kwargs())
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=ConnectionError("persistent"))
    with (
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        patch("psalm.builder.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(PSALMConfigError) as exc_info:
            await PSALM()._ping_llm(config, "juror-1")
    assert exc_info.value.code == "PSALM-C006"
    assert exc_info.value.cause is not None
    assert mock_llm.ainvoke.call_count == 3
```
with:
```python
async def test_ping_llm_raises_psalm_c006_after_exhausting_retries():
    from psalm.models.config import AgentConfig

    config = AgentConfig(**_agent_kwargs())
    execution = _RunExecution(semaphore=asyncio.Semaphore(8), max_retries=3, backoff_factor=2.0)
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_builder.py -v`
Expected: PASS (all tests in the file, including the 5 new ones from Step 1)

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `383 passed, 1 skipped` (378 from the end of Task 2 + 5 new tests from this task's Step 1)

- [ ] **Step 7: Commit**

```bash
git add psalm/builder.py tests/unit/test_builder.py
git commit -m "feat: thread shared execution config through PSALM.build()"
```

---

## Task 4: Web backend — `TrialConfigRequest` and `build_psalm`

**Files:**
- Modify: `examples/web/backend/schemas.py`
- Modify: `examples/web/backend/execution.py`
- Test: `examples/web/backend/tests/test_execution.py`

**Interfaces:**
- Consumes: `PSALM.with_execution(...)` (Task 3).
- Produces: `TrialConfigRequest.max_concurrent_llm_calls: int` (default `8`), `TrialConfigRequest.max_retries: int` (default `3`) — both `Field(..., ge=1)`. `build_psalm` forwards both into `.with_execution(...)`.

- [ ] **Step 1: Write the failing tests**

Append to `examples/web/backend/tests/test_execution.py`:
```python
async def test_build_psalm_forwards_execution_settings():
    from unittest.mock import MagicMock

    config = _config(max_concurrent_llm_calls=2, max_retries=1)
    resolved = resolve_config(config)
    captured = {}

    class _FakeBuilder:
        def with_prosecutor(self, **kw): return self
        def with_defense(self, **kw): return self
        def with_judge(self, **kw): return self
        def with_jury(self, jury): return self
        def with_dimensions(self, dims): return self
        def with_debate(self, **kw): return self
        def with_voting(self, strategies): return self
        def with_evaluation_strategy(self, strategy): return self
        def with_execution(self, **kw):
            captured.update(kw)
            return self
        async def build(self): return "built"

    with patch("execution.PSALM", return_value=_FakeBuilder()):
        result = await build_psalm(config, resolved)

    assert captured == {"max_concurrent_llm_calls": 2, "max_retries": 1}
    assert result == "built"


def test_trial_config_request_execution_defaults():
    config = _config()
    assert config.max_concurrent_llm_calls == 8
    assert config.max_retries == 3


def test_trial_config_request_rejects_non_positive_max_concurrent_llm_calls():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _config(max_concurrent_llm_calls=0)


def test_trial_config_request_rejects_non_positive_max_retries():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _config(max_retries=0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd examples/web/backend && python -m pytest tests/test_execution.py -v`
Expected: FAIL — `TypeError: TrialConfigRequest() got unexpected keyword arguments: 'max_concurrent_llm_calls', 'max_retries'` (Pydantic rejects unknown kwargs passed via `_config(**overrides)`)

- [ ] **Step 3: Add the fields to `TrialConfigRequest`**

In `examples/web/backend/schemas.py`, change the import line:
```python
from pydantic import BaseModel
```
to:
```python
from pydantic import BaseModel, Field
```

Replace `TrialConfigRequest`:
```python
class TrialConfigRequest(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str]
    evaluation_strategy: str = "fully_separate"
    argumentation_rounds: int = 3
    deliberation_rounds: int = 2
    time_limit_seconds: int = 120
    prosecutor: AgentConfigRequest = AgentConfigRequest()
    defense: AgentConfigRequest = AgentConfigRequest()
    judge: AgentConfigRequest = AgentConfigRequest()
    jury: list[JurorConfigRequest] = [
        JurorConfigRequest(), JurorConfigRequest(), JurorConfigRequest(),
    ]
```
with:
```python
class TrialConfigRequest(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str]
    evaluation_strategy: str = "fully_separate"
    argumentation_rounds: int = 3
    deliberation_rounds: int = 2
    time_limit_seconds: int = 120
    max_concurrent_llm_calls: int = Field(default=8, ge=1)
    max_retries: int = Field(default=3, ge=1)
    prosecutor: AgentConfigRequest = AgentConfigRequest()
    defense: AgentConfigRequest = AgentConfigRequest()
    judge: AgentConfigRequest = AgentConfigRequest()
    jury: list[JurorConfigRequest] = [
        JurorConfigRequest(), JurorConfigRequest(), JurorConfigRequest(),
    ]
```

- [ ] **Step 4: Forward the settings in `build_psalm`**

In `examples/web/backend/execution.py`, replace:
```python
    try:
        return await (
            PSALM()
            .with_prosecutor(**resolved["prosecutor"])
            .with_defense(**resolved["defense"])
            .with_judge(**resolved["judge"])
            .with_jury(resolved["jury"])
            .with_dimensions(dimensions)
            .with_debate(
                argumentation_rounds=config.argumentation_rounds,
                deliberation_rounds=config.deliberation_rounds,
                time_limit_seconds=config.time_limit_seconds,
            )
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .with_evaluation_strategy(evaluation_strategy)
            .build()
        )
    except PSALMConfigError as exc:
        raise TrialStartError(code=exc.code, message=exc.message, context=exc.context) from exc
```
with:
```python
    try:
        return await (
            PSALM()
            .with_prosecutor(**resolved["prosecutor"])
            .with_defense(**resolved["defense"])
            .with_judge(**resolved["judge"])
            .with_jury(resolved["jury"])
            .with_dimensions(dimensions)
            .with_debate(
                argumentation_rounds=config.argumentation_rounds,
                deliberation_rounds=config.deliberation_rounds,
                time_limit_seconds=config.time_limit_seconds,
            )
            .with_execution(
                max_concurrent_llm_calls=config.max_concurrent_llm_calls,
                max_retries=config.max_retries,
            )
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .with_evaluation_strategy(evaluation_strategy)
            .build()
        )
    except PSALMConfigError as exc:
        raise TrialStartError(code=exc.code, message=exc.message, context=exc.context) from exc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd examples/web/backend && python -m pytest tests/test_execution.py -v`
Expected: PASS (all tests in the file, including the 4 new ones)

- [ ] **Step 6: Run the full backend suite**

Run: `cd examples/web/backend && python -m pytest -q`
Expected: all pre-existing backend tests still pass, plus the 4 new ones (check the printed total against a baseline run before Step 1, e.g. `python -m pytest -q` before this task's changes, and confirm the count increased by exactly 4)

- [ ] **Step 7: Commit**

```bash
git add examples/web/backend/schemas.py examples/web/backend/execution.py examples/web/backend/tests/test_execution.py
git commit -m "feat(web): forward execution concurrency/retry settings to PSALM builder"
```

---

## Task 5: Web frontend — trial config form fields

**Files:**
- Modify: `examples/web/frontend/src/api/types.ts`
- Modify: `examples/web/frontend/src/routes/SetupPage.tsx`
- Test: `examples/web/frontend/src/routes/SetupPage.test.tsx`

**Interfaces:**
- Consumes: `TrialConfigRequest.max_concurrent_llm_calls`/`max_retries` (Task 4) — the frontend field names must match these exactly since they're sent as the JSON request body.
- Produces: two new `NumberInput`s in `SetupPage`'s "Advanced settings" accordion, `id="max-concurrent-llm-calls"` and `id="max-retries"`, defaulting to `8` and `3`.

- [ ] **Step 1: Write the failing test assertions**

In `examples/web/frontend/src/routes/SetupPage.test.tsx`, in the `"submits the trial with the right payload and navigates on success"` test, add these two lines directly after `expect(payload.dimensions).toContain("Character");`:
```tsx
    expect(payload.max_concurrent_llm_calls).toBe(8);
    expect(payload.max_retries).toBe(3);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd examples/web/frontend && npx vitest run src/routes/SetupPage.test.tsx`
Expected: FAIL — `expect(payload.max_concurrent_llm_calls).toBe(8)` fails because `payload.max_concurrent_llm_calls` is `undefined`

- [ ] **Step 3: Add the fields to `TrialConfigInput`**

In `examples/web/frontend/src/api/types.ts`, replace:
```ts
export interface TrialConfigInput {
  source_text: string;
  target_text: string;
  dimensions: string[];
  evaluation_strategy: string;
  argumentation_rounds: number;
  deliberation_rounds: number;
  time_limit_seconds: number;
  prosecutor: AgentConfigInput;
  defense: AgentConfigInput;
  judge: AgentConfigInput;
  jury: JurorConfigInput[];
}
```
with:
```ts
export interface TrialConfigInput {
  source_text: string;
  target_text: string;
  dimensions: string[];
  evaluation_strategy: string;
  argumentation_rounds: number;
  deliberation_rounds: number;
  time_limit_seconds: number;
  max_concurrent_llm_calls: number;
  max_retries: number;
  prosecutor: AgentConfigInput;
  defense: AgentConfigInput;
  judge: AgentConfigInput;
  jury: JurorConfigInput[];
}
```

- [ ] **Step 4: Add state, form fields, and payload wiring to `SetupPage.tsx`**

Replace:
```tsx
  const [timeLimitSeconds, setTimeLimitSeconds] = useState(120);
```
with:
```tsx
  const [timeLimitSeconds, setTimeLimitSeconds] = useState(120);
  const [maxConcurrentLlmCalls, setMaxConcurrentLlmCalls] = useState(8);
  const [maxRetries, setMaxRetries] = useState(3);
```

Replace the `startTrial` call inside `handleSubmit`:
```tsx
      const { trial_id } = await startTrial({
        source_text: sourceText,
        target_text: targetText,
        dimensions: selectedDimensions,
        evaluation_strategy: evaluationStrategy,
        argumentation_rounds: argumentationRounds,
        deliberation_rounds: deliberationRounds,
        time_limit_seconds: timeLimitSeconds,
        prosecutor,
        defense,
        judge,
        jury,
      });
```
with:
```tsx
      const { trial_id } = await startTrial({
        source_text: sourceText,
        target_text: targetText,
        dimensions: selectedDimensions,
        evaluation_strategy: evaluationStrategy,
        argumentation_rounds: argumentationRounds,
        deliberation_rounds: deliberationRounds,
        time_limit_seconds: timeLimitSeconds,
        max_concurrent_llm_calls: maxConcurrentLlmCalls,
        max_retries: maxRetries,
        prosecutor,
        defense,
        judge,
        jury,
      });
```

Replace the `time-limit` `NumberInput` inside the "Advanced settings" `Accordion.Panel`:
```tsx
                    <NumberInput
                      id="time-limit" label="Time limit (seconds)" min={1}
                      value={timeLimitSeconds}
                      onChange={(value) => setTimeLimitSeconds(Number(value))}
                    />
```
with:
```tsx
                    <NumberInput
                      id="time-limit" label="Time limit (seconds)" min={1}
                      value={timeLimitSeconds}
                      onChange={(value) => setTimeLimitSeconds(Number(value))}
                    />
                    <NumberInput
                      id="max-concurrent-llm-calls" label="Max concurrent LLM calls" min={1}
                      value={maxConcurrentLlmCalls}
                      onChange={(value) => setMaxConcurrentLlmCalls(Number(value))}
                    />
                    <NumberInput
                      id="max-retries" label="Max retries" min={1}
                      value={maxRetries}
                      onChange={(value) => setMaxRetries(Number(value))}
                    />
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd examples/web/frontend && npx vitest run src/routes/SetupPage.test.tsx`
Expected: PASS (all tests in the file)

- [ ] **Step 6: Run the full frontend suite**

Run: `cd examples/web/frontend && npm test`
Expected: all tests pass (no regressions in other files that import `TrialConfigInput` or render `SetupPage`)

- [ ] **Step 7: Commit**

```bash
git add examples/web/frontend/src/api/types.ts examples/web/frontend/src/routes/SetupPage.tsx examples/web/frontend/src/routes/SetupPage.test.tsx
git commit -m "feat(web): expose max concurrent LLM calls and max retries in the trial config form"
```

---

## Task 6: Full-suite verification

**Files:** none (verification only)

**Interfaces:** none — this task runs the three test suites end-to-end and confirms nothing regressed.

- [ ] **Step 1: Run the full SDK suite**

Run: `python -m pytest tests/ -q`
Expected: `383 passed, 1 skipped` (per the running total established in Task 3, Step 6 — if any earlier task's actual count differed from this plan's prediction, expect that adjusted total instead, not literally `383`)

- [ ] **Step 2: Run the full web backend suite**

Run: `cd examples/web/backend && python -m pytest -q`
Expected: all tests pass, 0 failures

- [ ] **Step 3: Run the full web frontend suite**

Run: `cd examples/web/frontend && npm test`
Expected: all tests pass, 0 failures

- [ ] **Step 4: Manually sanity-check the demo app (if a local OpenAI-compatible endpoint is available)**

Start the backend (`cd examples/web/backend && uvicorn main:app --reload`) and frontend (`cd examples/web/frontend && npm run dev`), open the app, select all 10 dimensions in the trial config form, confirm the "Max concurrent LLM calls" and "Max retries" fields appear in Advanced settings pre-filled with `8` and `3`, and start a trial. This step is exploratory (not a pass/fail gate for this plan) — its purpose is to confirm the original reported symptom (`Trial failed: Structured LLM retry limit reached after 3 attempts.` under a full-dimension run) no longer occurs at the default cap. Skip if no live LLM endpoint is available in the environment; the automated suites in Steps 1-3 are the actual completion gate.

- [ ] **Step 5: Report**

No commit for this task (verification only). Confirm to the user: exact pass/fail counts from Steps 1-3, and whether Step 4 was performed and what was observed.
