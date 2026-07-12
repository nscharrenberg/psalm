# Realtime Event Streaming

**Date**: 2026-07-12
**Author**: Noah Scharrenberg
**Project**: psalm-eu v2
**Scope**: Emit realtime, semantically-meaningful events for every step of a courtroom run (arguments, judge rulings, jury votes/discussion, verdicts, agent retries/failures) so a consumer can observe progress live, instead of only receiving the final `PSALMResult` JSON after the whole run completes.

---

## 1. Overview

Today, `_BuiltPSALM.evaluate()` / `.aevaluate()` run the entire courtroom process (argumentation → deliberation, per dimension, potentially in parallel) opaquely and return one `PSALMResult` at the end. Everything that happens along the way — an argument being submitted, the Judge rejecting it, a juror casting a vote, an LLM call being retried after a transient failure — is only visible afterward, buried in the final result tree.

This spec adds a second, purely additive way to consume a run: a live stream of typed events, one per meaningful step, correctly attributed to the dimension/round/role it came from. `.evaluate()` / `.aevaluate()` are unchanged — same signatures, same return type, no event machinery engaged when nobody asks for it.

**Explicitly out of scope**: two-way control. Consumers can *observe* a run in realtime; they cannot pause it, approve/reject a step, or inject input mid-run. This is a read-only, best-effort broadcast of what's already happening.

---

## 2. Architecture

### 2.1 New package `psalm/events/`

- `psalm/events/context.py` — two `contextvars.ContextVar`s and one public function:

  ```python
  _current_sink: ContextVar[EventSink | None] = ContextVar("_current_sink", default=None)
  _current_dimension: ContextVar[str | None] = ContextVar("_current_dimension", default=None)

  async def emit(event: PSALMEvent) -> None:
      sink = _current_sink.get()
      if sink is None:
          return  # no-op when nobody is streaming — .evaluate()/.aevaluate() pay nothing
      await sink.put(event)
  ```

- `psalm/events/base.py` — the envelope and the sink:

  ```python
  class PSALMEvent(BaseModel):
      event_id: str = Field(default_factory=lambda: str(uuid4()))
      sequence: int = 0            # overwritten by EventSink.put()
      timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
      run_id: str = ""             # overwritten by EventSink.put()
      dimension: str | None = None # filled from _current_dimension if not already set
      category: Literal["lifecycle", "argumentation", "deliberation", "verdict", "agent"]
      type: str

  class EventSink:
      def __init__(self, run_id: str) -> None:
          self.run_id = run_id
          self._queue: asyncio.Queue[PSALMEvent] = asyncio.Queue()
          self._seq = itertools.count(1)

      async def put(self, event: PSALMEvent) -> None:
          await self._queue.put(event.model_copy(update={
              "run_id": self.run_id,
              "sequence": next(self._seq),
              "dimension": event.dimension or _current_dimension.get(),
          }))

      async def get(self) -> PSALMEvent:
          return await self._queue.get()

      def empty(self) -> bool:
          return self._queue.empty()
  ```

  Call sites never set `run_id`/`sequence`/`dimension` themselves — only event-specific fields (`round`, `role`, `argument`, etc.).

- `psalm/events/types.py` — concrete event classes (§3), a `Event` discriminated union on `type`, and `__all__` re-exporting everything from `psalm.events`.

### 2.2 Runtime flow — `astream_evaluate()`

```python
async def astream_evaluate(self, source_text: str, target_text: str) -> AsyncIterator[PSALMEvent]:
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
            return await self._aidentical_texts_result(source_text)  # §2.6 — emits its own shortcut sequence
        case_input = CaseInput(source_text=source_text, target_text=target_text,
                                dimensions=self._debate_config.dimensions)
        return await self._courtroom.run(case_input)  # emits DimensionVerdictReached / FinalVerdictReached itself

    task = asyncio.create_task(_run())
    try:
        while not task.done() or not sink.empty():
            get_task = asyncio.ensure_future(sink.get())
            done, _ = await asyncio.wait({task, get_task}, return_when=asyncio.FIRST_COMPLETED)
            if get_task in done:
                yield get_task.result()
            elif not get_task.done():
                get_task.cancel()
        await task  # surface any exception
    except Exception as exc:
        await emit(RunFailed(code=getattr(exc, "code", "PSALM-UNKNOWN"), message=str(exc)))
        while not sink.empty():
            yield await sink.get()
        raise
```

