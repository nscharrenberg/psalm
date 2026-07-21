# Execution Concurrency & Rate-Limit Configuration — Design

## 1. Overview

Running PSALM with all dimensions selected (10 in the catalog) at the web app's default
jury size (3) fires `dimensions × jurors` = up to 30 simultaneous structured-output LLM
calls per deliberation round, all commonly sharing one API key. `BaseAgent._call_llm`/
`_call_structured` (`psalm/agents/base.py`) retry each call 3× with a fixed, non-jittered
exponential backoff (1s/2s/4s) — under a burst this large, many calls get rate-limited
together, back off on the same schedule, and collide again on retry, exhausting the retry
budget even though the calls would succeed if spread out over time. `PSALM.build()`'s
`_ping_all_llms` (`psalm/builder.py`) has the same unbounded-burst shape (one ping per
agent, all at once) with its own duplicated retry constants. There is currently no
concurrency or rate-limit configuration anywhere in the SDK.

**Goal:** add a single, global, configurable concurrency cap shared across every LLM call
in a run (including the build-time connectivity ping), plus jittered and
user-configurable retry/backoff, and expose the two most actionable knobs
(`max_concurrent_llm_calls`, `max_retries`) in the demo web app's trial config form.

**Deliberately out of scope:** per-provider/per-API-key cap scoping (a single global cap
is sufficient — the common case is one shared provider, and the demo app doesn't exercise
mixed-provider setups); exposing `backoff_factor` in the web UI; respecting
provider-supplied `Retry-After` headers (a reasonable future improvement, not required to
fix the reported failure).

## 2. `ExecutionConfig`

**`psalm/models/config.py` — new model:**
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

`max_retries=3` and `backoff_factor=2.0` match today's hardcoded `_RETRY_ATTEMPTS`/
`_BACKOFF_FACTOR` exactly, so a user who never touches this config sees identical retry
behavior (modulo jitter — see §4). `max_concurrent_llm_calls=8` is new: comfortably above
what a single dimension needs at the web app's default 3 jurors (no slowdown for small
runs), while capping a full 10-dimension run to 8 in-flight calls instead of ~30.

## 3. Builder Surface

**`psalm/builder.py` — `PSALM`:**
- `__init__` gains `self._execution_config: ExecutionConfig = ExecutionConfig()`.
- New method:
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
  Matches the existing builder method pattern (`with_debate`, `with_voting`, etc.) — full
  replacement of the config, not a partial update.

## 4. Runtime Wiring: One Shared Semaphore

`ExecutionConfig` is a plain, serializable Pydantic model — it cannot hold an
`asyncio.Semaphore`. `PSALM.build()` builds the actual runtime object once per build.

This dataclass is defined in `psalm/agents/base.py`, not `psalm/builder.py`, to avoid a
circular import: `builder.py` already imports concrete agent classes from
`psalm.agents.*`, so if the dataclass lived in `builder.py`, `agents/base.py` would need
to import it back from `builder.py` for `BaseAgent.__init__`'s type hint — a cycle.
Defining it in `agents/base.py` (where `BaseAgent` is its primary consumer) and having
`builder.py` import it from there (`from psalm.agents.base import _RunExecution`) follows
the same direction as builder.py's existing agent imports and has no cycle.

**`psalm/agents/base.py` — new internal dataclass, alongside `BaseAgent`:**
```python
@dataclass
class _RunExecution:
    semaphore: asyncio.Semaphore
    max_retries: int
    backoff_factor: float
```

**`psalm/builder.py` — `PSALM.build()`** (file gains `from psalm.agents.base import _RunExecution`):
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

