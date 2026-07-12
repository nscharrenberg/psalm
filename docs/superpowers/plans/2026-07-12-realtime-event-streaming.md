# Realtime Event Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live, typed event stream (`_BuiltPSALM.astream_evaluate()`) and a callback adapter (`PSALM.with_event_listener()`) so a consumer can observe every step of a courtroom run in realtime — arguments, judge rulings, jury votes/discussion, verdicts, agent retries/failures — while leaving `.evaluate()`/`.aevaluate()` with no listeners registered completely unchanged.

**Architecture:** A `contextvars.ContextVar`-bound `EventSink` (an `asyncio.Queue` wrapper) is created fresh per streamed run. A single `emit(event)` helper reads the ambient sink and pushes to it, no-opping when unbound. Deep call sites (LangGraph node methods, agents, courtroom orchestration) call `emit()` directly with zero signature changes. Each dimension's `asyncio.gather`-scheduled task independently sets its own "current dimension" contextvar, so parallel dimensions tag their events correctly with no explicit threading.

**Tech Stack:** Python 3.14, Pydantic v2 (discriminated unions), LangGraph (existing `StateGraph` phases, untouched topology), `asyncio` (contextvars, `Queue`, `create_task`/`wait`), pytest + pytest-asyncio (`asyncio_mode = "auto"`).

## Global Constraints

- No existing method signature or return type changes for `.evaluate()` / `.aevaluate()` when no listeners are registered — see spec §4.3.
- All new event fields must reuse existing models (`Argument`, `DimensionScore`, `PSALMResult`, etc.) — no new duplicate data shapes.
- `ruff` line length 100, `target-version = "py314"`; `pytest` `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed).
- Full existing test suite must remain green, unmodified in behavior, throughout (spec §6: no breaking changes).
- Spec reference: `docs/superpowers/specs/2026-07-12-realtime-event-streaming-design.md`.

---

### Task 1: Event envelope, context primitives, shared test helpers

**Files:**
- Create: `psalm/events/__init__.py` (placeholder, filled in Task 2)
- Create: `psalm/events/base.py`
- Create: `psalm/events/context.py`
- Create: `tests/unit/events/__init__.py`
- Create: `tests/unit/events/test_base.py`
- Create: `tests/unit/events/test_context.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Produces: `psalm.events.base.PSALMEvent` (pydantic base model — fields `event_id: str`, `sequence: int`, `timestamp: datetime`, `run_id: str`, `dimension: str | None`, `category: Literal["lifecycle","argumentation","deliberation","verdict","agent"]`, `type: str`), `psalm.events.base.EventSink` (`__init__(run_id: str)`, `async put(event: PSALMEvent) -> None`, `async get() -> PSALMEvent`, `empty() -> bool`), `psalm.events.context.emit(event: PSALMEvent) -> Awaitable[None]`, `psalm.events.context._current_sink: ContextVar[EventSink | None]`, `psalm.events.context._current_dimension: ContextVar[str | None]`.
- Produces (test helpers): `tests.conftest.bound_event_sink()` (context manager yielding a fresh `EventSink` bound to `_current_sink` for the duration of the `with` block), `tests.conftest.drain_events(sink) -> list[PSALMEvent]` (async, drains all queued events in order).

- [ ] **Step 1: Write failing tests for `PSALMEvent` and `EventSink`**

Create `tests/unit/events/__init__.py` (empty file).

Create `tests/unit/events/test_base.py`:

```python
from psalm.events.base import EventSink, PSALMEvent


def test_psalm_event_generates_unique_id_and_defaults():
    e1 = PSALMEvent(category="lifecycle", type="run_started")
    e2 = PSALMEvent(category="lifecycle", type="run_started")
    assert e1.event_id != e2.event_id
    assert e1.sequence == 0
    assert e1.run_id == ""
    assert e1.dimension is None


async def test_event_sink_put_stamps_run_id_and_increments_sequence():
    sink = EventSink(run_id="run-123")
    await sink.put(PSALMEvent(category="lifecycle", type="run_started"))
    await sink.put(PSALMEvent(category="lifecycle", type="run_started"))

    first = await sink.get()
    second = await sink.get()

    assert first.run_id == "run-123"
    assert second.run_id == "run-123"
    assert first.sequence == 1
    assert second.sequence == 2


async def test_event_sink_empty_reflects_queue_state():
    sink = EventSink(run_id="run-123")
    assert sink.empty() is True
    await sink.put(PSALMEvent(category="lifecycle", type="run_started"))
    assert sink.empty() is False
    await sink.get()
    assert sink.empty() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/events/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'psalm.events'`

- [ ] **Step 3: Implement `psalm/events/base.py`**

Create `psalm/events/__init__.py` (empty for now — filled in Task 2):

```python
```

Create `psalm/events/base.py`:

```python
from __future__ import annotations

import asyncio
import itertools
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class PSALMEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    sequence: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str = ""
    dimension: str | None = None
    category: Literal["lifecycle", "argumentation", "deliberation", "verdict", "agent"]
    type: str


class EventSink:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._queue: asyncio.Queue[PSALMEvent] = asyncio.Queue()
        self._seq = itertools.count(1)

    async def put(self, event: PSALMEvent) -> None:
        stamped = event.model_copy(update={"run_id": self.run_id, "sequence": next(self._seq)})
        await self._queue.put(stamped)

    async def get(self) -> PSALMEvent:
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/events/test_base.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write failing tests for `emit()` and the context vars**

Create `tests/unit/events/test_context.py`:

```python
from psalm.events.base import EventSink, PSALMEvent
from psalm.events.context import _current_dimension, _current_sink, emit


async def test_emit_is_noop_without_bound_sink():
    # No sink bound anywhere in this test's task context — must not raise or block.
    await emit(PSALMEvent(category="lifecycle", type="run_started"))


async def test_emit_delivers_to_bound_sink():
    sink = EventSink(run_id="run-abc")
    token = _current_sink.set(sink)
    try:
        await emit(PSALMEvent(category="lifecycle", type="run_started"))
    finally:
        _current_sink.reset(token)

    delivered = await sink.get()
    assert delivered.run_id == "run-abc"
    assert delivered.type == "run_started"


async def test_emit_fills_dimension_from_ambient_context():
    sink = EventSink(run_id="run-abc")
    sink_token = _current_sink.set(sink)
    dim_token = _current_dimension.set("character")
    try:
        await emit(PSALMEvent(category="argumentation", type="argumentation_round_started"))
    finally:
        _current_sink.reset(sink_token)
        _current_dimension.reset(dim_token)

    delivered = await sink.get()
    assert delivered.dimension == "character"


async def test_emit_does_not_override_explicit_dimension():
    sink = EventSink(run_id="run-abc")
    sink_token = _current_sink.set(sink)
    dim_token = _current_dimension.set("character")
    try:
        await emit(PSALMEvent(
            category="argumentation", type="argumentation_round_started", dimension="plot",
        ))
    finally:
        _current_sink.reset(sink_token)
        _current_dimension.reset(dim_token)

    delivered = await sink.get()
    assert delivered.dimension == "plot"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/unit/events/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'psalm.events.context'`

- [ ] **Step 7: Implement `psalm/events/context.py`**

```python
from __future__ import annotations

from contextvars import ContextVar

from psalm.events.base import EventSink, PSALMEvent

_current_sink: ContextVar[EventSink | None] = ContextVar("_current_sink", default=None)
_current_dimension: ContextVar[str | None] = ContextVar("_current_dimension", default=None)


async def emit(event: PSALMEvent) -> None:
    sink = _current_sink.get()
    if sink is None:
        return
    if event.dimension is None:
        dim = _current_dimension.get()
        if dim is not None:
            event = event.model_copy(update={"dimension": dim})
    await sink.put(event)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/unit/events/ -v`
Expected: PASS (7 tests)

- [ ] **Step 9: Add shared test helpers to `tests/conftest.py`**

Add these imports and definitions at the end of `tests/conftest.py` (after the existing fixtures):

```python
from contextlib import contextmanager

from psalm.events.base import EventSink
from psalm.events.context import _current_sink


@contextmanager
def bound_event_sink():
    """Bind a fresh EventSink to the ambient context for the duration of the block."""
    sink = EventSink(run_id="test-run")
    token = _current_sink.set(sink)
    try:
        yield sink
    finally:
        _current_sink.reset(token)


async def drain_events(sink: EventSink) -> list:
    events = []
    while not sink.empty():
        events.append(await sink.get())
    return events
```

- [ ] **Step 10: Verify the helper works with a quick smoke test**

Add to `tests/unit/events/test_context.py`:

```python
from tests.conftest import bound_event_sink, drain_events


async def test_bound_event_sink_and_drain_events_helpers():
    with bound_event_sink() as sink:
        await emit(PSALMEvent(category="lifecycle", type="run_started"))
        await emit(PSALMEvent(category="lifecycle", type="run_started"))
        events = await drain_events(sink)
    assert len(events) == 2
    assert events[0].sequence == 1
    assert events[1].sequence == 2
```

Run: `pytest tests/unit/events/test_context.py -v`
Expected: PASS (5 tests)

- [ ] **Step 11: Commit**

```bash
git add psalm/events/ tests/unit/events/ tests/conftest.py
git commit -m "feat: add event envelope, context-bound sink, and emit() primitive"
```

---

### Task 2: Concrete event types and package exports

**Files:**
- Create: `psalm/events/types.py`
- Modify: `psalm/events/__init__.py`
- Create: `tests/unit/events/test_types.py`

**Interfaces:**
- Consumes: `psalm.events.base.PSALMEvent` (Task 1)
- Produces: all 19 concrete event classes (listed below) importable from `psalm.events` and `psalm.events.types`; `psalm.events.types.Event` (discriminated union type, discriminator `"type"`); `psalm.events.types.EventAdapter` (`TypeAdapter[Event]`, for round-trip validation).

- [ ] **Step 1: Write failing tests for the event types**

Create `tests/unit/events/test_types.py`:

```python
from psalm.dimensions.base import Importance, SimilarityScore
from psalm.models.evidence import Argument, Proof
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
    DimensionScore,
    DimensionVerdict,
    PSALMResult,
    ResultMetadata,
)
from psalm.events.types import (
    AgentCallFailed,
    AgentCallRetrying,
    ArgumentBatchCompletenessRetry,
    ArgumentRejected,
    ArgumentSubmitted,
    ArgumentValidated,
    ArgumentationRoundStarted,
    ArgumentationStabilityChecked,
    ClosingArgumentDelivered,
    ClosingStatementDelivered,
    DeliberationRoundStarted,
    DimensionStarted,
    DimensionVerdictReached,
    EventAdapter,
    FinalVerdictReached,
    JuryConsensusChecked,
    JuryDiscussionMessage,
    JurorVoteCast,
    RunFailed,
    RunStarted,
    VotingStrategyApplied,
)


