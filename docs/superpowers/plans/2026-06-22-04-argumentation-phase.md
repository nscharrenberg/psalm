# Argumentation Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `ArgumentationPhase` as a LangGraph `StateGraph` subgraph that runs prosecutor/defense argumentation rounds, judge validation, conditional cross-examination, and adaptive stability detection.

**Architecture:** `BasePhase` defines the interface. `ArgumentationPhase` compiles a LangGraph `StateGraph(ArgumentationState)`. Nodes are plain `async` functions that receive `ArgumentationState` and return a partial state dict. Conditional edges route between rounds, cross-examination, and termination. The compiled graph is invoked via `phase.run(case_input) -> ArgumentationLog`.

**Tech Stack:** Python 3.14+, LangGraph 1.2.6+, Pydantic 2.13.4+, pytest-asyncio

## Global Constraints

- `requires-python = ">=3.14"`
- Nodes return `dict` (partial state update), never mutate the state object
- `ArgumentationState` is a Pydantic `BaseModel` — LangGraph uses it as the state schema
- Cross-examination triggered only when `Judge.should_cross_examine()` returns `True`
- Stability detected when current round claims == previous round claims (implemented in `Judge.detect_stability()`)
- Phase always terminates: round limit reached OR stability detected
- Fallback: if all agents fail, `ArgumentationLog(rounds=[])` returned with error in metadata

---

### Task 1: BasePhase and ArgumentationPhase Scaffold

**Files:**
- Create: `psalm/phases/base.py`
- Create: `psalm/phases/argumentation.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_argumentation_phase.py` (scaffold only — filled in Task 4)

**Interfaces:**
- Produces:
  - `BasePhase` — abstract with `async run(case_input) -> Any`
  - `ArgumentationPhase(prosecutor, defense, judge, config)` — compiles LangGraph graph in `__init__`
  - `ArgumentationPhase.run(case_input: CaseInput) -> ArgumentationLog`
  - `CaseInput(source_text, target_text, dimensions)` — added to `psalm/models/config.py`

- [ ] **Step 1: Add `CaseInput` to `psalm/models/config.py`**

Open `psalm/models/config.py` and add at the bottom:

```python
class CaseInput(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str] = ["character", "world-building", "plot"]
```

- [ ] **Step 2: Write the scaffold test (will be extended in Task 4)**

```python
# tests/integration/test_argumentation_phase.py
import pytest
# Tests are added in Task 4 of this plan.
```

- [ ] **Step 3: Implement `psalm/phases/base.py`**

```python
from abc import ABC, abstractmethod
from typing import Any
from psalm.models.config import CaseInput


class BasePhase(ABC):
    @abstractmethod
    async def run(self, case_input: CaseInput) -> Any: ...
```

- [ ] **Step 4: Implement `psalm/phases/argumentation.py` (graph scaffold)**