(Sketch — exact orchestration of the "drain queue while task runs, then drain remainder" loop is an implementation detail for the plan; the contract is: every event emitted during the run is yielded, in emission order, before the generator returns or raises.)

`asyncio.create_task(_run())` captures the current context at creation time, including the `_current_sink.set(sink)` call happening *inside* `_run()` itself (not before `create_task`) — this keeps the binding scoped to this run's task tree only, so two concurrent `astream_evaluate()` calls on the same built `PSALM` never share a sink.

### 2.3 Dimension tagging under parallelism

`DefaultCourtroom._run_single_dimension` (and `_deliberate_single`, used by the other two `EvaluationStrategy` modes) gets one line added at the very top:

```python
async def _run_single_dimension(self, dimension, delib_phase, case_input) -> DimensionVerdict:
    _current_dimension.set(dimension.name)
    await emit(DimensionStarted(dimension_type=dimension.dimension_type, importance=dimension.importance.value))
    ...
```

Because `_run_fully_separate` schedules these via `asyncio.gather`, each becomes its own `Task` with its own copy of the context; `_current_dimension.set(...)` inside one task's coroutine never affects a sibling task evaluating a different dimension concurrently. No dimension parameter needs to be threaded into any deeper method (agents, phase node methods) — they all read the ambient value through `emit()`.

### 2.4 Terminal event

There is no separate `RunCompleted` event. `DefaultCourtroom.run()` emits `FinalVerdictReached` (carrying the full `PSALMResult`) as the last thing it does before returning — that event, drained from the queue like every other, is the stream's natural terminal item. `RunFailed` is the terminal item on the error path instead.

### 2.5 Dimension tag is `None` under shared-argumentation strategies

Under `SHARED_ARG_PER_DIM_DELIBERATION` and `SHARED_ALL`, `_argumentation_phase.run(case_input)` runs once for *all* dimensions together, outside any dimension-scoped task — `_current_dimension` is never set at that point, so every `argumentation`-category event from that shared run carries `dimension=None`. This is correct, not a gap: under those strategies an argument genuinely isn't scoped to one dimension. `deliberation`- and `verdict`-category events are still correctly per-dimension in all three strategies, since `_deliberate_single` (or `_run_single_dimension` under `FULLY_SEPARATE`) always sets `_current_dimension` before running.

### 2.6 Identical-texts shortcut

`_BuiltPSALM._identical_texts_result` (the `source == target` fast path) bypasses `DefaultCourtroom` entirely, so it's the one place outside the courtroom that must emit `DimensionVerdictReached`/`FinalVerdictReached` itself. It gains an async sibling, `_aidentical_texts_result`, used only by `astream_evaluate()`:

```python
async def _aidentical_texts_result(self, text: str) -> PSALMResult:
    result = self._identical_texts_result(text)  # unchanged, still used by plain .evaluate()/.aevaluate()
    for dv in result.dimension_verdicts:
        await emit(DimensionVerdictReached(
            dimension_type=dv.dimension_type, importance=dv.importance.value,
            verdict=dv.verdict, weighted_score=dv.weighted_score,
        ))
    await emit(FinalVerdictReached(result=result))
    return result
```

`_identical_texts_result` itself is untouched — plain `.evaluate()`/`.aevaluate()` keep calling it directly with no emission (§4.3).

### 2.7 Abandoned streams

If a consumer stops iterating early (e.g. a disconnected websocket breaks out of the `async for` loop), the generator's `finally` does **not** cancel `task` — the underlying run keeps executing to completion, same as it would under plain `.evaluate()`. Watching is a side observation, not a control mechanism (§1 scope).

---

## 3. Event taxonomy

All events subclass `PSALMEvent` (§2.1). Grouped by `category`:

### `lifecycle`
| Type | Fields | Fires in |
|---|---|---|
| `RunStarted` | `dimensions: list[str]`, `evaluation_strategy: str`, `source_length: int`, `target_length: int` | `astream_evaluate()`, before dispatch |
| `RunFailed` | `code: str`, `message: str`, `context: dict` | `astream_evaluate()`, on unhandled exception |
| `DimensionStarted` | `dimension_type: str`, `importance: str` | `_run_single_dimension` / `_deliberate_single` (top) |

