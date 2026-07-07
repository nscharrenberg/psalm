# Argumentation Phase v2: Exception Dimensions & Evidentiary Discipline

**Date**: 2026-07-07
**Author**: Noah Scharrenberg
**Project**: psalm-eu v2
**Scope**: Exception-dimension cross-application, explicit argument-exhaustion signaling, factual/unambiguous evidentiary constraints on prosecutor and defense agents.

---

## 1. Overview

The symmetric 4-step argumentation round (prosecution argues → defense counters → defense argues → prosecution counters, each judge-validated) and the `EvaluationStrategy` per-dimension pipeline are already implemented (plans 09 and 11) and are **not** being redesigned here. This spec covers four gaps identified by auditing the current code against the intended courtroom behavior:

1. **Exception dimensions** (e.g. `scenes-a-faire`) currently cannot be applied to any other dimension's argumentation — `Dimension` has no type marker, and `FULLY_SEPARATE` (the default `EvaluationStrategy`) isolates every dimension's pipeline to itself alone.
2. **Argument exhaustion is silent** — an agent that has nothing left to argue just returns an empty list; there is no explicit "no further arguments" statement visible in the log.
3. **Prompts actively encourage padding weak arguments** — `_SYSTEM_PROMPT` in both `prosecutor.py` and `defense.py` currently says *"You MUST produce at least one argument... including generic or weak ones"* and *"make the argument anyway"*, the opposite of the required factual/unambiguous/no-guesswork discipline.
4. **No structural gate catches a non-answer** — if an agent returns an empty batch without declaring it's done, nothing currently detects or corrects that.

Order of argument (prosecution always argues first, per steps 1–2 then 3–4) stays fixed — no reversal support is being added.

---

## 2. Dimension type: infringement vs. exception

### 2.1 `Dimension` model

```python
# psalm/dimensions/base.py
from typing import Literal

class Dimension(BaseModel):
    name: str
    description: str
    sub_dimensions: list[SubDimension]
    importance: Importance = Importance.MEDIUM
    dimension_type: Literal["infringement", "exception"] = "infringement"
```

`CHARACTER`, `PLOT`, `WORLD_BUILDING` need no changes (default applies). `SCENES_A_FAIRE` is updated:

```python
# psalm/dimensions/scenes_a_faire.py
SCENES_A_FAIRE = Dimension(
    name="scenes-a-faire",
    description="Stock elements that are not copyright-protected.",
    importance=Importance.MEDIUM,
    dimension_type="exception",
    sub_dimensions=[...],  # unchanged
)
```

`DebateConfig.dimensions` / `CaseInput.dimensions` remain one flat `list[Dimension]` — a caller opts in to exception handling simply by including `SCENES_A_FAIRE` in the list, same as today:

```python
DebateConfig(dimensions=[CHARACTER, PLOT, WORLD_BUILDING, SCENES_A_FAIRE])
```

### 2.2 `DimensionVerdict` gains the same field

```python
# psalm/models/result.py
class DimensionVerdict(BaseModel):
    dimension: str
    dimension_type: Literal["infringement", "exception"]
    importance: Importance
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    weighted_score: float
    argumentation_log: ArgumentationLog
    debate_log: DebateLog
```

Populated from the source `Dimension.dimension_type` wherever `DimensionVerdict` is constructed (`courtroom/default.py`, `builder.py::_identical_texts_result`).

---

## 3. Cross-dimension wiring

An exception dimension always gets its own full pipeline and its own `DimensionVerdict` (confirmed requirement — not merely ammunition). Separately, its sub-dimensions are made available as optional argumentative tools inside every infringement dimension's pipeline.

### 3.1 `FULLY_SEPARATE` (default strategy) — `psalm/courtroom/default.py`

`_run_single_dimension` changes its scoping logic:

```python
async def _run_single_dimension(
    self,
    dimension: Dimension,
    delib_phase: DeliberationPhase,
    case_input: CaseInput,
) -> DimensionVerdict:
    if dimension.dimension_type == "infringement":
        exception_dims = [d for d in case_input.dimensions if d.dimension_type == "exception"]
        scoped_dims = [dimension] + exception_dims
    else:
        scoped_dims = [dimension]  # exception dimensions run standalone, no aux injection
    scoped_input = case_input.model_copy(update={"dimensions": scoped_dims})
    arg_log = await self._argumentation_phase.run(scoped_input)
    verdict, debate_log, weighted_score = await delib_phase.run(arg_log, dimension)
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

Deliberation still scores only `dimension`'s own sub-dimensions (`Juror.vote(dimension=dimension)` is unchanged) — the exception dimension's sub-dims are argumentation-time context only, never scored as part of the infringement dimension's verdict.

No change needed to `builder.py::_assemble` — it already creates one `DeliberationPhase` per entry in `DebateConfig.dimensions`, regardless of type, so the 1:1 zip in `_run_fully_separate` already covers exception dimensions correctly.

### 3.2 `SHARED_ARG_PER_DIM_DELIBERATION` and `SHARED_ALL`

No orchestration change. Both already pass the full `case_input.dimensions` (infringement + exception together) into one shared `ArgumentationPhase.run` call, and both already run one deliberation per dimension in that list (`_run_shared_arg`) or one shared `vote_all_dimensions` pass (`_run_shared_all`). Exception dimensions are already "in the room" as soon as they're included in `dimensions` — the only change these two strategies need is the prompt-formatting change in §4.

### 3.3 Verdict aggregation excludes exception dimensions

```python
# psalm/courtroom/default.py
def _aggregate_verdict(
    dimension_verdicts: list[DimensionVerdict],
    guilty_threshold: float,
) -> Literal["Guilty", "Not Guilty", "Undecided"]:
    infringement_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "infringement"]
    if not infringement_verdicts:
        return "Undecided"

    for dv in infringement_verdicts:
        if dv.importance == Importance.CRITICAL and dv.verdict == "Guilty":
            return "Guilty"

    total_weighted = sum(dv.weighted_score * _IMPORTANCE_MULTIPLIERS[dv.importance] for dv in infringement_verdicts)
    total_weight = sum(_IMPORTANCE_MULTIPLIERS[dv.importance] for dv in infringement_verdicts)
    if total_weight == 0.0:
        return "Undecided"
    normalised = total_weighted / total_weight
    return "Guilty" if normalised >= guilty_threshold else "Not Guilty"
```

Exception dimensions are excluded because their own "Guilty" verdict means "the shared material is indeed generic/unprotectable" — evidence *against* infringement, not for it — a different polarity than infringement dimensions. They still appear in `PSALMResult.dimension_verdicts` for transparency; `_synthesize_rationale` labels them distinctly (e.g. `"scenes-a-faire [exception, excluded from verdict]: Not Guilty"`).

`builder.py::_identical_texts_result` also gains `dimension_type=dim.dimension_type` on each constructed `DimensionVerdict` for consistency (it bypasses `_aggregate_verdict` entirely, hardcoding the identical-text shortcut, so no other change needed there).

---

## 4. Prompt formatting — `_format_sub_dimensions`

Duplicated identically today in `psalm/agents/prosecutor.py` and `psalm/agents/defense.py`. Both become type-aware:

```python
def _format_sub_dimensions(dimensions: list[Dimension]) -> str:
    lines: list[str] = []
    infringement_dims = [d for d in dimensions if d.dimension_type == "infringement"]
    exception_dims = [d for d in dimensions if d.dimension_type == "exception"]

    for dim in infringement_dims:
        lines.append(f"\nPRIMARY DIMENSION (must argue): {dim.name} — {dim.description}")
        lines.append("Sub-dimensions (argue ALL marked HIGH or CRITICAL where factually supportable):")
        for sd in dim.sub_dimensions:
            lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")

    for dim in exception_dims:
        lines.append(f"\nAVAILABLE EXCEPTION TOOLS (optional, cite only if relevant): {dim.name} — {dim.description}")
        for sd in dim.sub_dimensions:
            lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")

    return "\n".join(lines)
```

This single change covers all three `EvaluationStrategy` modes: under `FULLY_SEPARATE` the list passed in is `[primary] + exception_dims`; under `SHARED_ARG`/`SHARED_ALL` it's the full configured list containing both types together. Either way, infringement dimensions render as mandatory, exception dimensions as optional tools.

---

## 5. Explicit "no further arguments" signal

### 5.1 New shared models — `psalm/models/evidence.py`

```python
from pydantic import model_validator

class ClosingStatement(BaseModel):
    round: int
    statement: str

class ArgumentBatch(BaseModel):
    arguments: list[Argument] = Field(default_factory=list)
    no_further_arguments: bool = False
    closing_statement: str | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> "ArgumentBatch":
        if self.no_further_arguments and not self.closing_statement:
            raise ValueError("closing_statement is required when no_further_arguments=True")
        if self.no_further_arguments and self.arguments:
            raise ValueError("no_further_arguments=True must not include arguments")
        return self