```python
from __future__ import annotations
from typing import Any
from langgraph.graph import END, StateGraph
from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.prosecutor import Prosecutor
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.result import ArgumentationLog, RoundArguments
from psalm.models.state import ArgumentationState
from psalm.phases.base import BasePhase


class ArgumentationPhase(BasePhase):
    def __init__(self, prosecutor: Prosecutor, defense: Defense, judge: Judge, config: DebateConfig) -> None:
        self._prosecutor = prosecutor
        self._defense = defense
        self._judge = judge
        self._config = config
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ArgumentationState)

        graph.add_node("prosecutor_gather", self._prosecutor_gather)
        graph.add_node("judge_validate_prosecution", self._judge_validate_prosecution)
        graph.add_node("defense_gather", self._defense_gather)
        graph.add_node("judge_validate_defense", self._judge_validate_defense)
        graph.add_node("cross_examination", self._cross_examination)
        graph.add_node("check_next_round", self._check_next_round)
        graph.add_node("finalize_arguments", self._finalize_arguments)

        graph.set_entry_point("prosecutor_gather")
        graph.add_edge("prosecutor_gather", "judge_validate_prosecution")
        graph.add_edge("judge_validate_prosecution", "defense_gather")
        graph.add_edge("defense_gather", "judge_validate_defense")
        graph.add_conditional_edges(
            "judge_validate_defense",
            self._route_cross_exam,
            {"cross_examine": "cross_examination", "skip": "check_next_round"},
        )
        graph.add_edge("cross_examination", "check_next_round")
        graph.add_conditional_edges(
            "check_next_round",
            self._route_next_round,
            {"continue": "prosecutor_gather", "done": "finalize_arguments"},
        )
        graph.add_edge("finalize_arguments", END)

        return graph.compile()

    async def run(self, case_input: CaseInput) -> ArgumentationLog:
        initial_state = ArgumentationState(
            source_text=case_input.source_text,
            target_text=case_input.target_text,
            dimensions=case_input.dimensions,
            max_rounds=self._config.rounds,
        )
        final_state = await self._graph.ainvoke(initial_state)
        return final_state["argumentation_log"]

    # --- Nodes ---

    async def _prosecutor_gather(self, state: ArgumentationState) -> dict[str, Any]:
        arguments = await self._prosecutor.gather_arguments(
            source_text=state.source_text,
            target_text=state.target_text,
            dimensions=state.dimensions,
            round=state.current_round + 1,
        )
        return {"_pending_prosecution_arguments": arguments}

    async def _judge_validate_prosecution(self, state: ArgumentationState) -> dict[str, Any]:
        pending = state.model_extra.get("_pending_prosecution_arguments", [])
        valid = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg)
        return {"_validated_prosecution_arguments": valid}

    async def _defense_gather(self, state: ArgumentationState) -> dict[str, Any]:
        prosecution_args = state.model_extra.get("_validated_prosecution_arguments", [])
        counter_arguments = await self._defense.gather_counter_arguments(
            source_text=state.source_text,
            target_text=state.target_text,
            dimensions=state.dimensions,
            prosecutor_arguments=prosecution_args,
            round=state.current_round + 1,
        )
        return {"_pending_defense_arguments": counter_arguments}

    async def _judge_validate_defense(self, state: ArgumentationState) -> dict[str, Any]:
        pending = state.model_extra.get("_pending_defense_arguments", [])
        valid = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg)

        prosecution_args = state.model_extra.get("_validated_prosecution_arguments", [])
        cross_exam = await self._judge.should_cross_examine(prosecution_args, valid)

        new_round = RoundArguments(
            round=state.current_round + 1,
            arguments=prosecution_args,
            counter_arguments=valid,
        )
        return {
            "cross_examination_triggered": cross_exam,
            "arguments": state.arguments + prosecution_args,
            "counter_arguments": state.counter_arguments + valid,
            "_current_round_record": new_round,
        }

    async def _cross_examination(self, state: ArgumentationState) -> dict[str, Any]:
        # Cross-examination: defense challenges prosecution on discrepancies (and vice versa)
        # For now this is a no-op node — cross-examination prompts are embedded in a future extension
        return {}

    async def _check_next_round(self, state: ArgumentationState) -> dict[str, Any]:
        prev_args = state.arguments[: -len(state.model_extra.get("_validated_prosecution_arguments", [1])) or None]
        stability = await self._judge.detect_stability(
            state.model_extra.get("_validated_prosecution_arguments", []),
            prev_args,
        )
        return {
            "current_round": state.current_round + 1,
            "stability_detected": stability,
        }

    async def _finalize_arguments(self, state: ArgumentationState) -> dict[str, Any]:
        rounds = []
        all_args = state.arguments
        all_counters = state.counter_arguments
        for r in range(1, state.current_round + 1):
            round_args = [a for a in all_args if a.round == r]
            round_counters = [a for a in all_counters if a.round == r]
            rounds.append(RoundArguments(round=r, arguments=round_args, counter_arguments=round_counters))
        return {"argumentation_log": ArgumentationLog(rounds=rounds)}

    # --- Routing ---

    def _route_cross_exam(self, state: ArgumentationState) -> str:
        return "cross_examine" if state.cross_examination_triggered else "skip"

    def _route_next_round(self, state: ArgumentationState) -> str:
        if state.stability_detected or state.current_round >= state.max_rounds:
            return "done"
        return "continue"
```