def _sample_argument() -> Argument:
    return Argument(
        claim="Test claim.",
        dimension="character",
        proofs=[Proof(source_excerpt="src", target_excerpt="tgt", relevance="rel")],
        agent_role="prosecutor",
        round=1,
    )


def _sample_result() -> PSALMResult:
    return PSALMResult(
        verdict="Guilty",
        rationale="Because.",
        dimension_verdicts=[
            DimensionVerdict(
                dimension="character",
                importance=Importance.HIGH,
                verdict="Guilty",
                weighted_score=0.8,
                argumentation_log=ArgumentationLog(rounds=[]),
                debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
            )
        ],
        metadata=ResultMetadata(
            duration_seconds=1.0,
            argumentation_rounds_used=1,
            deliberation_rounds_used=1,
            voting_strategy_applied="unanimous",
        ),
    )


def test_run_started_defaults():
    e = RunStarted(dimensions=["character"], evaluation_strategy="fully_separate",
                    source_length=10, target_length=12)
    assert e.category == "lifecycle"
    assert e.type == "run_started"


def test_run_failed_defaults():
    e = RunFailed(code="PSALM-A003", message="boom", context={})
    assert e.category == "lifecycle"
    assert e.type == "run_failed"


def test_dimension_started_defaults():
    e = DimensionStarted(dimension_type="infringement", importance="high")
    assert e.category == "lifecycle"
    assert e.type == "dimension_started"


def test_argumentation_round_started_defaults():
    e = ArgumentationRoundStarted(round=1)
    assert e.category == "argumentation"
    assert e.type == "argumentation_round_started"


def test_argument_submitted_defaults():
    e = ArgumentSubmitted(round=1, role="prosecution", kind="argument", argument=_sample_argument())
    assert e.category == "argumentation"
    assert e.type == "argument_submitted"
    assert e.argument.claim == "Test claim."


def test_argument_validated_defaults():
    e = ArgumentValidated(round=1, role="prosecution", argument=_sample_argument())
    assert e.type == "argument_validated"


def test_argument_rejected_defaults():
    e = ArgumentRejected(round=1, role="prosecution", argument=_sample_argument(), reason="No proof.")
    assert e.type == "argument_rejected"
    assert e.reason == "No proof."


def test_closing_statement_delivered_defaults():
    e = ClosingStatementDelivered(round=1, role="defense", statement="Resting.")
    assert e.type == "closing_statement_delivered"


def test_argumentation_stability_checked_defaults():
    e = ArgumentationStabilityChecked(round=2, stability_detected=True)
    assert e.type == "argumentation_stability_checked"


def test_closing_argument_delivered_defaults():
    e = ClosingArgumentDelivered(role="prosecution", statement="Final words.")
    assert e.type == "closing_argument_delivered"


def test_argument_batch_completeness_retry_defaults():
    e = ArgumentBatchCompletenessRetry(round=1, role="prosecution", attempt=1, max_attempts=3)
    assert e.category == "argumentation"
    assert e.type == "argument_batch_completeness_retry"


def test_deliberation_round_started_defaults():
    e = DeliberationRoundStarted(round=1)
    assert e.category == "deliberation"
    assert e.type == "deliberation_round_started"


def test_juror_vote_cast_defaults():
    e = JurorVoteCast(
        round=1, juror_id="juror-0", vote="Guilty", rationale="Strong evidence.",
        dimension_scores=[DimensionScore(sub_dimension="x", score=SimilarityScore.CLEAR, reasoning="r")],
    )
    assert e.type == "juror_vote_cast"
    assert e.dimension_scores[0].sub_dimension == "x"


def test_jury_consensus_checked_defaults():
    e = JuryConsensusChecked(round=1, is_unanimous=True, top_verdict="Guilty")
    assert e.type == "jury_consensus_checked"


def test_jury_discussion_message_defaults():
    e = JuryDiscussionMessage(round=2, juror_id="juror-0", message="I think...")
    assert e.type == "jury_discussion_message"


def test_voting_strategy_applied_defaults():
    e = VotingStrategyApplied(strategy_name="SimpleMajorityVoting", is_tie=False, verdict="Guilty")
    assert e.category == "deliberation"
    assert e.type == "voting_strategy_applied"


def test_dimension_verdict_reached_defaults():
    e = DimensionVerdictReached(
        dimension_type="infringement", importance="high", verdict="Guilty", weighted_score=0.8,
    )
    assert e.category == "verdict"
    assert e.type == "dimension_verdict_reached"


def test_final_verdict_reached_defaults():
    e = FinalVerdictReached(result=_sample_result())
    assert e.category == "verdict"
    assert e.type == "final_verdict_reached"
    assert e.result.verdict == "Guilty"


def test_agent_call_retrying_defaults():
    e = AgentCallRetrying(role="prosecutor", attempt=1, max_attempts=3, backoff_seconds=2.0, error="boom")
    assert e.category == "agent"
    assert e.type == "agent_call_retrying"


def test_agent_call_failed_defaults():
    e = AgentCallFailed(role="prosecutor", attempts=3, code="PSALM-A003", error="boom")
    assert e.category == "agent"
    assert e.type == "agent_call_failed"


def test_event_adapter_resolves_correct_subclass_from_dump():
    original = ArgumentRejected(round=1, role="prosecution", argument=_sample_argument(), reason="No proof.")
    restored = EventAdapter.validate_python(original.model_dump())
    assert isinstance(restored, ArgumentRejected)
    assert restored.reason == "No proof."


def test_event_adapter_resolves_final_verdict_reached():
    original = FinalVerdictReached(result=_sample_result())
    restored = EventAdapter.validate_python(original.model_dump())
    assert isinstance(restored, FinalVerdictReached)
    assert restored.result.verdict == "Guilty"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/events/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'psalm.events.types'`

- [ ] **Step 3: Implement `psalm/events/types.py`**

```python
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, TypeAdapter

from psalm.events.base import PSALMEvent
from psalm.models.evidence import Argument
from psalm.models.result import DimensionScore, PSALMResult

# --- lifecycle ---


class RunStarted(PSALMEvent):
    category: Literal["lifecycle"] = "lifecycle"
    type: Literal["run_started"] = "run_started"
    dimensions: list[str]
    evaluation_strategy: str
    source_length: int
    target_length: int


class RunFailed(PSALMEvent):
    category: Literal["lifecycle"] = "lifecycle"
    type: Literal["run_failed"] = "run_failed"
    code: str
    message: str
    context: dict = Field(default_factory=dict)


class DimensionStarted(PSALMEvent):
    category: Literal["lifecycle"] = "lifecycle"
    type: Literal["dimension_started"] = "dimension_started"
    dimension_type: str
    importance: str


# --- argumentation ---