```

This replaces the `_ArgumentList(arguments: list[Argument])` model currently duplicated in `prosecutor.py` and `defense.py`. `Argument` itself is unchanged (still requires non-empty `proofs`) — a "nothing more to say" response never constructs an `Argument`.

Note: since this is a pydantic `model_validator`, a malformed `no_further_arguments=True` response raises during structured-output parsing inside `structured_llm.ainvoke(...)`, which `BaseAgent._call_structured`'s existing exception-based retry (`_RETRY_ATTEMPTS = 3`) already retries automatically. No new plumbing needed for that failure mode — only for the separate "quietly empty" case in §5.4.

### 5.2 Agent method signatures

All four gather methods change return type from `list[Argument]` to `ArgumentBatch`, and gain an optional `retry_hint` parameter used by the completeness gate (§5.4):

- `Prosecutor.gather_arguments(source_text, target_text, dimensions, round, prior_defense_arguments=None, retry_hint=None) -> ArgumentBatch`
- `Prosecutor.gather_counter_arguments(source_text, target_text, dimensions, defense_arguments, round, retry_hint=None) -> ArgumentBatch`
- `Defense.gather_counter_arguments(source_text, target_text, dimensions, prosecutor_arguments, round, retry_hint=None) -> ArgumentBatch`
- `Defense.gather_arguments(source_text, target_text, dimensions, round, retry_hint=None) -> ArgumentBatch`

When `retry_hint` is set, it's appended to the user message content as an explicit correction (see §5.4).

### 5.3 `RoundArguments` and `ArgumentationState`

```python
# psalm/models/result.py
class RoundArguments(BaseModel):
    round: int
    prosecution_arguments: list[Argument]
    prosecution_closing_statement: str | None = None
    defense_counters: list[Argument]
    defense_counter_closing_statement: str | None = None
    defense_arguments: list[Argument]
    defense_closing_statement: str | None = None
    prosecution_counters: list[Argument]
    prosecution_counter_closing_statement: str | None = None
```

```python
# psalm/models/state.py — ArgumentationState gains 4 accumulator lists (round-tagged,
# mirroring how prosecution_arguments/defense_counters/etc. already accumulate)
prosecution_closing_statements: list[dict[str, Any]] = Field(default_factory=list)
defense_counter_closing_statements: list[dict[str, Any]] = Field(default_factory=list)
defense_closing_statements: list[dict[str, Any]] = Field(default_factory=list)
prosecution_counter_closing_statements: list[dict[str, Any]] = Field(default_factory=list)
```

Closing statements don't go through per-argument judge validation (they're procedural remarks, not factual claims requiring proof) — each step's node handler appends directly to its accumulator.

### 5.4 `ArgumentationPhase` step handlers

Each of the four step node methods (`_prosecution_argue`, `_defense_counter`, `_defense_argue`, `_prosecution_counter`) is rewritten to call the agent through a shared completeness-retry wrapper, then split the resulting `ArgumentBatch` into pending arguments (still judge-validated per-argument as today) and a closing statement (appended directly, round-tagged):

```python
_COMPLETENESS_RETRY_ATTEMPTS = 2
_COMPLETENESS_RETRY_HINT = (
    "Your previous response provided no arguments and did not declare "
    "no_further_arguments. You MUST either provide at least one factually-grounded "
    "argument, or explicitly set no_further_arguments=True with a closing_statement "
    "explaining why you have nothing further to add."
)

async def _call_with_completeness_retry(
    self, call: Callable[[str | None], Awaitable[ArgumentBatch]]
) -> ArgumentBatch:
    hint: str | None = None
    for attempt in range(_COMPLETENESS_RETRY_ATTEMPTS + 1):
        batch = await call(hint)
        if self._judge.validate_batch_completeness(batch):
            return batch
        hint = _COMPLETENESS_RETRY_HINT
    raise PSALMAgentError(
        code="PSALM-A004",
        message="Agent failed to provide arguments or declare no_further_arguments after retries.",
        context={"attempts": _COMPLETENESS_RETRY_ATTEMPTS + 1},
        suggestion="Check the LLM model's instruction-following reliability.",
    )