- [ ] **Step 5: Run existing tests to ensure nothing broken**

```bash
uv run pytest tests/unit/ -v
```

Expected: all previous tests PASS.

- [ ] **Step 6: Commit**

```bash
git add psalm/phases/base.py psalm/phases/argumentation.py psalm/models/config.py tests/integration/test_argumentation_phase.py
git commit -m "feat: scaffold ArgumentationPhase LangGraph subgraph"
```

---

### Task 2: Fix State Handling and Integration Tests

The scaffold above uses `model_extra` for passing temporary data between nodes, which is not idiomatic LangGraph. This task refactors the state to include proper intermediate fields and adds full integration tests.

**Files:**
- Modify: `psalm/models/state.py`
- Modify: `psalm/phases/argumentation.py`
- Modify: `tests/integration/test_argumentation_phase.py`

**Interfaces:**
- Produces: `ArgumentationPhase.run()` fully tested with mock agents

- [ ] **Step 1: Add intermediate fields to `ArgumentationState`**

Open `psalm/models/state.py` and update `ArgumentationState`:

```python
class ArgumentationState(BaseModel):
    source_text: str
    target_text: str
    dimensions: list[str]
    max_rounds: int
    current_round: int = 0
    arguments: list[Argument] = Field(default_factory=list)
    counter_arguments: list[Argument] = Field(default_factory=list)
    cross_examination_triggered: bool = False
    stability_detected: bool = False
    message_queue: list[dict[str, Any]] = Field(default_factory=list)
    # Intermediate fields for passing data between nodes within a round
    pending_prosecution_arguments: list[Argument] = Field(default_factory=list)
    validated_prosecution_arguments: list[Argument] = Field(default_factory=list)
    pending_defense_arguments: list[Argument] = Field(default_factory=list)
    argumentation_log: ArgumentationLog | None = None

    model_config = {"arbitrary_types_allowed": True}
```

- [ ] **Step 2: Refactor `psalm/phases/argumentation.py` to use typed state fields**

Replace the node implementations (keep graph structure identical, fix state access):

```python
    async def _prosecutor_gather(self, state: ArgumentationState) -> dict[str, Any]:
        arguments = await self._prosecutor.gather_arguments(
            source_text=state.source_text,
            target_text=state.target_text,
            dimensions=state.dimensions,
            round=state.current_round + 1,
        )
        return {"pending_prosecution_arguments": arguments}

    async def _judge_validate_prosecution(self, state: ArgumentationState) -> dict[str, Any]:
        valid = []
        for arg in state.pending_prosecution_arguments:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg)
        return {"validated_prosecution_arguments": valid}

    async def _defense_gather(self, state: ArgumentationState) -> dict[str, Any]:
        counter_arguments = await self._defense.gather_counter_arguments(
            source_text=state.source_text,
            target_text=state.target_text,
            dimensions=state.dimensions,
            prosecutor_arguments=state.validated_prosecution_arguments,
            round=state.current_round + 1,
        )
        return {"pending_defense_arguments": counter_arguments}

    async def _judge_validate_defense(self, state: ArgumentationState) -> dict[str, Any]:
        valid = []
        for arg in state.pending_defense_arguments:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg)
        cross_exam = await self._judge.should_cross_examine(state.validated_prosecution_arguments, valid)
        return {
            "cross_examination_triggered": cross_exam,
            "arguments": state.arguments + state.validated_prosecution_arguments,
            "counter_arguments": state.counter_arguments + valid,
        }

    async def _cross_examination(self, state: ArgumentationState) -> dict[str, Any]:
        return {}  # Future extension point

    async def _check_next_round(self, state: ArgumentationState) -> dict[str, Any]:
        prev_round_args = [a for a in state.arguments if a.round == state.current_round]
        current_round_args = state.validated_prosecution_arguments
        stability = await self._judge.detect_stability(current_round_args, prev_round_args)
        return {"current_round": state.current_round + 1, "stability_detected": stability}

    async def _finalize_arguments(self, state: ArgumentationState) -> dict[str, Any]:
        rounds = []
        for r in range(1, state.current_round + 1):
            round_args = [a for a in state.arguments if a.round == r]
            round_counters = [a for a in state.counter_arguments if a.round == r]
            rounds.append(RoundArguments(round=r, arguments=round_args, counter_arguments=round_counters))
        return {"argumentation_log": ArgumentationLog(rounds=rounds)}
```