A dimension's completion is signaled by `DimensionVerdictReached` (§3, `verdict` category) — no separate `DimensionCompleted` event, since it would fire at the same point with no additional information.

### `argumentation` (`ArgumentationPhase`)
| Type | Fields | Fires in |
|---|---|---|
| `ArgumentationRoundStarted` | `round: int` | `_prosecution_argue` (top) |
| `ArgumentSubmitted` | `round: int`, `role: "prosecution"\|"defense"`, `kind: "argument"\|"counter"`, `argument: Argument` | one per `Argument` in `_prosecution_argue`, `_defense_counter`, `_defense_argue`, `_prosecution_counter` |
| `ArgumentValidated` | `round: int`, `role`, `argument: Argument` | per accepted argument in the four `_judge_validate_*` methods |
| `ArgumentRejected` | `round: int`, `role`, `argument: Argument`, `reason: str` | per rejected argument in the four `_judge_validate_*` methods |
| `ClosingStatementDelivered` | `round: int`, `role`, `statement: str` | the four step handlers, when `batch.closing_statement` is set |
| `ArgumentationStabilityChecked` | `round: int`, `stability_detected: bool` | `_check_next_round` |
| `ClosingArgumentDelivered` | `role`, `statement: str` | `_prosecution_closing_argument`, `_defense_closing_argument` |
| `ArgumentBatchCompletenessRetry` | `round: int`, `role`, `attempt: int`, `max_attempts: int` | `_call_with_completeness_retry`, on a failed `validate_batch_completeness` check |

### `deliberation` (`DeliberationPhase`)
| Type | Fields | Fires in |
|---|---|---|
| `DeliberationRoundStarted` | `round: int` | `_jury_vote` (top) |
| `JurorVoteCast` | `round: int`, `juror_id: str`, `vote: str`, `rationale: str`, `dimension_scores: list[DimensionScore]` | `_jury_vote`, per juror as votes resolve |
| `JuryConsensusChecked` | `round: int`, `is_unanimous: bool`, `top_verdict: str \| None` | `_check_consensus` |
| `JuryDiscussionMessage` | `round: int`, `juror_id: str`, `message: str` | `_jury_discussion`, per juror |
| `VotingStrategyApplied` | `strategy_name: str`, `is_tie: bool`, `verdict: str` | `_apply_voting_strategy` |

### `verdict`
| Type | Fields | Fires in |
|---|---|---|
| `DimensionVerdictReached` | `dimension_type: str`, `importance: str`, `verdict: str`, `weighted_score: float` | `_run_single_dimension` / `_deliberate_single`, right after `delib_phase.run()` returns |
| `FinalVerdictReached` | `result: PSALMResult` | `DefaultCourtroom.run()`, immediately before returning |

### `agent`
| Type | Fields | Fires in |
|---|---|---|
| `AgentCallRetrying` | `role: str`, `attempt: int`, `max_attempts: int`, `backoff_seconds: float`, `error: str` | `BaseAgent._call_llm` / `_call_structured`, in the `except` block before `asyncio.sleep` |
| `AgentCallFailed` | `role: str`, `attempts: int`, `code: str`, `error: str` | same two methods, when raising `PSALMAgentError` after retries exhausted |

Every field listed above is *already computed* by existing code today (it ends up in `RejectedArgument`, `JurorVote`, `RoundDeliberation`, etc.) — this spec adds emission of that same data as it's produced, not new computation.

---

## 4. Public API

### 4.1 `_BuiltPSALM.astream_evaluate()`

```python
async def astream_evaluate(self, source_text: str, target_text: str) -> AsyncIterator[PSALMEvent]:
```

```python
async for event in psalm.astream_evaluate(source, target):
    match event:
        case FinalVerdictReached():
            result = event.result   # identical PSALMResult to today's .aevaluate() return value
        case ArgumentRejected():
            ...
```

The identical-texts shortcut (`source == target`) now emits `RunStarted` → one `DimensionVerdictReached` per dimension → `FinalVerdictReached`, instead of silently returning with no events — a stream watcher should never see a run produce nothing.

### 4.2 `PSALM.with_event_listener(callback)`

```python
psalm = await (
    PSALM()
    .with_prosecutor(...).with_defense(...).with_judge(...).with_jury(...)
    .with_event_listener(my_callback)   # sync or async callable; may be called multiple times
    .build()
)
result = await psalm.aevaluate(source, target)   # unchanged signature and return type
```