class ArgumentationRoundStarted(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argumentation_round_started"] = "argumentation_round_started"
    round: int


class ArgumentSubmitted(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argument_submitted"] = "argument_submitted"
    round: int
    role: Literal["prosecution", "defense"]
    kind: Literal["argument", "counter"]
    argument: Argument


class ArgumentValidated(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argument_validated"] = "argument_validated"
    round: int
    role: str
    argument: Argument


class ArgumentRejected(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argument_rejected"] = "argument_rejected"
    round: int
    role: str
    argument: Argument
    reason: str


class ClosingStatementDelivered(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["closing_statement_delivered"] = "closing_statement_delivered"
    round: int
    role: str
    statement: str


class ArgumentationStabilityChecked(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argumentation_stability_checked"] = "argumentation_stability_checked"
    round: int
    stability_detected: bool


class ClosingArgumentDelivered(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["closing_argument_delivered"] = "closing_argument_delivered"
    role: str
    statement: str


class ArgumentBatchCompletenessRetry(PSALMEvent):
    category: Literal["argumentation"] = "argumentation"
    type: Literal["argument_batch_completeness_retry"] = "argument_batch_completeness_retry"
    round: int
    role: str
    attempt: int
    max_attempts: int


# --- deliberation ---


class DeliberationRoundStarted(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["deliberation_round_started"] = "deliberation_round_started"
    round: int


class JurorVoteCast(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["juror_vote_cast"] = "juror_vote_cast"
    round: int
    juror_id: str
    vote: str
    rationale: str
    dimension_scores: list[DimensionScore] = Field(default_factory=list)


class JuryConsensusChecked(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["jury_consensus_checked"] = "jury_consensus_checked"
    round: int
    is_unanimous: bool
    top_verdict: str | None = None


class JuryDiscussionMessage(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["jury_discussion_message"] = "jury_discussion_message"
    round: int
    juror_id: str
    message: str


class VotingStrategyApplied(PSALMEvent):
    category: Literal["deliberation"] = "deliberation"
    type: Literal["voting_strategy_applied"] = "voting_strategy_applied"
    strategy_name: str
    is_tie: bool
    verdict: str | None = None


# --- verdict ---


class DimensionVerdictReached(PSALMEvent):
    category: Literal["verdict"] = "verdict"
    type: Literal["dimension_verdict_reached"] = "dimension_verdict_reached"
    dimension_type: str
    importance: str
    verdict: str
    weighted_score: float


class FinalVerdictReached(PSALMEvent):
    category: Literal["verdict"] = "verdict"
    type: Literal["final_verdict_reached"] = "final_verdict_reached"
    result: PSALMResult


# --- agent ---


class AgentCallRetrying(PSALMEvent):
    category: Literal["agent"] = "agent"
    type: Literal["agent_call_retrying"] = "agent_call_retrying"
    role: str
    attempt: int
    max_attempts: int
    backoff_seconds: float
    error: str


class AgentCallFailed(PSALMEvent):
    category: Literal["agent"] = "agent"
    type: Literal["agent_call_failed"] = "agent_call_failed"
    role: str
    attempts: int
    code: str
    error: str


Event = Annotated[
    Union[
        RunStarted, RunFailed, DimensionStarted,
        ArgumentationRoundStarted, ArgumentSubmitted, ArgumentValidated, ArgumentRejected,
        ClosingStatementDelivered, ArgumentationStabilityChecked, ClosingArgumentDelivered,
        ArgumentBatchCompletenessRetry,
        DeliberationRoundStarted, JurorVoteCast, JuryConsensusChecked, JuryDiscussionMessage,
        VotingStrategyApplied,
        DimensionVerdictReached, FinalVerdictReached,
        AgentCallRetrying, AgentCallFailed,
    ],
    Field(discriminator="type"),
]

EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/events/test_types.py -v`
Expected: PASS (21 tests)

- [ ] **Step 5: Fill in `psalm/events/__init__.py`**

```python
from psalm.events.base import EventSink, PSALMEvent
from psalm.events.context import emit
from psalm.events.types import (
    AgentCallFailed,
    AgentCallRetrying,
    ArgumentBatchCompletenessRetry,
    ArgumentRejected,
    ArgumentSubmitted,
    ArgumentValidated,
    ArgumentationRoundStarted,
    ArgumentationStabilityChecked,
    ClosingArgumentDelivered,
    ClosingStatementDelivered,
    DeliberationRoundStarted,
    DimensionStarted,
    DimensionVerdictReached,
    Event,
    EventAdapter,
    FinalVerdictReached,
    JuryConsensusChecked,
    JuryDiscussionMessage,
    JurorVoteCast,
    RunFailed,
    RunStarted,
    VotingStrategyApplied,
)

__all__ = [
    "PSALMEvent",
    "EventSink",
    "emit",
    "Event",
    "EventAdapter",
    "RunStarted",
    "RunFailed",
    "DimensionStarted",
    "ArgumentationRoundStarted",
    "ArgumentSubmitted",
    "ArgumentValidated",
    "ArgumentRejected",
    "ClosingStatementDelivered",
    "ArgumentationStabilityChecked",
    "ClosingArgumentDelivered",
    "ArgumentBatchCompletenessRetry",
    "DeliberationRoundStarted",
    "JurorVoteCast",
    "JuryConsensusChecked",
    "JuryDiscussionMessage",
    "VotingStrategyApplied",
    "DimensionVerdictReached",
    "FinalVerdictReached",
    "AgentCallRetrying",
    "AgentCallFailed",
]
```

- [ ] **Step 6: Run the full events test directory to confirm nothing broke**

Run: `pytest tests/unit/events/ -v`
Expected: PASS (26 tests)

- [ ] **Step 7: Commit**

```bash
git add psalm/events/
git commit -m "feat: add concrete event types and discriminated union"
```

---

### Task 3: Instrument `ArgumentationPhase`

**Files:**
- Modify: `psalm/phases/argumentation.py`
- Modify: `tests/unit/phases/test_argumentation_phase.py`

**Interfaces:**
- Consumes: `emit` and event types from `psalm.events` (Task 2); `bound_event_sink`/`drain_events` from `tests.conftest` (Task 1).
- Produces: no new public interface — `ArgumentationPhase.run()` signature and `ArgumentationLog` output are unchanged; this task only adds `emit()` calls at existing decision points.

- [ ] **Step 1: Write failing tests for round-start and argument-submitted events**

Append to `tests/unit/phases/test_argumentation_phase.py`:

```python
from tests.conftest import bound_event_sink, drain_events


async def test_prosecution_argue_emits_round_started_and_argument_submitted(argumentation_phase, case_input):
    from psalm.events.types import ArgumentationRoundStarted, ArgumentSubmitted

    with bound_event_sink() as sink:
        await argumentation_phase.run(case_input)
        events = await drain_events(sink)

    round_started = [e for e in events if isinstance(e, ArgumentationRoundStarted)]
    submitted = [e for e in events if isinstance(e, ArgumentSubmitted)]
    assert len(round_started) >= 1
    assert round_started[0].round == 1
    assert any(e.role == "prosecution" and e.kind == "argument" for e in submitted)
    assert any(e.role == "defense" and e.kind == "counter" for e in submitted)
    assert any(e.role == "defense" and e.kind == "argument" for e in submitted)
    assert any(e.role == "prosecution" and e.kind == "counter" for e in submitted)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/phases/test_argumentation_phase.py::test_prosecution_argue_emits_round_started_and_argument_submitted -v`
Expected: FAIL — assertion error (no events collected, since nothing emits yet)

- [ ] **Step 3: Add imports and instrument the four argue/counter step handlers**

In `psalm/phases/argumentation.py`, add to the imports:

```python
from psalm.events import (
    ArgumentBatchCompletenessRetry,
    ArgumentRejected,
    ArgumentSubmitted,
    ArgumentValidated,
    ArgumentationRoundStarted,
    ArgumentationStabilityChecked,
    ClosingArgumentDelivered,
    ClosingStatementDelivered,
    emit,
)
```

Replace `_prosecution_argue`:

```python
    async def _prosecution_argue(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        await emit(ArgumentationRoundStarted(round=round_num))
        prior_defense = list(state.defense_arguments) or None
        batch = await self._call_with_completeness_retry(
            lambda hint: self._prosecutor.gather_arguments(
                source_text=state.source_text,
                target_text=state.target_text,
                dimensions=state.dimensions,
                round=round_num,
                prior_defense_arguments=prior_defense,
                retry_hint=hint,
            ),
            role="prosecution",
            round=round_num,
        )
        for arg in batch.arguments:
            await emit(ArgumentSubmitted(round=round_num, role="prosecution", kind="argument", argument=arg))
        if batch.closing_statement:
            await emit(ClosingStatementDelivered(round=round_num, role="prosecution", statement=batch.closing_statement))
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_prosecution_arguments": [a.model_dump() for a in batch.arguments],
            "prosecution_closing_statements": state.prosecution_closing_statements + closing,
        }
```

Replace `_defense_counter`:

```python
    async def _defense_counter(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        prosecution_args = [Argument(**a) for a in state.validated_prosecution_arguments]
        batch = await self._call_with_completeness_retry(
            lambda hint: self._defense.gather_counter_arguments(
                source_text=state.source_text,
                target_text=state.target_text,
                dimensions=state.dimensions,
                prosecutor_arguments=prosecution_args,
                round=round_num,
                retry_hint=hint,
            ),
            role="defense",
            round=round_num,
        )
        for arg in batch.arguments:
            await emit(ArgumentSubmitted(round=round_num, role="defense", kind="counter", argument=arg))
        if batch.closing_statement:
            await emit(ClosingStatementDelivered(round=round_num, role="defense", statement=batch.closing_statement))
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_defense_counters": [a.model_dump() for a in batch.arguments],
            "defense_counter_closing_statements": (
                state.defense_counter_closing_statements + closing
            ),
        }
```

Replace `_defense_argue`:

```python
    async def _defense_argue(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        batch = await self._call_with_completeness_retry(
            lambda hint: self._defense.gather_arguments(
                source_text=state.source_text,
                target_text=state.target_text,
                dimensions=state.dimensions,
                round=round_num,
                retry_hint=hint,
            ),
            role="defense",
            round=round_num,
        )
        for arg in batch.arguments:
            await emit(ArgumentSubmitted(round=round_num, role="defense", kind="argument", argument=arg))
        if batch.closing_statement:
            await emit(ClosingStatementDelivered(round=round_num, role="defense", statement=batch.closing_statement))
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_defense_arguments": [a.model_dump() for a in batch.arguments],
            "defense_closing_statements": state.defense_closing_statements + closing,
        }
```

Replace `_prosecution_counter`:

```python
    async def _prosecution_counter(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        defense_args = [Argument(**a) for a in state.validated_defense_arguments]
        batch = await self._call_with_completeness_retry(
            lambda hint: self._prosecutor.gather_counter_arguments(
                source_text=state.source_text,
                target_text=state.target_text,
                dimensions=state.dimensions,
                defense_arguments=defense_args,
                round=round_num,
                retry_hint=hint,
            ),
            role="prosecution",
            round=round_num,
        )
        for arg in batch.arguments:
            await emit(ArgumentSubmitted(round=round_num, role="prosecution", kind="counter", argument=arg))
        if batch.closing_statement:
            await emit(ClosingStatementDelivered(round=round_num, role="prosecution", statement=batch.closing_statement))
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_prosecution_counters": [a.model_dump() for a in batch.arguments],
            "prosecution_counter_closing_statements": (
                state.prosecution_counter_closing_statements + closing
            ),
        }
```

- [ ] **Step 4: Update `_call_with_completeness_retry` to accept `role`/`round` and emit retry events**

Replace `_call_with_completeness_retry`:

```python
    async def _call_with_completeness_retry(
        self,
        call: Callable[[str | None], Awaitable[ArgumentBatch]],
        *,
        role: str,
        round: int,
    ) -> ArgumentBatch:
        hint: str | None = None
        max_attempts = _COMPLETENESS_RETRY_ATTEMPTS + 1
        for attempt in range(max_attempts):
            batch = await call(hint)
            if await self._judge.validate_batch_completeness(batch):
                return batch
            await emit(ArgumentBatchCompletenessRetry(
                round=round, role=role, attempt=attempt + 1, max_attempts=max_attempts,
            ))
            hint = _COMPLETENESS_RETRY_HINT
        raise PSALMAgentError(
            code="PSALM-A004",
            message=(
                "Agent failed to provide arguments or declare no_further_arguments "
                "after retries."
            ),
            context={"attempts": max_attempts},
            suggestion="Check the LLM model's instruction-following reliability.",
        )
```

- [ ] **Step 5: Run the round-started/argument-submitted test to verify it passes**

Run: `pytest tests/unit/phases/test_argumentation_phase.py::test_prosecution_argue_emits_round_started_and_argument_submitted -v`
Expected: PASS

- [ ] **Step 6: Run the full argumentation unit and integration suites to confirm nothing broke**

Run: `pytest tests/unit/phases/test_argumentation_phase.py tests/integration/test_argumentation_phase.py -v`
Expected: PASS (all existing + 1 new test)

- [ ] **Step 7: Write failing tests for judge-validation events**

Append to `tests/unit/phases/test_argumentation_phase.py`:

```python
async def test_judge_validate_emits_argument_validated(argumentation_phase, case_input):
    from psalm.events.types import ArgumentValidated

    with bound_event_sink() as sink:
        await argumentation_phase.run(case_input)
        events = await drain_events(sink)

    validated = [e for e in events if isinstance(e, ArgumentValidated)]
    assert any(e.role == "prosecution" for e in validated)
    assert any(e.role == "defense" for e in validated)


async def test_judge_validate_emits_argument_rejected(mock_prosecutor, mock_defense, mock_judge, case_input):
    from psalm.events.types import ArgumentRejected

    mock_judge.validate_argument = AsyncMock(
        return_value=MagicMock(is_valid=False, rejection_reason="No excerpts.")
    )
    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)

    with bound_event_sink() as sink:
        await phase.run(case_input)
        events = await drain_events(sink)

    rejected = [e for e in events if isinstance(e, ArgumentRejected)]
    assert len(rejected) >= 1
    assert rejected[0].reason == "No excerpts."
    assert rejected[0].role in {"prosecution", "defense"}
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `pytest tests/unit/phases/test_argumentation_phase.py::test_judge_validate_emits_argument_validated tests/unit/phases/test_argumentation_phase.py::test_judge_validate_emits_argument_rejected -v`
Expected: FAIL — no `ArgumentValidated`/`ArgumentRejected` events collected

- [ ] **Step 9: Instrument the four judge-validation step handlers**

Replace `_judge_validate_prosecution`:

```python
    async def _judge_validate_prosecution(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_prosecution_arguments]
        valid = []
        rejected = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg.model_dump())
                await emit(ArgumentValidated(round=arg.round, role="prosecution", argument=arg))
            else:
                rejected.append(_rejected_entry(arg, result.rejection_reason))
                await emit(ArgumentRejected(
                    round=arg.round, role="prosecution", argument=arg,
                    reason=result.rejection_reason or "No reason provided.",
                ))
        existing = [a.model_dump() for a in state.prosecution_arguments]
        return {
            "validated_prosecution_arguments": valid,
            "prosecution_arguments": existing + valid,
            "prosecution_rejected_arguments": state.prosecution_rejected_arguments + rejected,
        }
```

Replace `_judge_validate_defense_counter`:

```python
    async def _judge_validate_defense_counter(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_defense_counters]
        valid = []
        rejected = []
        for arg in pending:
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense"
            )
            if result.is_valid:
                valid.append(arg.model_dump())
                await emit(ArgumentValidated(round=arg.round, role="defense", argument=arg))
            else:
                rejected.append(_rejected_entry(arg, result.rejection_reason))
                await emit(ArgumentRejected(
                    round=arg.round, role="defense", argument=arg,
                    reason=result.rejection_reason or "No reason provided.",
                ))
        existing = [a.model_dump() for a in state.defense_counters]
        return {
            "defense_counters": existing + valid,
            "defense_counter_rejected_arguments": (
                state.defense_counter_rejected_arguments + rejected
            ),
        }
```

Replace `_judge_validate_defense`:

```python
    async def _judge_validate_defense(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_defense_arguments]
        valid = []
        rejected = []
        for arg in pending:
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense"
            )
            if result.is_valid:
                valid.append(arg.model_dump())
                await emit(ArgumentValidated(round=arg.round, role="defense", argument=arg))
            else:
                rejected.append(_rejected_entry(arg, result.rejection_reason))
                await emit(ArgumentRejected(
                    round=arg.round, role="defense", argument=arg,
                    reason=result.rejection_reason or "No reason provided.",
                ))
        existing = [a.model_dump() for a in state.defense_arguments]
        return {
            "validated_defense_arguments": valid,
            "defense_arguments": existing + valid,
            "defense_rejected_arguments": state.defense_rejected_arguments + rejected,
        }
```

Replace `_judge_validate_prosecution_counter`:

```python
    async def _judge_validate_prosecution_counter(
        self, state: ArgumentationState
    ) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_prosecution_counters]
        valid = []
        rejected = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg.model_dump())
                await emit(ArgumentValidated(round=arg.round, role="prosecution", argument=arg))
            else:
                rejected.append(_rejected_entry(arg, result.rejection_reason))
                await emit(ArgumentRejected(
                    round=arg.round, role="prosecution", argument=arg,
                    reason=result.rejection_reason or "No reason provided.",
                ))
        existing = [a.model_dump() for a in state.prosecution_counters]
        return {
            "prosecution_counters": existing + valid,
            "prosecution_counter_rejected_arguments": (
                state.prosecution_counter_rejected_arguments + rejected
            ),
        }
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `pytest tests/unit/phases/test_argumentation_phase.py -v -k "validated or rejected"`
Expected: PASS (2 new tests, plus the pre-existing `test_rejected_arguments_recorded_with_reason`)

- [ ] **Step 11: Write failing tests for stability, closing argument, and completeness-retry events**

Append to `tests/unit/phases/test_argumentation_phase.py`:

```python
async def test_check_next_round_emits_stability_checked(mock_prosecutor, mock_defense, mock_judge, case_input):
    from psalm.events.types import ArgumentationStabilityChecked

    mock_judge.detect_stability = AsyncMock(return_value=True)
    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=5, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)

    with bound_event_sink() as sink:
        await phase.run(case_input)
        events = await drain_events(sink)

    checked = [e for e in events if isinstance(e, ArgumentationStabilityChecked)]
    assert len(checked) == 1
    assert checked[0].round == 1
    assert checked[0].stability_detected is True


async def test_closing_arguments_emit_closing_argument_delivered(argumentation_phase, case_input):
    from psalm.events.types import ClosingArgumentDelivered

    with bound_event_sink() as sink:
        await argumentation_phase.run(case_input)
        events = await drain_events(sink)

    delivered = [e for e in events if isinstance(e, ClosingArgumentDelivered)]
    assert any(e.role == "prosecution" and e.statement == "Prosecution closing argument." for e in delivered)
    assert any(e.role == "defense" and e.statement == "Defense closing argument." for e in delivered)


async def test_completeness_retry_emits_argument_batch_completeness_retry(mock_judge):
    from psalm.events.types import ArgumentBatchCompletenessRetry

    call_count = 0

    async def ambiguous_then_valid(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ArgumentBatch()
        return _make_batch([_make_arg(role="prosecutor")])

    completeness_calls = 0

    async def completeness_side_effect(batch):
        nonlocal completeness_calls
        completeness_calls += 1
        return completeness_calls > 1

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=ambiguous_then_valid)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.deliver_closing_argument = AsyncMock(return_value="Prosecution closing argument.")
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.deliver_closing_argument = AsyncMock(return_value="Defense closing argument.")
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)
    mock_judge.validate_batch_completeness = AsyncMock(side_effect=completeness_side_effect)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with bound_event_sink() as sink:
        await phase.run(case_input)
        events = await drain_events(sink)

    retries = [e for e in events if isinstance(e, ArgumentBatchCompletenessRetry)]
    assert len(retries) == 1
    assert retries[0].role == "prosecution"
    assert retries[0].attempt == 1
    assert retries[0].max_attempts == 3
```

- [ ] **Step 12: Run tests to verify they fail**

Run: `pytest tests/unit/phases/test_argumentation_phase.py -v -k "stability_checked or closing_argument_delivered or completeness_retry_emits"`
Expected: FAIL — no matching events collected

- [ ] **Step 13: Instrument `_check_next_round` and the two closing-argument handlers**

Replace `_check_next_round`:

```python
    async def _check_next_round(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        pros_this_round = [a for a in state.prosecution_arguments if a.round == round_num]
        def_counters_this_round = [a for a in state.defense_counters if a.round == round_num]
        def_this_round = [a for a in state.defense_arguments if a.round == round_num]
        pros_counters_this_round = [a for a in state.prosecution_counters if a.round == round_num]
        both_empty = (
            len(pros_this_round) == 0
            and len(def_counters_this_round) == 0
            and len(def_this_round) == 0
            and len(pros_counters_this_round) == 0
        )
        stability = await self._judge.detect_stability(
            [Argument(**a) for a in state.validated_prosecution_arguments],
            [a for a in state.prosecution_arguments if a.round == state.current_round],
        )
        decision = stability or both_empty
        await emit(ArgumentationStabilityChecked(round=round_num, stability_detected=decision))
        return {
            "current_round": state.current_round + 1,
            "stability_detected": decision,
        }
```

Replace `_prosecution_closing_argument`:

```python
    async def _prosecution_closing_argument(self, state: ArgumentationState) -> dict[str, Any]:
        statement = await self._prosecutor.deliver_closing_argument(
            dimensions=state.dimensions,
            prosecution_arguments=state.prosecution_arguments,
            prosecution_counters=state.prosecution_counters,
            defense_counters=state.defense_counters,
            defense_arguments=state.defense_arguments,
        )
        await emit(ClosingArgumentDelivered(role="prosecution", statement=statement))
        return {"prosecution_closing_argument": statement}
```

Replace `_defense_closing_argument`:

```python
    async def _defense_closing_argument(self, state: ArgumentationState) -> dict[str, Any]:
        statement = await self._defense.deliver_closing_argument(
            dimensions=state.dimensions,
            defense_counters=state.defense_counters,
            defense_arguments=state.defense_arguments,
            prosecution_arguments=state.prosecution_arguments,
            prosecution_counters=state.prosecution_counters,
        )
        await emit(ClosingArgumentDelivered(role="defense", statement=statement))
        return {"defense_closing_argument": statement}
```

- [ ] **Step 14: Run tests to verify they pass**

Run: `pytest tests/unit/phases/test_argumentation_phase.py -v -k "stability_checked or closing_argument_delivered or completeness_retry_emits"`
Expected: PASS (3 tests)

- [ ] **Step 15: Run the full argumentation-phase test suites**

Run: `pytest tests/unit/phases/test_argumentation_phase.py tests/integration/test_argumentation_phase.py -v`
Expected: PASS (all existing tests + 6 new event tests)

- [ ] **Step 16: Commit**

```bash
git add psalm/phases/argumentation.py tests/unit/phases/test_argumentation_phase.py
git commit -m "feat: emit realtime events from ArgumentationPhase node handlers"
```

---

### Task 4: Instrument `DeliberationPhase`

**Files:**
- Modify: `psalm/phases/deliberation.py`
- Modify: `tests/unit/phases/test_deliberation_phase.py`

**Interfaces:**
- Consumes: `emit` and event types from `psalm.events` (Task 2); `bound_event_sink`/`drain_events` from `tests.conftest` (Task 1).
- Produces: no new public interface — `DeliberationPhase.run()` signature and return type are unchanged.

- [ ] **Step 1: Write failing tests for round-started and vote-cast events**

Append to `tests/unit/phases/test_deliberation_phase.py`:

```python
from tests.conftest import bound_event_sink, drain_events


async def test_jury_vote_emits_round_started_and_vote_cast(deliberation_phase, minimal_argumentation_log):
    from psalm.events.types import DeliberationRoundStarted, JurorVoteCast

    state = DeliberationState(
        argumentation_log=minimal_argumentation_log, max_rounds=2, current_dimension=CHARACTER,
    )
    with bound_event_sink() as sink:
        await deliberation_phase._jury_vote(state)
        events = await drain_events(sink)

    round_started = [e for e in events if isinstance(e, DeliberationRoundStarted)]
    votes_cast = [e for e in events if isinstance(e, JurorVoteCast)]
    assert len(round_started) == 1
    assert round_started[0].round == 1
    assert len(votes_cast) == 1
    assert votes_cast[0].juror_id == "juror-0"
    assert votes_cast[0].vote == "Guilty"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/phases/test_deliberation_phase.py::test_jury_vote_emits_round_started_and_vote_cast -v`
Expected: FAIL — no events collected

- [ ] **Step 3: Add imports and instrument `_jury_vote`**

In `psalm/phases/deliberation.py`, add to the imports:

```python
from psalm.events import (
    DeliberationRoundStarted,
    JuryConsensusChecked,
    JuryDiscussionMessage,
    JurorVoteCast,
    VotingStrategyApplied,
    emit,
)
```

Replace `_jury_vote`:

```python
    async def _jury_vote(self, state: DeliberationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        await emit(DeliberationRoundStarted(round=round_num))
        vote_tasks = [
            juror.vote(
                argumentation_log=state.argumentation_log,
                previous_rounds=state.vote_history,
                discussion_messages=state.discussion_messages,
                round=round_num,
                dimension=state.current_dimension,
            )
            for juror in self._jury
        ]
        votes: list[JurorVote] = await asyncio.gather(*vote_tasks)
        for v in votes:
            await emit(JurorVoteCast(
                round=round_num, juror_id=v.juror_id, vote=v.vote, rationale=v.rationale,
                dimension_scores=v.dimension_scores,
            ))
        return {"current_round_votes": [v.model_dump() for v in votes]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/phases/test_deliberation_phase.py::test_jury_vote_emits_round_started_and_vote_cast -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for consensus-checked, discussion-message, and voting-strategy-applied events**

Append to `tests/unit/phases/test_deliberation_phase.py`:

```python
async def test_check_consensus_emits_jury_consensus_checked(deliberation_phase, minimal_argumentation_log):
    from psalm.events.types import JuryConsensusChecked

    state = DeliberationState(
        argumentation_log=minimal_argumentation_log, max_rounds=2, current_dimension=CHARACTER,
        current_round=1,
        vote_history=[{
            "round": 1, "votes": [], "discussion_messages": [],
            "is_unanimous": True, "top_verdict": "Guilty",
        }],
    )
    with bound_event_sink() as sink:
        await deliberation_phase._check_consensus(state)
        events = await drain_events(sink)

    checked = [e for e in events if isinstance(e, JuryConsensusChecked)]
    assert len(checked) == 1
    assert checked[0].is_unanimous is True
    assert checked[0].top_verdict == "Guilty"


async def test_jury_discussion_emits_discussion_message(deliberation_phase, minimal_argumentation_log):
    from psalm.events.types import JuryDiscussionMessage

    state = DeliberationState(
        argumentation_log=minimal_argumentation_log, max_rounds=2, current_dimension=CHARACTER,
    )
    with bound_event_sink() as sink:
        await deliberation_phase._jury_discussion(state)
        events = await drain_events(sink)

    messages = [e for e in events if isinstance(e, JuryDiscussionMessage)]
    assert len(messages) == 1
    assert messages[0].juror_id == "juror-0"
    assert isinstance(messages[0].message, str)


async def test_apply_voting_strategy_emits_voting_strategy_applied(
    mock_juror, mock_judge, mock_voting_strategy, minimal_argumentation_log
):
    from psalm.events.types import VotingStrategyApplied

    phase = DeliberationPhase(
        jury=[mock_juror], voting_strategies=[mock_voting_strategy], judge=mock_judge, config=DebateConfig(),
    )
    state = DeliberationState(
        argumentation_log=minimal_argumentation_log, max_rounds=1, current_dimension=CHARACTER,
        vote_history=[{
            "round": 1,
            "votes": [{
                "juror_id": "juror-0", "vote": "Guilty", "rationale": "r",
                "dimension_scores": [], "dimension": None,
            }],
            "discussion_messages": [], "is_unanimous": False, "top_verdict": None,
        }],
    )
    with bound_event_sink() as sink:
        await phase._apply_voting_strategy(state)
        events = await drain_events(sink)

    applied = [e for e in events if isinstance(e, VotingStrategyApplied)]
    assert len(applied) == 1
    assert applied[0].is_tie is False
    assert applied[0].verdict == "Guilty"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/unit/phases/test_deliberation_phase.py -v -k "consensus_checked or discussion_message or voting_strategy_applied"`
Expected: FAIL — no matching events collected

- [ ] **Step 7: Instrument `_check_consensus`, `_jury_discussion`, `_apply_voting_strategy`**

Replace `_check_consensus`:

```python
    async def _check_consensus(self, state: DeliberationState) -> dict[str, Any]:
        last_round = state.vote_history[-1] if state.vote_history else {}
        is_unanimous = last_round.get("is_unanimous", False)
        top_verdict = last_round.get("top_verdict")
        await emit(JuryConsensusChecked(
            round=state.current_round, is_unanimous=is_unanimous, top_verdict=top_verdict,
        ))
        if is_unanimous:
            return {"consensus_reached": True, "final_verdict": last_round["top_verdict"]}
        return {"consensus_reached": False}
```

Replace `_jury_discussion`:

```python
    async def _jury_discussion(self, state: DeliberationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        discussion: list[dict[str, str]] = []
        for juror in self._jury:
            message = await juror.discuss(
                argumentation_log=state.argumentation_log,
                previous_rounds=state.vote_history,
                current_discussion=discussion,
                round=round_num,
            )
            discussion.append({"juror_id": juror.juror_id, "message": message})
            await emit(JuryDiscussionMessage(round=round_num, juror_id=juror.juror_id, message=message))
        return {"discussion_messages": discussion}
```

Replace `_apply_voting_strategy`:

```python
    async def _apply_voting_strategy(self, state: DeliberationState) -> dict[str, Any]:
        latest_votes = [JurorVote(**v) for v in state.vote_history[-1]["votes"]]
        for strategy in self._voting_strategies:
            result = await strategy.apply(latest_votes, self._judge, state.argumentation_log)
            await emit(VotingStrategyApplied(
                strategy_name=type(strategy).__name__, is_tie=result.is_tie, verdict=result.verdict,
            ))
            if not result.is_tie:
                return {
                    "final_verdict": result.verdict,
                    "voting_strategy_applied": type(strategy).__name__,
                }
        return {"final_verdict": "Undecided", "voting_strategy_applied": "fallback"}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/unit/phases/test_deliberation_phase.py -v -k "consensus_checked or discussion_message or voting_strategy_applied"`
Expected: PASS (3 tests)

- [ ] **Step 9: Run the full deliberation-phase test suites**

Run: `pytest tests/unit/phases/test_deliberation_phase.py tests/integration/test_deliberation_phase.py -v`
Expected: PASS (all existing tests + 4 new event tests)

- [ ] **Step 10: Commit**

```bash
git add psalm/phases/deliberation.py tests/unit/phases/test_deliberation_phase.py
git commit -m "feat: emit realtime events from DeliberationPhase node handlers"
```

---

### Task 5: Instrument `BaseAgent` retry/failure paths

**Files:**
- Modify: `psalm/agents/base.py`
- Create: `tests/unit/agents/test_base.py`

**Interfaces:**
- Consumes: `emit`, `AgentCallRetrying`, `AgentCallFailed` from `psalm.events` (Task 2); `bound_event_sink`/`drain_events` from `tests.conftest` (Task 1).
- Produces: no new public interface — `_call_llm`/`_call_structured` signatures and behavior (retry count, backoff, raised exceptions) are unchanged.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/test_base.py`:

```python
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
    test_agent._llm.ainvoke = AsyncMock(side_effect=[Exception("boom"), Exception("boom"), "ok"])

    with bound_event_sink() as sink:
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
    test_agent._llm.ainvoke = AsyncMock(side_effect=Exception("persistent failure"))

    with bound_event_sink() as sink:
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/test_base.py -v`
Expected: FAIL — no `AgentCallRetrying`/`AgentCallFailed` events collected

- [ ] **Step 3: Instrument `_call_llm` and `_call_structured`**

In `psalm/agents/base.py`, add to the imports:

```python
from psalm.events import AgentCallFailed, AgentCallRetrying, emit
```

Replace `_call_llm`:

```python
    async def _call_llm(self, messages: list[Any]) -> Any:
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                return await self._llm.ainvoke(messages)
            except Exception as exc:
                if attempt == _RETRY_ATTEMPTS - 1:
                    await emit(AgentCallFailed(
                        role=self.role, attempts=_RETRY_ATTEMPTS, code="PSALM-A003", error=str(exc),
                    ))
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=f"LLM retry limit reached after {_RETRY_ATTEMPTS} attempts.",
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": _RETRY_ATTEMPTS,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                backoff = _BACKOFF_FACTOR**attempt
                await emit(AgentCallRetrying(
                    role=self.role, attempt=attempt + 1, max_attempts=_RETRY_ATTEMPTS,
                    backoff_seconds=backoff, error=str(exc),
                ))
                await asyncio.sleep(backoff)
        raise RuntimeError("unreachable")
```

Replace `_call_structured`:

```python
    async def _call_structured(self, structured_llm: Any, messages: list[Any]) -> Any:
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                return await structured_llm.ainvoke(messages)
            except Exception as exc:
                if attempt == _RETRY_ATTEMPTS - 1:
                    await emit(AgentCallFailed(
                        role=self.role, attempts=_RETRY_ATTEMPTS, code="PSALM-A003", error=str(exc),
                    ))
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=(
                            f"Structured LLM retry limit reached after {_RETRY_ATTEMPTS} attempts."
                        ),
                        context={
                            "role": self.role,
                            "model": self._config.model,
                            "attempts": _RETRY_ATTEMPTS,
                        },
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                backoff = _BACKOFF_FACTOR**attempt
                await emit(AgentCallRetrying(
                    role=self.role, attempt=attempt + 1, max_attempts=_RETRY_ATTEMPTS,
                    backoff_seconds=backoff, error=str(exc),
                ))
                await asyncio.sleep(backoff)
        raise RuntimeError("unreachable")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/agents/test_base.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full agents test suite to confirm nothing broke**

Run: `pytest tests/unit/agents/ -v`
Expected: PASS (all existing tests + 3 new)

- [ ] **Step 6: Commit**

```bash
git add psalm/agents/base.py tests/unit/agents/test_base.py
git commit -m "feat: emit realtime retry/failure events from BaseAgent"
```

---

### Task 6: Instrument `DefaultCourtroom` — dimension tagging and verdict events

**Files:**
- Modify: `psalm/courtroom/default.py`
- Create: `tests/unit/courtroom/test_events.py`

**Interfaces:**
- Consumes: `emit`, `DimensionStarted`, `DimensionVerdictReached`, `FinalVerdictReached` from `psalm.events` (Task 2); `_current_dimension` from `psalm.events.context` (Task 1); `bound_event_sink`/`drain_events` from `tests.conftest` (Task 1).
- Produces: no new public interface — `DefaultCourtroom.run()` signature and `PSALMResult` output are unchanged.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/courtroom/test_events.py`:

```python
from unittest.mock import AsyncMock

import pytest

from psalm.courtroom.default import DefaultCourtroom
from psalm.dimensions import CHARACTER
from psalm.events.types import DimensionStarted, DimensionVerdictReached, FinalVerdictReached
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.result import ArgumentationLog, DebateLog, RoundArguments
from tests.conftest import bound_event_sink, drain_events


@pytest.fixture
def mock_argumentation_phase():
    phase = AsyncMock()
    phase.run = AsyncMock(return_value=ArgumentationLog(rounds=[
        RoundArguments(
            round=1, prosecution_arguments=[], defense_counters=[],
            defense_arguments=[], prosecution_counters=[],
        ),
    ]))
    return phase


@pytest.fixture
def mock_deliberation_phase():
    phase = AsyncMock()
    phase.run = AsyncMock(return_value=(
        "Guilty", DebateLog(rounds=[], final_voting_strategy_applied="unanimous"), 0.8,
    ))
    return phase


async def test_run_single_dimension_emits_dimension_lifecycle_events(
    mock_argumentation_phase, mock_deliberation_phase
):
    config = DebateConfig(dimensions=[CHARACTER])
    courtroom = DefaultCourtroom(mock_argumentation_phase, [mock_deliberation_phase], config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with bound_event_sink() as sink:
        await courtroom.run(case_input)
        events = await drain_events(sink)

    started = [e for e in events if isinstance(e, DimensionStarted)]
    reached = [e for e in events if isinstance(e, DimensionVerdictReached)]
    final = [e for e in events if isinstance(e, FinalVerdictReached)]
    assert len(started) == 1
    assert started[0].dimension == "character"
    assert started[0].dimension_type == "infringement"
    assert len(reached) == 1
    assert reached[0].dimension == "character"
    assert reached[0].verdict == "Guilty"
    assert len(final) == 1


async def test_final_verdict_reached_carries_full_result(mock_argumentation_phase, mock_deliberation_phase):
    config = DebateConfig(dimensions=[CHARACTER])
    courtroom = DefaultCourtroom(mock_argumentation_phase, [mock_deliberation_phase], config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with bound_event_sink() as sink:
        result = await courtroom.run(case_input)
        events = await drain_events(sink)

    final = [e for e in events if isinstance(e, FinalVerdictReached)]
    assert len(final) == 1
    assert final[0].result == result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/courtroom/test_events.py -v`
Expected: FAIL — no events collected

- [ ] **Step 3: Add imports and instrument `_run_single_dimension`, `_deliberate_single`, `run`**

In `psalm/courtroom/default.py`, add to the imports:

```python
from psalm.events import DimensionStarted, DimensionVerdictReached, FinalVerdictReached, emit
from psalm.events.context import _current_dimension
```

Replace `run`:

```python
    async def run(self, case_input: CaseInput) -> PSALMResult:
        start = time.monotonic()
        strategy = self._config.evaluation_strategy

        if strategy == EvaluationStrategy.FULLY_SEPARATE:
            dimension_verdicts = await self._run_fully_separate(case_input)
        elif strategy == EvaluationStrategy.SHARED_ARG_PER_DIM_DELIBERATION:
            dimension_verdicts = await self._run_shared_arg(case_input)
        else:  # SHARED_ALL
            dimension_verdicts = await self._run_shared_all(case_input)

        verdict = _aggregate_verdict(dimension_verdicts, self._config.guilty_threshold)
        rationale = _synthesize_rationale(verdict, dimension_verdicts)
        duration = time.monotonic() - start

        # Dimension verdicts may share the same ArgumentationLog instance (e.g. under
        # SHARED_ARG_PER_DIM_DELIBERATION / SHARED_ALL, one argumentation phase run is
        # reused across all dimensions). Dedup by object identity before summing rounds
        # so shared logs are not counted once per dimension.
        distinct_arg_logs = {
            id(dv.argumentation_log): dv.argumentation_log for dv in dimension_verdicts
        }
        total_arg_rounds = sum(len(log.rounds) for log in distinct_arg_logs.values())
        total_delib_rounds = sum(len(dv.debate_log.rounds) for dv in dimension_verdicts)
        strategy_applied = (
            dimension_verdicts[0].debate_log.final_voting_strategy_applied
            if dimension_verdicts
            else "none"
        )

        metadata = ResultMetadata(
            duration_seconds=round(duration, 3),
            argumentation_rounds_used=total_arg_rounds,
            deliberation_rounds_used=total_delib_rounds,
            voting_strategy_applied=strategy_applied,
        )
        result = PSALMResult(
            verdict=verdict,
            rationale=rationale,
            dimension_verdicts=dimension_verdicts,
            metadata=metadata,
        )
        await emit(FinalVerdictReached(result=result))
        return result
```

Replace `_run_single_dimension`:

```python
    async def _run_single_dimension(
        self,
        dimension: Dimension,
        delib_phase: DeliberationPhase,
        case_input: CaseInput,
    ) -> DimensionVerdict:
        _current_dimension.set(dimension.name)
        await emit(DimensionStarted(
            dimension_type=dimension.dimension_type, importance=dimension.importance.value,
        ))
        if dimension.dimension_type == "infringement":
            exception_dims = [d for d in case_input.dimensions if d.dimension_type == "exception"]
            scoped_dims = [dimension] + exception_dims
        else:
            scoped_dims = [dimension]
        scoped_input = case_input.model_copy(update={"dimensions": scoped_dims})
        arg_log = await self._argumentation_phase.run(scoped_input)
        verdict, debate_log, weighted_score = await delib_phase.run(arg_log, dimension)
        await emit(DimensionVerdictReached(
            dimension_type=dimension.dimension_type, importance=dimension.importance.value,
            verdict=verdict, weighted_score=weighted_score,
        ))
        return DimensionVerdict(
            dimension=dimension.name,
            dimension_type=dimension.dimension_type,
            importance=dimension.importance,
            verdict=verdict,
            weighted_score=weighted_score,
            argumentation_log=arg_log,
            debate_log=debate_log,
        )
```

Replace `_deliberate_single`:

```python
    async def _deliberate_single(
        self,
        dimension: Dimension,
        delib_phase: DeliberationPhase,
        arg_log: ArgumentationLog,
    ) -> DimensionVerdict:
        _current_dimension.set(dimension.name)
        await emit(DimensionStarted(
            dimension_type=dimension.dimension_type, importance=dimension.importance.value,
        ))
        verdict, debate_log, weighted_score = await delib_phase.run(arg_log, dimension)
        await emit(DimensionVerdictReached(
            dimension_type=dimension.dimension_type, importance=dimension.importance.value,
            verdict=verdict, weighted_score=weighted_score,
        ))
        return DimensionVerdict(
            dimension=dimension.name,
            dimension_type=dimension.dimension_type,
            importance=dimension.importance,
            verdict=verdict,
            weighted_score=weighted_score,
            argumentation_log=arg_log,
            debate_log=debate_log,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/courtroom/test_events.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full courtroom and builder test suites to confirm nothing broke**

Run: `pytest tests/unit/courtroom/ tests/unit/test_builder.py -v`
Expected: PASS (all existing tests + 2 new)

- [ ] **Step 6: Commit**

```bash
git add psalm/courtroom/default.py tests/unit/courtroom/test_events.py
git commit -m "feat: emit dimension lifecycle and verdict events from DefaultCourtroom"
```

---

### Task 7: Public API — `astream_evaluate()` and `with_event_listener()`

**Files:**
- Modify: `psalm/builder.py`
- Modify: `psalm/__init__.py`
- Modify: `tests/unit/test_builder.py`

**Interfaces:**
- Consumes: `EventSink`, `emit`, all event types from `psalm.events` (Tasks 1–2); `_current_sink` from `psalm.events.context` (Task 1).
- Produces: `PSALM.with_event_listener(listener: Callable[[PSALMEvent], Any]) -> PSALM`; `_BuiltPSALM.astream_evaluate(source_text: str, target_text: str) -> AsyncIterator[PSALMEvent]`; `_BuiltPSALM._aidentical_texts_result(text: str) -> PSALMResult` (async sibling of the existing `_identical_texts_result`); `_BuiltPSALM.aevaluate()` — same signature and return type, now branches internally when listeners are registered.

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_builder.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_builder.py -v -k "event_listener or astream_evaluate"`
Expected: FAIL — `AttributeError: 'PSALM' object has no attribute 'with_event_listener'` / `'_BuiltPSALM' object has no attribute 'astream_evaluate'`

- [ ] **Step 3: Implement the builder changes**

In `psalm/builder.py`, add to the imports:

```python
import inspect
from typing import AsyncIterator, Callable
from uuid import uuid4

from psalm.events import EventSink, FinalVerdictReached, PSALMEvent, RunFailed, RunStarted, emit
from psalm.events.context import _current_sink
```

In `PSALM.__init__`, add the listener list:

```python
class PSALM:
    def __init__(self) -> None:
        self._prosecutor_config: AgentConfig | None = None
        self._defense_config: AgentConfig | None = None
        self._judge_config: AgentConfig | None = None
        self._jury_configs: list[AgentConfig] = []
        self._debate_config = DebateConfig()
        self._event_listeners: list[Callable[[PSALMEvent], Any]] = []
```

Add the new builder method (anywhere among the other `with_*` methods, e.g. after `with_evaluation_strategy`):

```python
    def with_event_listener(self, listener: Callable[[PSALMEvent], Any]) -> PSALM:
        self._event_listeners.append(listener)
        return self
```

In `PSALM._assemble`, pass the listeners through:

```python
        courtroom = DefaultCourtroom(arg_phase, deliberation_phases, self._debate_config)
        return _BuiltPSALM(
            courtroom=courtroom,
            debate_config=self._debate_config,
            event_listeners=self._event_listeners,
        )
```

Replace `_BuiltPSALM.__init__`:

```python
class _BuiltPSALM:
    def __init__(
        self,
        courtroom: DefaultCourtroom,
        debate_config: DebateConfig,
        event_listeners: list[Callable[[PSALMEvent], Any]] | None = None,
    ) -> None:
        self._courtroom = courtroom
        self._debate_config = debate_config
        self._event_listeners = event_listeners or []
```

Replace `evaluate` and `aevaluate`:

```python
    def evaluate(self, source_text: str, target_text: str) -> PSALMResult:
        return asyncio.run(self.aevaluate(source_text, target_text))

    async def aevaluate(self, source_text: str, target_text: str) -> PSALMResult:
        if not self._event_listeners:
            self._validate_inputs(source_text, target_text)
            if source_text.strip() == target_text.strip():
                return self._identical_texts_result(source_text)
            case_input = CaseInput(
                source_text=source_text,
                target_text=target_text,
                dimensions=self._debate_config.dimensions,
            )
            return await self._courtroom.run(case_input)

        result: PSALMResult | None = None
        async for event in self.astream_evaluate(source_text, target_text):
            for listener in self._event_listeners:
                outcome = listener(event)
                if inspect.isawaitable(outcome):
                    await outcome
            if isinstance(event, FinalVerdictReached):
                result = event.result
        assert result is not None
        return result

    async def astream_evaluate(
        self, source_text: str, target_text: str
    ) -> AsyncIterator[PSALMEvent]:
        self._validate_inputs(source_text, target_text)
        run_id = str(uuid4())
        sink = EventSink(run_id)

        async def _run() -> PSALMResult:
            _current_sink.set(sink)
            await emit(RunStarted(
                dimensions=[d.name for d in self._debate_config.dimensions],
                evaluation_strategy=self._debate_config.evaluation_strategy.value,
                source_length=len(source_text),
                target_length=len(target_text),
            ))
            if source_text.strip() == target_text.strip():
                return await self._aidentical_texts_result(source_text)
            case_input = CaseInput(
                source_text=source_text,
                target_text=target_text,
                dimensions=self._debate_config.dimensions,
            )
            return await self._courtroom.run(case_input)

        task = asyncio.create_task(_run())
        try:
            while not task.done() or not sink.empty():
                get_task = asyncio.ensure_future(sink.get())
                done, _pending = await asyncio.wait(
                    {task, get_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if get_task in done:
                    yield get_task.result()
                else:
                    get_task.cancel()
            await task
        except Exception as exc:
            code = getattr(exc, "code", "PSALM-UNKNOWN")
            context = getattr(exc, "context", {})
            await sink.put(RunFailed(code=code, message=str(exc), context=context))
            while not sink.empty():
                yield await sink.get()
            raise
```

Add `_aidentical_texts_result` (directly below the existing `_identical_texts_result`):

```python
    async def _aidentical_texts_result(self, text: str) -> PSALMResult:
        from psalm.events import DimensionVerdictReached

        result = self._identical_texts_result(text)
        for dv in result.dimension_verdicts:
            await emit(DimensionVerdictReached(
                dimension_type=dv.dimension_type, importance=dv.importance.value,
                verdict=dv.verdict, weighted_score=dv.weighted_score,
            ))
        await emit(FinalVerdictReached(result=result))
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_builder.py -v`
Expected: PASS (all existing tests + 6 new)

- [ ] **Step 5: Export event types from `psalm/__init__.py`**

Replace the full contents of `psalm/__init__.py`:

```python
from psalm.builder import PSALM
from psalm.dimensions.base import Dimension, Importance, SimilarityScore, SubDimension
from psalm.events import (
    AgentCallFailed,
    AgentCallRetrying,
    ArgumentBatchCompletenessRetry,
    ArgumentRejected,
    ArgumentSubmitted,
    ArgumentValidated,
    ArgumentationRoundStarted,
    ArgumentationStabilityChecked,
    ClosingArgumentDelivered,
    ClosingStatementDelivered,
    DeliberationRoundStarted,
    DimensionStarted,
    DimensionVerdictReached,
    Event,
    FinalVerdictReached,
    JuryConsensusChecked,
    JuryDiscussionMessage,
    JurorVoteCast,
    PSALMEvent,
    RunFailed,
    RunStarted,
    VotingStrategyApplied,
)
from psalm.exceptions import PSALMConfigError, PSALMError, PSALMValidationError
from psalm.models.config import AgentConfig, EvaluationStrategy
from psalm.models.result import DimensionVerdict, PSALMResult

__all__ = [
    "PSALM",
    "AgentConfig",
    "EvaluationStrategy",
    "PSALMResult",
    "DimensionVerdict",
    "PSALMError",
    "PSALMConfigError",
    "PSALMValidationError",
    "Dimension",
    "SubDimension",
    "Importance",
    "SimilarityScore",
    "PSALMEvent",
    "Event",
    "RunStarted",
    "RunFailed",
    "DimensionStarted",
    "ArgumentationRoundStarted",
    "ArgumentSubmitted",
    "ArgumentValidated",
    "ArgumentRejected",
    "ClosingStatementDelivered",
    "ArgumentationStabilityChecked",
    "ClosingArgumentDelivered",
    "ArgumentBatchCompletenessRetry",
    "DeliberationRoundStarted",
    "JurorVoteCast",
    "JuryConsensusChecked",
    "JuryDiscussionMessage",
    "VotingStrategyApplied",
    "DimensionVerdictReached",
    "FinalVerdictReached",
    "AgentCallRetrying",
    "AgentCallFailed",
]
```

- [ ] **Step 6: Run the public-API test suite to confirm exports are correct**

Run: `pytest tests/unit/test_public_api.py -v`
Expected: PASS (existing tests unaffected — none of the newly exported names are among the internal names that test asserts are absent)

- [ ] **Step 7: Run the full unit test suite to confirm no regressions**

Run: `pytest tests/unit/ -v`
Expected: PASS (all tests, no failures)

- [ ] **Step 8: Commit**

```bash
git add psalm/builder.py psalm/__init__.py tests/unit/test_builder.py
git commit -m "feat: add PSALM.with_event_listener() and astream_evaluate() public API"
```

---

### Task 8: Concurrency integration test and e2e parity test

**Files:**
- Create: `tests/integration/test_event_concurrency.py`
- Modify: `tests/e2e/test_full_evaluation.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7 (full public API, full event taxonomy).
- Produces: no new production interface — this task is test-only, verifying the spec's concurrency and parity guarantees end-to-end.

- [ ] **Step 1: Write the concurrency test**

Create `tests/integration/test_event_concurrency.py`:

```python
from unittest.mock import AsyncMock, patch

from psalm import PSALM
from psalm.dimensions import CHARACTER, PLOT
from psalm.events.types import ArgumentSubmitted, DimensionStarted, DimensionVerdictReached
from psalm.models.evidence import Argument, ArgumentBatch, Proof
from psalm.models.result import JurorVote, ValidationResult


def _agent_kwargs():
    return {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o"}


def _jury_configs():
    return [
        {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o", "seed": i}
        for i in range(3)
    ]


def _make_arg_side_effect(role: str):
    async def _side_effect(*, dimensions, **kwargs):
        dim_name = dimensions[0].name
        proof = Proof(source_excerpt="x", target_excerpt="y", relevance="r")
        arg = Argument(
            claim=f"{dim_name}-claim", dimension=dim_name, proofs=[proof],
            agent_role=role, round=kwargs["round"],
        )
        return ArgumentBatch(arguments=[arg])
    return _side_effect


async def test_concurrent_dimensions_events_correctly_tagged():
    no_further = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")

    with (
        patch("psalm.agents.prosecutor.Prosecutor.gather_arguments",
              new=AsyncMock(side_effect=_make_arg_side_effect("prosecutor"))),
        patch("psalm.agents.prosecutor.Prosecutor.gather_counter_arguments", new=AsyncMock(return_value=no_further)),
        patch("psalm.agents.defense.Defense.gather_counter_arguments",
              new=AsyncMock(side_effect=_make_arg_side_effect("defense"))),
        patch("psalm.agents.defense.Defense.gather_arguments", new=AsyncMock(return_value=no_further)),
        patch("psalm.agents.prosecutor.Prosecutor.deliver_closing_argument", new=AsyncMock(return_value="P closing.")),
        patch("psalm.agents.defense.Defense.deliver_closing_argument", new=AsyncMock(return_value="D closing.")),
        patch("psalm.agents.judge.Judge.validate_argument", new=AsyncMock(return_value=ValidationResult(is_valid=True))),
        patch("psalm.agents.judge.Judge.detect_stability", new=AsyncMock(return_value=False)),
        patch("psalm.agents.judge.Judge.validate_batch_completeness", new=AsyncMock(return_value=True)),
        patch("psalm.agents.juror.Juror.discuss", new=AsyncMock(return_value="Discussing.")),
        patch("psalm.agents.juror.Juror.vote", new=AsyncMock(
            return_value=JurorVote(juror_id="juror-0", vote="Guilty", rationale="r"))),
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
    ):
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .with_dimensions([CHARACTER, PLOT])
            .with_debate(argumentation_rounds=1, deliberation_rounds=1, time_limit_seconds=60)
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .build()
        )
        events = [
            e async for e in psalm.astream_evaluate(
                "source text about wizards", "target text about wizards, longer",
            )
        ]

    sequences = [e.sequence for e in events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))

    submitted = [e for e in events if isinstance(e, ArgumentSubmitted)]
    assert len(submitted) > 0
    for e in submitted:
        assert e.dimension == e.argument.dimension

    started = {e.dimension for e in events if isinstance(e, DimensionStarted)}
    reached = {e.dimension for e in events if isinstance(e, DimensionVerdictReached)}
    assert started == {"character", "plot"}
    assert reached == {"character", "plot"}
```

- [ ] **Step 2: Run test to verify it fails or passes for the wrong reason first**

Run: `pytest tests/integration/test_event_concurrency.py -v`
Expected: PASS — this test exercises only code already built in Tasks 1–7; if it fails, it indicates a real defect in dimension tagging to fix before proceeding (this step is verification, not TDD-red, since no new production code is added in this task).

- [ ] **Step 3: Refactor `tests/e2e/test_full_evaluation.py` to extract the shared mock-agent context manager**

Replace the full contents of `tests/e2e/test_full_evaluation.py`:

```python
# tests/e2e/test_full_evaluation.py
import json
import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from psalm import PSALM, PSALMResult
from psalm.dimensions import CHARACTER, PLOT, WORLD_BUILDING
from psalm.models.evidence import Argument, ArgumentBatch, Proof
from psalm.models.result import JurorVote, ValidationResult

CASES_PATH = Path(__file__).parent / "fixtures" / "cases.json"


@pytest.fixture
def cases():
    return json.loads(CASES_PATH.read_text())


def _agent_kwargs():
    return {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o"}


def _jury_configs():
    return [
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model": "gpt-4o",
            "seed": i,
        }
        for i in range(3)
    ]


@contextmanager
def _mock_agents():
    sample_proof = Proof(
        source_excerpt="silver hair that shimmered like moonlight",
        target_excerpt="shimmering silver locks",
        relevance="Both describe the same distinctive silver hair.",
    )
    sample_arg = Argument(
        claim="Characters share silver hair trait.",
        dimension="character",
        proofs=[sample_proof],
        agent_role="prosecutor",
        round=1,
    )
    sample_counter = Argument(
        claim="Silver hair is a generic fantasy trope.",
        dimension="character",
        proofs=[sample_proof],
        agent_role="defense",
        round=1,
    )
    no_further = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further to add.")

    with (
        patch(
            "psalm.agents.prosecutor.Prosecutor.gather_arguments",
            new=AsyncMock(return_value=ArgumentBatch(arguments=[sample_arg])),
        ),
        patch(
            "psalm.agents.prosecutor.Prosecutor.gather_counter_arguments",
            new=AsyncMock(return_value=no_further),
        ),
        patch(
            "psalm.agents.defense.Defense.gather_counter_arguments",
            new=AsyncMock(return_value=ArgumentBatch(arguments=[sample_counter])),
        ),
        patch(
            "psalm.agents.defense.Defense.gather_arguments",
            new=AsyncMock(return_value=no_further),
        ),
        patch(
            "psalm.agents.prosecutor.Prosecutor.deliver_closing_argument",
            new=AsyncMock(return_value="Prosecution closing argument."),
        ),
        patch(
            "psalm.agents.defense.Defense.deliver_closing_argument",
            new=AsyncMock(return_value="Defense closing argument."),
        ),
        patch(
            "psalm.agents.judge.Judge.validate_argument",
            new=AsyncMock(return_value=ValidationResult(is_valid=True)),
        ),
        patch(
            "psalm.agents.judge.Judge.detect_stability",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "psalm.agents.judge.Judge.validate_batch_completeness",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "psalm.agents.juror.Juror.discuss",
            new=AsyncMock(return_value="I believe this infringes."),
        ),
        patch(
            "psalm.agents.juror.Juror.vote",
            new=AsyncMock(
                return_value=JurorVote(
                    juror_id="juror-0", vote="Guilty", rationale="Strong evidence."
                )
            ),
        ),
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
    ):
        yield


@pytest.mark.skipif(
    os.getenv("PSALM_E2E") != "true",
    reason="Set PSALM_E2E=true to run real LLM tests",
)
async def test_e2e_real_llm(cases):
    psalm = await (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_dimensions([CHARACTER, PLOT, WORLD_BUILDING])
        .with_debate(argumentation_rounds=2, deliberation_rounds=2, time_limit_seconds=120)
        .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
        .build()
    )
    for case in cases:
        result = await psalm.aevaluate(source_text=case["source"], target_text=case["target"])
        assert isinstance(result, PSALMResult)
        assert result.verdict in {"Guilty", "Not Guilty", "Undecided"}


async def test_e2e_mock_full_pipeline(cases):
    with _mock_agents():
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .with_dimensions([CHARACTER])
            .with_debate(argumentation_rounds=1, deliberation_rounds=1, time_limit_seconds=60)
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .build()
        )
        result = await psalm.aevaluate(
            source_text=cases[0]["source"],
            target_text=cases[0]["target"],
        )

    assert isinstance(result, PSALMResult)
    assert result.verdict in {"Guilty", "Not Guilty", "Undecided"}
    assert result.rationale
    assert len(result.dimension_verdicts) == 1
    assert len(result.dimension_verdicts[0].argumentation_log.rounds) > 0
    assert len(result.dimension_verdicts[0].debate_log.rounds) > 0
    assert result.metadata.duration_seconds >= 0


async def test_astream_evaluate_matches_aevaluate_result(cases):
    from psalm.events.types import FinalVerdictReached

    with _mock_agents():
        psalm_a = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .with_dimensions([CHARACTER])
            .with_debate(argumentation_rounds=1, deliberation_rounds=1, time_limit_seconds=60)
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .build()
        )
        result_a = await psalm_a.aevaluate(
            source_text=cases[0]["source"], target_text=cases[0]["target"],
        )

        psalm_b = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .with_dimensions([CHARACTER])
            .with_debate(argumentation_rounds=1, deliberation_rounds=1, time_limit_seconds=60)
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .build()
        )
        events = [
            e async for e in psalm_b.astream_evaluate(
                source_text=cases[0]["source"], target_text=cases[0]["target"],
            )
        ]

    final = [e for e in events if isinstance(e, FinalVerdictReached)]
    assert len(final) == 1
    result_b = final[0].result

    assert result_a.verdict == result_b.verdict
    assert result_a.rationale == result_b.rationale
    assert len(result_a.dimension_verdicts) == len(result_b.dimension_verdicts)
    for dv_a, dv_b in zip(result_a.dimension_verdicts, result_b.dimension_verdicts):
        assert dv_a.dimension == dv_b.dimension
        assert dv_a.verdict == dv_b.verdict
        assert dv_a.weighted_score == dv_b.weighted_score


async def test_identical_texts_returns_guilty_immediately():
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .build()
        )
    text = "The wizard had blue eyes."
    result = await psalm.aevaluate(source_text=text, target_text=text)
    assert result.verdict == "Guilty"
    assert result.metadata.argumentation_rounds_used == 0
```

- [ ] **Step 4: Run the e2e suite to verify everything passes**

Run: `pytest tests/e2e/ -v`
Expected: PASS (4 tests run — `test_e2e_real_llm` skipped unless `PSALM_E2E=true`)

- [ ] **Step 5: Run the entire test suite**

Run: `pytest tests/ -v`
Expected: PASS — every test in `tests/unit/`, `tests/integration/`, `tests/e2e/` passes; zero failures, zero regressions.

- [ ] **Step 6: Run ruff to confirm lint cleanliness**

Run: `ruff check psalm/ tests/`
Expected: No errors (fix any `E`/`F`/`I` violations reported — most likely unused-import or import-order issues from the new `psalm.events` imports added across Tasks 3–7)

- [ ] **Step 7: Commit**

```bash
git add tests/integration/test_event_concurrency.py tests/e2e/test_full_evaluation.py
git commit -m "test: add concurrency and astream_evaluate/aevaluate parity coverage"
```

---

## Self-Review

**Spec coverage:**
- §2.1 event envelope/sink/context → Task 1. ✓
- §2.2 `astream_evaluate()` runtime flow → Task 7. ✓
- §2.3 dimension tagging under parallelism → Task 6 (`_current_dimension.set`) + Task 8 (concurrency proof). ✓
- §2.4 terminal event (`FinalVerdictReached`, no `RunCompleted`) → Task 6 + Task 7. ✓
- §2.5 dimension `None` under shared strategies → naturally true since Task 6 only sets `_current_dimension` in `_run_single_dimension`/`_deliberate_single`, never around the shared `_argumentation_phase.run()` call in `_run_shared_arg`/`_run_shared_all` — no extra task needed, verified by existing courtroom tests continuing to pass with `SHARED_ALL`/`SHARED_ARG` config in Task 6/7's regression runs.
- §2.6 identical-texts shortcut → Task 7 (`_aidentical_texts_result`). ✓
- §2.7 abandoned streams → satisfied by construction in Task 7 (`task` is never cancelled by the generator); no dedicated test added since it requires simulating consumer abandonment, which is lower-value than the concurrency/parity tests already covering the stream's correctness — noted here as intentionally out of scope for automated testing, consistent with spec's "best-effort" framing.
- §3 all 19 event types → Task 2 (types) + Tasks 3–7 (emission sites), one test per type across those tasks.
- §4.1 `astream_evaluate()` → Task 7.
- §4.2 `with_event_listener()` → Task 7.
- §4.3 unchanged `.evaluate()`/`.aevaluate()` → Task 7 (regression tests + full suite run in Step 7).
- §5 testing plan → mapped 1:1 to Tasks 1–8's test files.
- §6 no breaking changes → verified by full suite passing at the end of every task from Task 3 onward.
- §7/§8 files table / unchanged list → matches the Files sections of each task.

**Placeholder scan:** No "TBD"/"TODO"/"add error handling" phrases in any step; every code block is complete, runnable code with real assertions.

**Type consistency:** `ArgumentBatchCompletenessRetry`, `AgentCallRetrying`, `AgentCallFailed`, `DimensionStarted`, `DimensionVerdictReached`, `FinalVerdictReached` field names are identical between their Task 2 class definitions and every call site in Tasks 3, 5, 6, 7. `_call_with_completeness_retry`'s new `role`/`round` keyword-only parameters are consistent across all four call sites updated in Task 3 Step 3. `bound_event_sink`/`drain_events` signatures (Task 1) are used identically in Tasks 3, 4, 5, 6, 8.

---

Plan complete and saved to `docs/superpowers/plans/2026-07-12-realtime-event-streaming.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