- [ ] **Step 3: Write integration tests**

```python
# tests/integration/test_argumentation_phase.py
from unittest.mock import AsyncMock
import pytest
from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.prosecutor import Prosecutor
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.result import ValidationResult
from psalm.phases.argumentation import ArgumentationPhase


@pytest.fixture
def case_input():
    return CaseInput(
        source_text="The wizard had bright blue eyes and wore a silver cloak.",
        target_text="The sorcerer possessed azure irises and donned a grey mantle.",
        dimensions=["character"],
    )


@pytest.fixture
def mock_prosecutor(agent_config, sample_argument):
    prosecutor = AsyncMock(spec=Prosecutor)
    prosecutor.gather_arguments = AsyncMock(return_value=[sample_argument])
    return prosecutor


@pytest.fixture
def mock_defense(agent_config, sample_counter_argument):
    defense = AsyncMock(spec=Defense)
    defense.gather_counter_arguments = AsyncMock(return_value=[sample_counter_argument])
    return defense


@pytest.fixture
def mock_judge(agent_config):
    judge = AsyncMock(spec=Judge)
    judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=True))
    judge.should_cross_examine = AsyncMock(return_value=False)
    judge.detect_stability = AsyncMock(return_value=False)
    return judge


@pytest.fixture
def argumentation_phase(mock_prosecutor, mock_defense, mock_judge):
    config = DebateConfig(rounds=2)
    return ArgumentationPhase(
        prosecutor=mock_prosecutor,
        defense=mock_defense,
        judge=mock_judge,
        config=config,
    )


async def test_argumentation_phase_runs(argumentation_phase, case_input):
    log = await argumentation_phase.run(case_input)
    assert log is not None
    assert len(log.rounds) > 0


async def test_argumentation_phase_calls_prosecutor(argumentation_phase, case_input, mock_prosecutor):
    await argumentation_phase.run(case_input)
    assert mock_prosecutor.gather_arguments.called


async def test_argumentation_phase_calls_defense(argumentation_phase, case_input, mock_defense):
    await argumentation_phase.run(case_input)
    assert mock_defense.gather_counter_arguments.called


async def test_argumentation_phase_validates_arguments(argumentation_phase, case_input, mock_judge):
    await argumentation_phase.run(case_input)
    assert mock_judge.validate_argument.called


async def test_invalid_arguments_excluded(mock_prosecutor, mock_defense, mock_judge, case_input, sample_argument):
    mock_judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=False, rejection_reason="No excerpts."))
    config = DebateConfig(rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    # All arguments rejected by judge — rounds exist but args lists empty
    for round_rec in log.rounds:
        assert round_rec.arguments == []


async def test_stability_terminates_early(mock_prosecutor, mock_defense, mock_judge, case_input, sample_argument):
    mock_judge.detect_stability = AsyncMock(return_value=True)
    config = DebateConfig(rounds=5)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    # Should terminate after 1 round due to stability
    assert len(log.rounds) == 1
```

- [ ] **Step 4: Run integration tests**

```bash
uv run pytest tests/integration/test_argumentation_phase.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add psalm/models/state.py psalm/phases/argumentation.py tests/integration/test_argumentation_phase.py
git commit -m "feat: complete ArgumentationPhase with integration tests"
```