Implemented as an adapter with one code path underneath: when listeners are registered, `aevaluate()` internally drives `astream_evaluate()` and forwards every event to each listener (`await cb(event)` if a coroutine function, else `cb(event)`), returning `event.result` from the terminal `FinalVerdictReached`. When no listeners are registered, `aevaluate()` calls `self._courtroom.run(case_input)` directly, exactly as it does today — no sink is ever created, so `emit()` no-ops throughout.

### 4.3 Unchanged

`.evaluate()` / `.aevaluate()` with no listeners: identical signature, identical return type, identical behavior to today. This is verified by regression — the full existing test suite must remain green with zero modifications.

---

## 5. Testing

Following the existing `tests/unit` / `tests/integration` / `tests/e2e` structure:

- `tests/unit/events/test_context.py` — `emit()` no-ops with no bound sink; `EventSink.put()` correctly stamps `run_id`/`sequence`/`dimension`.
- `tests/unit/phases/test_argumentation_phase.py`, `test_deliberation_phase.py` — extend existing mocked-agent tests: bind a `FakeSink` (a simple list-collecting `EventSink` subclass or equivalent test double) via `_current_sink`, run a node method, assert the expected event(s) landed with correct fields (e.g. a mocked Judge rejection → exactly one `ArgumentRejected` with the right `reason`).
- `tests/unit/agents/test_*.py` — induce an LLM call failure via mocks, assert `AgentCallRetrying` fires per attempt and `AgentCallFailed` fires once retries are exhausted, matching `_RETRY_ATTEMPTS`.
- `tests/integration/` — new concurrency test: run `EvaluationStrategy.FULLY_SEPARATE` with 2+ dimensions against the existing mock pipeline, assert every event's `dimension` matches its true source with no cross-talk between concurrently-gathered tasks, and that `sequence` is strictly increasing across the whole run.
- `tests/e2e/test_full_evaluation.py` — extend to also drive `astream_evaluate()` end-to-end; assert the `FinalVerdictReached.result` equals what plain `.aevaluate()` returns for the same input (proves both paths stay in sync).
- Full existing suite must pass unmodified (proves §4.3).

---

## 6. Breaking changes

None. This is a purely additive feature — no existing method signature, return type, or behavior changes.

---

## 7. Files added / modified

| File | Change |
|---|---|
| `psalm/events/__init__.py` | New — re-exports `PSALMEvent`, `EventSink`, `emit`, all concrete event types |
| `psalm/events/context.py` | New — `_current_sink`, `_current_dimension`, `emit()` |
| `psalm/events/base.py` | New — `PSALMEvent`, `EventSink` |
| `psalm/events/types.py` | New — all concrete event classes + discriminated union |
| `psalm/phases/argumentation.py` | Add `emit(...)` calls in the 4 step handlers, 4 judge-validation handlers, `_check_next_round`, both closing-argument handlers, `_call_with_completeness_retry` |
| `psalm/phases/deliberation.py` | Add `emit(...)` calls in `_jury_vote`, `_check_consensus`, `_jury_discussion`, `_apply_voting_strategy` |
| `psalm/agents/base.py` | Add `emit(...)` calls in `_call_llm` / `_call_structured` retry and failure paths |
| `psalm/courtroom/default.py` | Add `_current_dimension.set(...)` + `emit(...)` calls in `_run_single_dimension`, `_deliberate_single`, `run()` |
| `psalm/builder.py` | Add `PSALM.with_event_listener()`, `_BuiltPSALM.astream_evaluate()`, `_aidentical_texts_result()` (§2.6); `aevaluate()` branches to the listener-forwarding path when listeners are registered; `_identical_texts_result` itself is unchanged |
| `tests/unit/events/` | New test directory (§5) |
| `tests/integration/test_event_concurrency.py` | New (§5) |
| `tests/e2e/test_full_evaluation.py` | Extended (§5) |

---

## 8. Unchanged

`.evaluate()` / `.aevaluate()` signatures and return types; `PSALMResult` and all existing result models; the `ArgumentationPhase`/`DeliberationPhase` LangGraph graph topology and node logic (only additive `emit()` calls, no control-flow changes); `EvaluationStrategy` modes; voting strategies; the existing (unused) `psalm/communication/` module, which serves a different purpose (inter-agent evidence sharing per the original design doc) and is not reused here.