`_ping_all_llms` and `_ping_llm` gain an `execution: _RunExecution` parameter, use
`execution.semaphore`/`execution.max_retries`/`execution.backoff_factor` in place of the
current module-level `_PING_RETRY_ATTEMPTS`/`_PING_BACKOFF_FACTOR` constants (removed —
this also fixes the pre-existing duplication between the ping path's retry logic and
`BaseAgent`'s). `_assemble` gains the same `execution: _RunExecution` parameter and passes
it to every constructed agent: `Prosecutor(config=..., execution=execution)`,
`Defense(config=..., execution=execution)`, `Judge(config=..., execution=execution)`,
`Juror(config=..., juror_id=..., execution=execution)`. Because it is the *same*
`_RunExecution` (and therefore the same `Semaphore`) instance passed everywhere, the cap
is enforced globally across every role and every dimension's deliberation, matching the
single-global-cap decision — not per-agent, per-role, or per-dimension.

**`psalm/agents/base.py` — `BaseAgent`:**
```python
class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, execution: _RunExecution) -> None:
        self._config = config
        self._execution = execution
        self._llm = ChatOpenAI(...)  # unchanged

    async def _call_llm(self, messages: list[Any]) -> Any:
        for attempt in range(self._execution.max_retries):
            try:
                async with self._execution.semaphore:
                    return await self._llm.ainvoke(messages)
            except Exception as exc:
                if attempt == self._execution.max_retries - 1:
                    ...  # unchanged failure path, using self._execution.max_retries
                    raise PSALMAgentError(..., context={..., "attempts": self._execution.max_retries}) from exc
                backoff = self._execution.backoff_factor**attempt
                jittered = random.uniform(0, backoff)
                await emit(AgentCallRetrying(
                    role=self.role, attempt=attempt + 1, max_attempts=self._execution.max_retries,
                    backoff_seconds=jittered, error=str(exc),
                ))
                await asyncio.sleep(jittered)
        raise RuntimeError("unreachable")
```
`_call_structured` gets the identical treatment. The semaphore is acquired **only around
the `ainvoke()` call itself**, not the whole retry loop — it's released before the backoff
sleep, so a failed attempt frees its slot immediately for other pending calls rather than
holding a scarce slot idle during its own wait. `AgentCallRetrying.backoff_seconds` now
reports the actual (jittered) sleep duration, which is more accurate than the previous
un-jittered value.

**`psalm/agents/juror.py` — `Juror.__init__`:**
```python
def __init__(self, config: AgentConfig, juror_id: str, execution: _RunExecution) -> None:
    super().__init__(config, execution)
    self._juror_id = juror_id
```

Prosecutor, Defense, and Judge have no custom `__init__` (they inherit `BaseAgent`'s
directly), so no other agent file changes.

**Jitter algorithm:** full jitter — `random.uniform(0, backoff_factor**attempt)` — rather
than the fixed schedule or a narrower jitter band. This is the standard mitigation for
"many independent clients retry against one shared limit and collide again," which is
exactly this failure mode. It is not exposed as configuration; it's an implementation
detail of the retry mechanism, not a tuning knob a user needs.

**No change to existing `asyncio.gather` call sites.** `DefaultCourtroom._run_fully_separate`
/`_run_shared_arg`/`_run_shared_all` (`psalm/courtroom/default.py`) and
`DeliberationPhase._jury_vote` (`psalm/phases/deliberation.py`) continue to launch every
dimension/juror task concurrently at the Python level — the cap lives one layer deeper, so
only `max_concurrent_llm_calls` of those tasks are ever actually inside a live LLM call at
once; the rest simply await the shared semaphore. This avoids restructuring either gather
site.

## 5. Web App

**`examples/web/backend/schemas.py` — `TrialConfigRequest`:**
```python
class TrialConfigRequest(BaseModel):
    ...  # unchanged fields
    max_concurrent_llm_calls: int = Field(default=8, ge=1)
    max_retries: int = Field(default=3, ge=1)
```
`backoff_factor` is intentionally not added here — SDK-configurable only, not surfaced in
the web app.

**`examples/web/backend/execution.py` — `build_psalm`:**
```python
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
```

**`examples/web/frontend/src/api/types.ts`:** add `max_concurrent_llm_calls: number` and
`max_retries: number` to the trial-config request type (mirrors the existing
`argumentation_rounds`/`deliberation_rounds`/`time_limit_seconds` fields).

**`examples/web/frontend/src/routes/SetupPage.tsx`:** two more `NumberInput`s in the
existing "Advanced settings" `Accordion.Panel` (Dimensions step), immediately following
`time-limit`, following the exact same pattern:
```tsx
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
with matching `useState(8)` / `useState(3)` declarations alongside the existing
`argumentationRounds`/`deliberationRounds`/`timeLimitSeconds` state, and both values added
to the `startTrial(...)` payload in `handleSubmit`.

## 6. Error Handling

`ExecutionConfig`'s validators raise `PSALMConfigError` (`PSALM-C008`) at `.with_execution()`
call time (Pydantic validation runs on model construction, i.e. inside `with_execution`),
consistent with how `AgentConfig.validate_temperature` (`PSALM-C007`) and
`DebateConfig.validate_voting_strategies` (`PSALM-C004`/`PSALM-C005`) already fail fast at
configuration time rather than at `.build()`. In the web app, `Field(ge=1)` on
`TrialConfigRequest` makes FastAPI reject an invalid request with its standard 422 before
`build_psalm` ever runs.

No new failure modes: the semaphore cannot deadlock (bounded resource, always released via
`async with`), and a lower `max_concurrent_llm_calls` only changes pacing, never
correctness — every call that would have succeeded uncapped still succeeds, just
potentially queued behind the cap.

## 7. Breaking Changes

`BaseAgent.__init__` and `Juror.__init__` gain a required `execution: _RunExecution`
parameter. Repo-wide search confirms `psalm/builder.py::_assemble` is the *only*
production construction site for `Prosecutor`/`Defense`/`Judge`/`Juror` anywhere in the
codebase (examples and docs don't construct agents directly) — so despite being a
same-package signature change, there is no external call site to preserve compatibility
for.

`AgentCallRetrying.backoff_seconds` now reports the actual jittered sleep duration instead
of the previously-deterministic exponential value — any consumer asserting an exact
backoff value (none currently exist in the test suite) would need updating to assert a
range instead.

## 8. Testing

- `ExecutionConfig` validation: `max_concurrent_llm_calls < 1`, `max_retries < 1`,
  `backoff_factor <= 0` each raise `PSALMConfigError` with code `PSALM-C008`.
- Semaphore actually caps concurrency: build a `_RunExecution` with `Semaphore(1)`, launch
  two concurrent `_call_llm` calls against a fake/mocked LLM that records the max number
  of simultaneously in-flight calls (e.g. via a counter incremented/decremented around an
  `await asyncio.sleep(...)` inside the fake), assert the observed max never exceeds 1.
- Retry count is honored: `max_retries=1` with an always-failing mock LLM raises
  `PSALMAgentError` after exactly one attempt, with no `asyncio.sleep` call.
- Full-jitter backoff: with `random.uniform` seeded/mocked, assert the sleep duration
  passed is in `[0, backoff_factor**attempt]` for each attempt.
- `PSALM.build()` passes the *same* `_RunExecution` instance (identity, `is`) to every
  constructed agent and to `_ping_all_llms` — assert via inspecting each agent's
  `_execution` attribute post-`_assemble`.
- `_ping_all_llms`/`_ping_llm` read `execution.max_retries`/`execution.backoff_factor`
  instead of the removed `_PING_RETRY_ATTEMPTS`/`_PING_BACKOFF_FACTOR` constants — existing
  ping tests updated to construct/pass an `_RunExecution`.
- `PSALM().with_execution(...)` replaces `self._execution_config`; omitting the call
  leaves the `ExecutionConfig()` default (`8`/`3`/`2.0`).
- Web backend: `TrialConfigRequest` accepts and validates `max_concurrent_llm_calls`/
  `max_retries` (rejects `< 1` with a 422); `build_psalm` forwards both values into
  `.with_execution(...)`.
- Full existing SDK and web-backend suites re-run unchanged (no assertions depend on the
  previous unbounded-concurrency or fixed-backoff behavior) — the cap and jitter only
  affect pacing, not outcomes.

## 9. Files Added / Modified

**Modified:**
- `psalm/models/config.py` — new `ExecutionConfig` model (§2)
- `psalm/builder.py` — `PSALM.__init__`/`with_execution`/`build`/`_ping_all_llms`/
  `_ping_llm`/`_assemble` (§3, §4)
- `psalm/agents/base.py` — new `_RunExecution` dataclass,
  `BaseAgent.__init__`/`_call_llm`/`_call_structured` (§4)
- `psalm/agents/juror.py` — `Juror.__init__` (§4)
- `examples/web/backend/schemas.py` — `TrialConfigRequest` (§5)
- `examples/web/backend/execution.py` — `build_psalm` (§5)
- `examples/web/frontend/src/api/types.ts`, `examples/web/frontend/src/routes/SetupPage.tsx` (§5)
- Corresponding test files under `tests/unit/agents/`, `tests/unit/`, and
  `examples/web/backend/tests/` (§8)

**Unchanged:** `psalm/courtroom/default.py`, `psalm/phases/deliberation.py` (the existing
`asyncio.gather` call sites — the cap is enforced one layer deeper, §4); `DebateConfig`
(execution settings are a separate top-level builder config, not folded into it, per
design decision); any provider `Retry-After` handling (out of scope, §1).