```

Example for step 1:

```python
async def _prosecution_argue(self, state: ArgumentationState) -> dict[str, Any]:
    round_num = state.current_round + 1
    prior_defense = list(state.defense_arguments) or None
    batch = await self._call_with_completeness_retry(
        lambda hint: self._prosecutor.gather_arguments(
            source_text=state.source_text,
            target_text=state.target_text,
            dimensions=state.dimensions,
            round=round_num,
            prior_defense_arguments=prior_defense,
            retry_hint=hint,
        )
    )
    closing = (
        [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
        if batch.closing_statement else []
    )
    return {
        "pending_prosecution_arguments": [a.model_dump() for a in batch.arguments],
        "prosecution_closing_statements": state.prosecution_closing_statements + closing,
    }
```

The other three step handlers follow the same shape. Existing per-argument judge validation nodes (`_judge_validate_prosecution`, etc.) are unchanged — they still operate on `pending_*_arguments`.

### 5.5 Stop condition — unchanged

`_check_next_round`'s existing "all four argument lists empty this round" check already correctly implies "all four sides declared no_further_arguments this round" (an `ArgumentBatch` with `arguments=[]` only reaches this point if it was accepted as complete, i.e. `no_further_arguments=True`). No logic change needed there.

### 5.6 `_finalize_arguments` — include closing-only rounds

The current inclusion check (`if pros_args or def_counters or def_args or pros_counters:`) must also treat a round as non-empty if it carries closing statements, so the final "everyone rests" round is still recorded in the log with all four remarks visible, even when every argument list is empty:

```python
async def _finalize_arguments(self, state: ArgumentationState) -> dict[str, Any]:
    def _closing_for(statements: list[dict[str, Any]], r: int) -> str | None:
        match = next((s for s in statements if s["round"] == r), None)
        return match["statement"] if match else None

    rounds = []
    for r in range(1, state.current_round + 1):
        pros_args = [a for a in state.prosecution_arguments if a.round == r]
        def_counters = [a for a in state.defense_counters if a.round == r]
        def_args = [a for a in state.defense_arguments if a.round == r]
        pros_counters = [a for a in state.prosecution_counters if a.round == r]
        pros_closing = _closing_for(state.prosecution_closing_statements, r)
        def_counter_closing = _closing_for(state.defense_counter_closing_statements, r)
        def_closing = _closing_for(state.defense_closing_statements, r)
        pros_counter_closing = _closing_for(state.prosecution_counter_closing_statements, r)
        if pros_args or def_counters or def_args or pros_counters or pros_closing or def_counter_closing or def_closing or pros_counter_closing:
            rounds.append(
                RoundArguments(
                    round=r,
                    prosecution_arguments=pros_args,
                    prosecution_closing_statement=pros_closing,
                    defense_counters=def_counters,
                    defense_counter_closing_statement=def_counter_closing,
                    defense_arguments=def_args,
                    defense_closing_statement=def_closing,
                    prosecution_counters=pros_counters,
                    prosecution_counter_closing_statement=pros_counter_closing,
                )
            )
    log = ArgumentationLog(rounds=rounds)
    return {"argumentation_log": log.model_dump()}
```

---

## 6. Factual / unambiguous / no-guesswork constraint

### 6.1 Prosecutor and defense system prompts

Remove all forced-quota and approximation-tolerance language that contradicts the requirement. `_SYSTEM_PROMPT` in both `prosecutor.py` and `defense.py` drops:
- *"You MUST produce at least one argument per HIGH and CRITICAL sub-dimension where any similarity exists — including generic or weak ones."*
- *"Structural or expression-level similarities... present these even if the defense may rebut them. The debate must proceed."*
- *"You MUST produce at least one argument"* (all three occurrences, across both files' system and user-message text).

Replacement instruction (added to both prompts, worded per role):

> Only assert claims backed by clear, unambiguous textual evidence. If no such evidence exists for a sub-dimension, do not argue it — omit it. Never present a guess, inference, or possibility as if it were a settled fact. If you have nothing further that meets this bar, say so explicitly (see `no_further_arguments`) rather than padding with a speculative claim.

The existing "quote as closely as possible to the original; close approximations are acceptable" clause is **kept** — it concerns excerpt-copying fidelity, not claim certainty, and doesn't conflict with the no-guesswork rule.

### 6.2 Judge validation prompts — hedging/speculation gate

`_PROSECUTION_VALIDATION_PROMPT` and `_DEFENSE_VALIDATION_PROMPT` in `psalm/agents/judge.py` each gain a new rejection criterion:

> (N) The claim is stated as a clear, unambiguous assertion — reject if it uses hedging or speculative language ("might," "could suggest," "possibly," "perhaps," "may indicate") or otherwise presents an inference/guess as settled fact without clear textual grounding.

This is enforced through the existing `Judge.validate_argument` LLM call — no new method needed here, just an additional criterion in the existing prompts.

### 6.3 Batch completeness gate — new `Judge` method

Deterministic, non-LLM check (same style as `Judge.detect_stability`, which already does a plain Python comparison with no model call):

```python
# psalm/agents/judge.py
def validate_batch_completeness(self, batch: ArgumentBatch) -> bool:
    if batch.no_further_arguments:
        return True  # pydantic validator already enforced closing_statement is present
    return bool(batch.arguments)
```

Used by `ArgumentationPhase._call_with_completeness_retry` (§5.4) to catch the case where an agent returns an empty batch without declaring `no_further_arguments` — a response that is structurally valid per `ArgumentBatch`'s own validator but doesn't actually resolve the step. On repeated failure to resolve (2 retries with a corrective prompt hint), raises `PSALMAgentError` with a new code `PSALM-A004`.

---

## 7. Breaking changes summary

| What | Old | New |
|---|---|---|
| `Dimension` | no type concept | `dimension_type: Literal["infringement", "exception"] = "infringement"` |
| `DimensionVerdict` | no type field | adds `dimension_type` |
| `Prosecutor`/`Defense` gather methods | return `list[Argument]` | return `ArgumentBatch` |
| `RoundArguments` | 4 argument-list fields | adds 4 optional closing-statement fields |
| `ArgumentationState` | no closing-statement storage | adds 4 round-tagged accumulator lists |
| `_format_sub_dimensions` | uniform "must argue" framing | type-aware: mandatory for infringement, optional-tool for exception |
| `_aggregate_verdict` / `_synthesize_rationale` | operates on all `dimension_verdicts` | filters to `dimension_type == "infringement"` only |
| `_run_single_dimension` (FULLY_SEPARATE) | scopes to `[dimension]` only | infringement dims get `[dimension] + exception_dims`; exception dims stay `[dimension]` |
| `Judge` | `validate_argument`, `detect_stability`, `tiebreak` | adds `validate_batch_completeness` |
| Prosecutor/defense `_SYSTEM_PROMPT` | forces at-least-one-argument quota, tolerates weak/generic padding | forbids padding; requires explicit `no_further_arguments` instead |

## 8. Files added / modified

| File | Change |
|---|---|
| `psalm/dimensions/base.py` | Add `dimension_type` field to `Dimension` |
| `psalm/dimensions/scenes_a_faire.py` | Set `dimension_type="exception"` |
| `psalm/models/evidence.py` | Add `ArgumentBatch`, `ClosingStatement` |
| `psalm/models/result.py` | Add `dimension_type` to `DimensionVerdict`; add 4 closing-statement fields to `RoundArguments` |
| `psalm/models/state.py` | Add 4 closing-statement accumulator lists to `ArgumentationState` |
| `psalm/agents/prosecutor.py` | Rewrite `_SYSTEM_PROMPT`, `_format_sub_dimensions`; change return types to `ArgumentBatch`; add `retry_hint` param |
| `psalm/agents/defense.py` | Same as above |
| `psalm/agents/judge.py` | Add hedging/speculation criterion to both validation prompts; add `validate_batch_completeness` |
| `psalm/phases/argumentation.py` | Rewrite all 4 step node methods; add `_call_with_completeness_retry`; update `_finalize_arguments` inclusion check |
| `psalm/courtroom/default.py` | Update `_run_single_dimension` scoping; filter `_aggregate_verdict`/`_synthesize_rationale` by `dimension_type` |
| `psalm/builder.py` | Add `dimension_type` to `DimensionVerdict` construction in `_identical_texts_result` |
| `psalm/exceptions.py` | New error code `PSALM-A004` (batch-completeness retry exhausted) |

## 9. Unchanged

Argue-first order (prosecution always first), the 4-step symmetric round graph topology, `EvaluationStrategy` enum and its three modes' basic orchestration shape, `guilty_threshold`/CRITICAL-override logic (now scoped to infringement dimensions only), `Argument` model itself, judge tiebreaking, voting strategies, deliberation phase internals.
