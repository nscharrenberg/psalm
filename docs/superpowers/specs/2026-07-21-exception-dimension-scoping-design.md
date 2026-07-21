# Exception-Dimension Scoping — Design

## 1. Overview

Root cause of the verdict-aggregation bug (single-dimension Character trial,
jury unanimously "Not Guilty", `weighted_score` 0.52, overall verdict
"Guilty"): protectability reasoning — the idea-expression dichotomy,
"unprotectable idea", "generic/scenes à faire" framing — leaks into every
infringement-dimension evaluation unconditionally, regardless of whether the
case actually selected a matching exception dimension (Scènes à Faire,
Parody/Satire, Pastiche, Citations). Concretely:

- The defense attorney's system prompt teaches idea-expression-dichotomy as
  its "most powerful" tool on every call, with no dependency on the case's
  selected dimensions.
- The judge's defense-argument validation prompt accepts "unprotectable
  ideas, genre conventions" as legitimate grounds unconditionally.
- The juror's scoring rubric bakes "generic / unprotectable (scenes à
  faire)" directly into the infringement dimension's own similarity scale.

Numerically confirmed: three HIGH-importance Character sub-dimensions were
scored "possible" by all three jurors, whose own rationale text was pure
idea-expression-dichotomy reasoning ("the defense has argued... common
archetype... unprotectable") — despite `possible`'s actual definition
describing something else entirely ("wording differs substantially,
independent creation plausible"), and despite the quoted passages being
frequently near-verbatim, not differing. Recomputing `_compute_weighted_score`
from these exact per-sub-dimension scores reproduces `0.5238095238095238`
exactly, confirming this is a deterministic, repeatable consequence of the
scoring pattern — not juror noise (all three jurors scored every
sub-dimension identically).

**Goal:** protectability-based defenses (idea-expression dichotomy, genre
convention, parody, pastiche, citation) are available only when the case
explicitly selects the matching exception dimension. Without one, an
infringement dimension's evaluation — defense argumentation, judge
validation, and jury scoring — is scoped to purely textual/expression
similarity and independent-creation questions. When an exception dimension
*is* selected, its jury-scored `weighted_score` now actually discounts the
infringement verdict's aggregate score, instead of being purely
informational as it is today.

## 2. Defense Attorney Scoping

**File:** `psalm/agents/defense.py`

The existing `_format_sub_dimensions` helper already scopes *which
sub-dimensions* are available per call — exception dimensions only appear
(as "AVAILABLE EXCEPTION TOOLS (optional, cite only if relevant)") when the
case actually selected them. That scoping is correct today and unchanged.

What's wrong is `_SYSTEM_PROMPT`, which is static and sent on every call
regardless of the per-call dimension list. Its "PRIMARY TOOLS" section
currently opens with:

```
1. IDEA-EXPRESSION DICHOTOMY (most powerful): ...
2. LACK OF EXPRESSION-LEVEL SIMILARITY: ...
3. INDEPENDENT CREATION: Show that the claimed similarities are genre
   conventions or common literary devices that any author could
   independently create without access to the source.
```

This becomes:

```
1. LACK OF EXPRESSION-LEVEL SIMILARITY: Even where concepts overlap, show
   that the specific wording, imagery, and narrative choices differ —
   different words, different details, different emotional register.

2. INDEPENDENT CREATION: Show that the specific wording differs enough from
   the source that independent, coincidental arrival at similar content is
   plausible — i.e. this was not copied.
```

("genre conventions" is dropped from tool 2's description — that's
protectability language; "independent creation" as a concept is legitimate
without any exception dimension, since it's about whether copying happened
at all, not about whether copied material is protected.)

A new paragraph replaces the removed tool 1, placed after the numbered
list:

```
EXCEPTION-BASED DEFENSES (unprotectable idea / idea-expression dichotomy,
genre convention, parody, satire, pastiche, permitted quotation or
citation) are available ONLY when a matching entry appears under AVAILABLE
EXCEPTION TOOLS in the case details below, and must be argued strictly
under that named dimension. If no such entry appears, you have no
exception-based defenses in this case — rely only on the two tools above
and the affirmative arguments below.
```

No changes to `_format_sub_dimensions` itself, to method signatures, or to
`ArgumentBatch`/`Argument` shapes.

## 3. Judge Validation Scoping

**Files:** `psalm/agents/judge.py`, `psalm/phases/argumentation.py`

`Judge.validate_argument` gains an optional parameter:

```python
async def validate_argument(
    self,
    argument: Argument,
    source_text: str,
    target_text: str,
    role: str = "prosecution",
    dimensions: list[Dimension] | None = None,
) -> ValidationResult:
```

`_DEFENSE_VALIDATION_PROMPT` (currently a module-level constant) becomes a
function `_defense_validation_prompt(exception_names: list[str]) -> str`
that appends one of two clauses to the existing base text:

- **No exception dimensions selected** (`exception_names` empty):
  ```
  This case has NO exception dimension selected. The defense may NOT argue
  legal insufficiency via unprotectable ideas, genre conventions, scenes à
  faire, parody, satire, pastiche, or citation exceptions — reject any
  argument that relies solely on such reasoning. Valid grounds here are
  differences in specific expression or independent creation only.
  ```
- **Some selected**:
  ```
  This case includes the following exception dimension(s): {names}. The
  defense may argue legal insufficiency via those specific exceptions only
  — reject an argument that invokes an exception not in this list.
  ```

`validate_argument` derives `exception_names` from `dimensions` (filtering
`dimension_type == "exception"`) only when `role == "defense"`; the
prosecution-role branch is unaffected and keeps using
`_PROSECUTION_VALIDATION_PROMPT` unchanged.

In `argumentation.py`, the two `role="defense"` call sites (inside
`_judge_validate_defense_counter` and `_judge_validate_defense`) pass
`dimensions=state.dimensions` — already present on `ArgumentationState`, no
new state needed. The two `role="prosecution"` call sites are unchanged.

## 4. Juror Rubric Simplification

**File:** `psalm/agents/juror.py`

`_VOTE_SYSTEM_PROMPT`'s rubric table changes from:

```
| none   | No similarity | No meaningful similarity found |
| generic | Generic only | Similarity exists but is generic / unprotectable (scenes à faire) |
| possible | Possible infringement | The wording itself differs substantially; independent creation is genuinely plausible |
| clear  | Clear infringement | Near-verbatim or identical wording in a substantial passage; the defense could not credibly rebut with evidence of genuine independent creation |
```

to:

```
| none   | No similarity | No meaningful textual/expression similarity found |
| generic | Slight similarity | Only isolated common words or phrasing; not a meaningful shared passage |
| possible | Possible independent creation | The wording itself differs substantially; independent, coincidental creation is genuinely plausible |
| clear  | Clear similarity | Near-verbatim or identical wording in a substantial passage; independent creation is not a plausible explanation |
```

`possible`'s definition text is unchanged — it was already correct; the bug
was that `generic` was *also* protectability-flavored, creating ambiguity
between the two.  `clear`'s label drops "infringement" (that's a legal
conclusion the jury reaches via its separate `vote`, not something a
textual-similarity sub-score should assert) in favor of "similarity",
mirroring `none`/`generic`.

The surrounding guidance bullets are trimmed: remove the bullet instructing
jurors to weigh "common archetype," "unprotectable idea," or "generic
trope" labels — that reasoning can no longer legitimately reach the jury
without a selected exception dimension, and the bullet's presence
implicitly signals jurors should expect and weigh it. The bullets about
near-verbatim wording as strong copying evidence, and about a single
differing detail not distinguishing an otherwise-identical passage, are
kept unchanged — those are pure textual-similarity reasoning.

`_DISCUSS_SYSTEM_PROMPT`'s parallel bullet — "Be skeptical of labels
('generic,' 'archetype,' 'unprotectable idea') that aren't backed by
actually differing wording" — is trimmed to drop the named protectability
labels, generalized to: "Be skeptical of any claim of distinctness that
isn't backed by actually differing wording — identical or near-identical
passages are strong evidence regardless of how a defense frames them."

No changes to `DimensionScore`, `JurorVote`, `SimilarityScore`, or
`_SCORE_VALUES` — the enum literals (`none`/`generic`/`possible`/`clear`)
are unchanged, only their prompt-facing definitions.

## 5. Exception-Dimension Discount in Aggregation

**File:** `psalm/courtroom/default.py`

`_aggregate_verdict` currently blends only infringement dimensions and
ignores exception dimensions entirely. It changes to:

```python
def _aggregate_verdict(
    dimension_verdicts: list[DimensionVerdict],
    guilty_threshold: float,
) -> Literal["Guilty", "Not Guilty", "Undecided"]:
    infringement_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "infringement"]
    if not infringement_verdicts:
        return "Undecided"

    # Hard override: any CRITICAL infringement dimension that is Guilty → overall Guilty.
    # Unaffected by exceptions — checked before any discount is computed.
    for dv in infringement_verdicts:
        if dv.importance == Importance.CRITICAL and dv.verdict == "Guilty":
            return "Guilty"

    normalised = _blend(infringement_verdicts)
    if normalised is None:
        return "Undecided"

    exception_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "exception"]
    exception_score = _blend(exception_verdicts) or 0.0
    effective = normalised * (1 - exception_score)

    if effective >= guilty_threshold:
        return "Guilty"
    return "Not Guilty"


def _blend(verdicts: list[DimensionVerdict]) -> float | None:
    total_weighted = 0.0
    total_weight = 0.0
    for dv in verdicts:
        multiplier = _IMPORTANCE_MULTIPLIERS[dv.importance]
        total_weighted += dv.weighted_score * multiplier
        total_weight += multiplier
    if total_weight == 0.0:
        return None
    return total_weighted / total_weight
```

`_blend` factors out the importance-weighted-average logic already used for
infringement dimensions, reused for exception dimensions so multiple
selected exceptions (e.g. both Scènes à Faire and Parody/Satire) combine
the same way multiple infringement dimensions already do — one blended
`exception_score`, not independent successive discounts (which would
double-penalize overlapping reasoning). If no exception dimension is
selected, `exception_verdicts` is empty, `_blend` returns `None`,
`exception_score` is `0.0`, and `effective == normalised` — identical to
today's behavior.

`_synthesize_rationale` is updated to show the discount when one applied:
non-zero `exception_score` gets an additional line noting the blended
exception score and the resulting effective score, so the rationale stays
fully traceable (matching the project's existing "complete transparency and
traceability" goal for this pipeline). Exact wording is an implementation
detail for the plan, not fixed here.

## 6. Data Flow

No new data enters or leaves the pipeline. `dimensions` (already part of
`CaseInput`/`ArgumentationState`) is threaded one hop further, into
`Judge.validate_argument`. `DimensionVerdict.weighted_score` (already
computed for exception dimensions today, just discarded) is now read by
`_aggregate_verdict`. No new fields on any Pydantic model, no changes to
`JurorVote`, `DimensionScore`, `ArgumentBatch`, or `DimensionVerdict`.

## 7. Error Handling

No new failure modes. `validate_argument`'s new `dimensions` parameter is
optional (defaults to `None`, treated as "no exception dimensions" —
i.e. the strict, no-exceptions-available prompt); existing callers that
don't pass it (the two prosecution-role call sites) are unaffected.
`_blend` returning `None` for an empty list is handled explicitly (treated
as a `0.0` discount), not raised as an error.

## 8. Testing

- `tests/unit/agents/test_defense.py` (or equivalent): a call with only
  infringement dimensions in scope does not produce an idea-expression /
  unprotectable-idea argument; a call that includes an exception dimension
  may.
- `tests/unit/agents/test_judge.py`: `validate_argument(role="defense", ...)`
  with `dimensions=None` or infringement-only rejects an
  unprotectable-idea-only argument; with a matching exception dimension
  present, accepts one.
- `tests/unit/agents/test_juror.py`: rubric text assertions updated for the
  new label/definition wording.
- `tests/unit/courtroom/test_default.py` (or equivalent): regression test
  reproducing the reported bug's shape — infringement dimension(s) blend to
  a `normalised` above threshold, no exception dimension selected → verdict
  is `Guilty` (unchanged, `exception_score` is `0.0`). A second test with an
  exception dimension present, high `weighted_score` → verdict flips to
  `Not Guilty` via the discount. A third test confirms the CRITICAL
  hard-override still fires regardless of any exception dimension's score.
- Full existing suite (currently 327 passed / 1 skipped) re-run after
  changes; any test asserting on the old rubric wording or old
  `_aggregate_verdict` behavior updated accordingly.

## 9. Breaking Changes

- `Judge.validate_argument` gains a new optional parameter — source
  compatible, no existing call sites break.
- `_aggregate_verdict`'s output can change for any case that already
  selects both an infringement and an exception dimension: today the
  exception dimension's score is pure decoration; after this change it can
  flip a borderline verdict. This is the intended fix, not a regression,
  but any existing test or stored example asserting a specific verdict for
  such a case needs re-checking.
- Rubric wording shown to the LLM (and, transitively, in `reasoning` text
  jurors write) changes — no schema change, but any test asserting on
  specific reasoning phrasing (unlikely, since that text is LLM-generated)
  would need updating.

## 10. Files Added / Modified

**Modified:**
- `psalm/agents/defense.py` — `_SYSTEM_PROMPT` restructured (§2)
- `psalm/agents/judge.py` — `validate_argument` new parameter,
  `_DEFENSE_VALIDATION_PROMPT` becomes a function (§3)
- `psalm/phases/argumentation.py` — two `role="defense"` call sites pass
  `dimensions=state.dimensions` (§3)
- `psalm/agents/juror.py` — `_VOTE_SYSTEM_PROMPT` rubric table and guidance
  bullets, `_DISCUSS_SYSTEM_PROMPT` bullet (§4)
- `psalm/courtroom/default.py` — `_aggregate_verdict` discount logic, new
  `_blend` helper, `_synthesize_rationale` discount line (§5)
- Corresponding test files under `tests/unit/agents/`,
  `tests/unit/phases/`, `tests/unit/courtroom/` (§8)

**Unchanged:** all Pydantic model shapes (`JurorVote`, `DimensionScore`,
`SimilarityScore`, `DimensionVerdict`, `Argument`, `ArgumentBatch`), the web
backend/frontend (no API shape changes), `prosecutor.py` (its
"genre conventions, shared archetypes" language is a weak-evidence signal
for guilt, not a legal-insufficiency defense, and stays as-is).
