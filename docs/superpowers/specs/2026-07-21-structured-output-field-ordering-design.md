# Structured-Output Field Ordering — Design

## 1. Overview

While investigating why a selected exception dimension's jury could vote "Exception
Does Not Apply" yet still contribute a high `weighted_score` toward the verdict discount
(Pastiche: 0.53, Parody/Satire: 0.67 — both above 0.5 despite a "Not Guilty" majority),
tracing the actual final-round votes showed the divergence wasn't caused by scoping
(both dimensions were legitimately selected) or by a minority dissenter — the *majority*
jurors themselves scored several sub-dimensions "possible"/"clear" while still voting
"Not Guilty" overall. Their own sub-dimension scores didn't drive their own vote.

The likely mechanism: every LLM call in this codebase uses
`with_structured_output(SomeModel)`, which constrains generation to a JSON schema whose
fields are emitted in declaration order. The underlying model is autoregressive — each
token is conditioned on every token already generated, including earlier JSON fields,
but cannot be conditioned on fields that haven't been generated yet. Every structured
output model in this codebase that pairs a conclusion field with its supporting
evidence/reasoning field declares the **conclusion first**:

| Model | Conclusion field | Evidence/reasoning field | Order today |
|---|---|---|---|
| `JurorVote` | `vote` | `rationale`, `dimension_scores` | conclusion first |
| `DimensionScore` | `score` | `reasoning` | conclusion first |
| `ValidationResult` | `is_valid` | `rejection_reason` (conditional) | conclusion first |
| `Argument` | `claim` | `proofs` | conclusion first |
| `_TiebreakDecision` (judge.py) | `verdict` | `rationale` | conclusion first |

This means every conclusion in this system is generated *before* the model has written
out the reasoning meant to support it — the reasoning field, generated second, has no
structural pressure to actually determine the conclusion; it can just as easily become
a post-hoc rationalization of a conclusion already committed to. This plausibly
explains the recurring pattern (first the Character-dimension bug, now Pastiche/
Parody-Satire) of a juror's own categorical vote disagreeing with its own sub-dimension
scores, independent of the scoping fixes already shipped.

**Goal:** reorder every structured-output model's fields so evidence/reasoning is
declared before the conclusion it supports, and add one reinforcing sentence to each
relevant prompt stating the same sequencing explicitly. This does not change any
runtime logic — Pydantic field access is always by name — it only changes the order
the LLM is asked to generate fields in.

**Note found during investigation, not part of this plan:** `judge.py`'s
`_StabilityDecision` model is dead code — `detect_stability()` never calls the LLM; it's
a pure Python set comparison (`current_claims == previous_claims`). It is not reordered
here since it's unused; separate cleanup (matching the earlier whole-branch review's
removal of `should_cross_examine`/`_CrossExamDecision`) is a candidate for later, not
in scope for this plan.

## 2. Field Reordering

**`psalm/models/result.py` — `DimensionScore`:**
```python
class DimensionScore(BaseModel):
    sub_dimension: str
    reasoning: str
    score: SimilarityScore
```
(was: `sub_dimension`, `score`, `reasoning`)

**`psalm/models/result.py` — `JurorVote`:**
```python
class JurorVote(BaseModel):
    juror_id: str
    dimension: str | None = None
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    rationale: str
    vote: Literal["Guilty", "Not Guilty", "Undecided"]
```
(was: `juror_id`, `vote`, `rationale`, `dimension_scores`, `dimension`)

`juror_id` and `dimension` are stamped over by calling code after the structured-output
call returns (`Juror.vote()` constructs the returned `JurorVote` with `juror_id=self._juror_id`,
never `result.juror_id`; `vote_all_dimensions()` sets `dimension` via
`.model_copy(update={"dimension": dim.name})`) — the LLM's own values for these two
fields are discarded, so their position doesn't affect reasoning quality. They stay
first, as pure context, not reordered around.

**`psalm/models/result.py` — `ValidationResult`:**
```python
class ValidationResult(BaseModel):
    reasoning: str
    is_valid: bool
    rejection_reason: str | None = None
```
(was: `is_valid`, `rejection_reason`; `reasoning` is new)

`rejection_reason` can't simply move before `is_valid` — it's `None` when valid, so
there's nothing to write before a rejection has been decided. A new unconditional
`reasoning` field is added instead: always required, filled in every case (valid or
not), forcing genuine analysis before `is_valid` is generated. `rejection_reason`
keeps its existing conditional semantics and position, used only when `is_valid=False`
exactly as today — nothing downstream that reads `rejection_reason` changes.

**`psalm/models/evidence.py` — `Argument`:**
```python
class Argument(BaseModel):
    dimension: str
    proofs: list[Proof]
    claim: str
    agent_role: str
    round: int
```
(was: `claim`, `dimension`, `proofs`, `agent_role`, `round`)

`dimension` moves first as a scope declaration (which sub-dimension this argument
addresses), then `proofs` (the cited textual evidence), then `claim` (the assertion
that evidence is meant to support) — evidence is identified before the claim built on
it is stated, rather than a claim being asserted and evidence then assembled to fit it.
`agent_role` and `round` are stamped over by calling code after the fact (every call
site does `.model_copy(update={"round": round, "agent_role": "..."})`) exactly like
`JurorVote`'s `juror_id`/`dimension` — left in their existing trailing position.

**`psalm/agents/judge.py` — `_TiebreakDecision`:**
```python
class _TiebreakDecision(BaseModel):
    rationale: str
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
```
(was: `verdict`, `rationale`)

## 3. Prompt Reinforcement

One sentence added to each prompt that requests one of the reordered models, stating
the same sequencing verbally so the schema order and the prompt's own instructions
reinforce each other rather than the schema being the only signal:

- `psalm/agents/juror.py`'s `_VOTE_SYSTEM_PROMPT` (used by `vote()`, which populates
  `dimension_scores` and `vote` in one call): add "Score every sub-dimension in the
  rubric first, with reasoning grounded in the evidence above. Then write your overall
  rationale synthesizing those scores. Only after that, cast your vote — it should
  follow from the rationale, not precede it."
- `psalm/agents/judge.py`'s `_PROSECUTION_VALIDATION_PROMPT` and the base
  `_DEFENSE_VALIDATION_PROMPT` text (both populate `ValidationResult`): add "State your
  reasoning first, then decide is_valid based on that reasoning."
- `psalm/agents/judge.py`'s tiebreak system prompt (inline string in `tiebreak()`,
  populates `_TiebreakDecision`): add "Explain your reasoning before stating the
  verdict — the verdict should follow from the reasoning, not precede it."
- `psalm/agents/defense.py`'s and `psalm/agents/prosecutor.py`'s `_SYSTEM_PROMPT` (both
  populate `ArgumentBatch`, i.e. lists of `Argument`): add "For each argument, identify
  the specific textual proof first, then state the claim that proof supports — not the
  other way around."

## 4. Data Flow

No new data flows anywhere except `ValidationResult.reasoning`, which is generated by
the LLM but not currently consumed by any downstream code (not logged, not included in
any event, not read by `validate_argument`'s caller). It exists purely to change
generation order; nothing needs to change to accommodate it structurally, though a
follow-up could later surface it (e.g. in `ArgumentRejected`/`ArgumentValidated` events)
if useful — out of scope here.

## 5. Error Handling

None needed. No new failure modes — every field remains exactly as required/optional
as it was; only declaration order changes, plus one new always-required field on
`ValidationResult` that the LLM must fill on every structured-output call already being
made (same call, same required-field mechanics Pydantic already enforces for
`rejection_reason` today under `mode="after"` validators elsewhere in this codebase).

## 6. Testing

Reordering Pydantic fields does not change any runtime behavior — field access is
always by name, never position — so the entire existing test suite is expected to keep
passing unchanged after this plan, with two categories of additions:

- **Order-assertion regression tests** (one per reordered model): assert
  `list(Model.model_fields) == [...]` in the new order, so a future edit can't silently
  revert the sequencing this plan establishes. These are the only tests that can
  meaningfully verify this plan's actual change, since the change is generation-order,
  not logic.
- **Prompt-text assertions** (one per touched prompt): assert the new sequencing
  sentence is present, matching the existing pattern already used throughout this
  codebase's prompt tests (e.g. `test_vote_prompt_grounds_verbatim_text_as_strong_evidence`).

What this plan **cannot** prove: that reordering actually reduces vote/score divergence
in practice. That would require live-LLM trials comparing before/after divergence
rates across many runs, which is expensive, flaky, and out of scope for an automated
test suite. This is stated explicitly so a clean test run is not mistaken for
behavioral proof — the next real signal will be whether future reported bugs of this
exact shape (categorical vote disagreeing with its own supporting scores) recur.

## 7. Breaking Changes

- `ValidationResult` gains a new required field (`reasoning: str`). Any code
  constructing a `ValidationResult` directly (not via the LLM) — e.g. test fixtures —
  needs updating to supply it. Existing tests using
  `ValidationResult(is_valid=True)`/`ValidationResult(is_valid=False, rejection_reason=...)`
  will fail to construct until updated; this is expected and each call site needs a
  `reasoning="..."` argument added.
- No API/schema changes visible outside the SDK's own agent layer — `DimensionScore`,
  `JurorVote`, `Argument`, and `_TiebreakDecision` keep the same field *names* and
  *types*, only declaration order changes, which is invisible to anything reading them
  by attribute (all current consumers, including the web backend/frontend, which only
  ever see the already-serialized `.model_dump()` output — JSON field order in a dict
  does not affect `dict`/JS-object key access).

## 8. Files Added / Modified

**Modified:**
- `psalm/models/result.py` — `DimensionScore`, `JurorVote`, `ValidationResult` field
  order (§2)
- `psalm/models/evidence.py` — `Argument` field order (§2)
- `psalm/agents/judge.py` — `_TiebreakDecision` field order, prosecution/defense
  validation prompts, tiebreak prompt (§2, §3)
- `psalm/agents/juror.py` — `_VOTE_SYSTEM_PROMPT` (§3)
- `psalm/agents/defense.py` — `_SYSTEM_PROMPT` (§3)
- `psalm/agents/prosecutor.py` — `_SYSTEM_PROMPT` (§3)
- Corresponding test files under `tests/unit/models/`, `tests/unit/agents/` (§6) —
  new order-assertion tests, new prompt-text assertions, and updates to every existing
  `ValidationResult(...)` construction site to supply `reasoning`

**Unchanged:** all other Pydantic models (`Proof`, `ArgumentBatch`, `RoundArguments`,
`ArgumentationLog`, `RoundDeliberation`, `DebateLog`, `ResultMetadata`,
`DimensionVerdict`, `PSALMResult`, etc.) — none of these pair a conclusion field with
its own supporting evidence field the way the five models above do. `_StabilityDecision`
(dead code, see §1) is left as-is. The web backend/frontend, `psalm/courtroom/default.py`,
`psalm/phases/*.py`, and `psalm/voting/*.py` are unaffected — none construct these
models directly except via the LLM calls and code paths already named above.
