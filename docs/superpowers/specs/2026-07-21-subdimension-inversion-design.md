# Sub-Dimension Score Inversion — Design

## 1. Overview

`psalm/dimensions/literature/exceptions/scenes_a_faire.py`'s "Creative Elaboration (INVERSE)"
sub-dimension is documented as semantically inverted — its own description says *"HIGH
originality reduces scènes à faire score, indicating more protectable content"* — but
`_compute_weighted_score` in `psalm/phases/deliberation.py` sums every sub-dimension's score the
same direction, with no inversion handling. This was harmless while exception-dimension
`weighted_score` was purely decorative; the 2026-07-21 exception-dimension-scoping fix made it
genuinely discount the infringement verdict (`psalm/courtroom/default.py::_aggregate_verdict`),
so this latent bug is now load-bearing and can bias verdicts backwards for cases where source and
target share near-verbatim *original* prose — the strongest possible infringement signal gets
scored as if it were the weakest.

A second, related problem surfaced during design: the sub-dimension's own name and description
are shown verbatim to the juror (`_format_sub_dimension_rubric` in `psalm/agents/juror.py`
renders `sd.name`/`sd.description` directly into the vote prompt), telling the juror about the
inversion — but the juror's rubric was separately rewritten (structured-output field-ordering
work, same date) to be *"a pure measure of textual/expression similarity, not a legal
conclusion."* Those two instructions now contradict each other, and if a juror tries to manually
account for the inversion while the code also flips the score, the two cancel out and the bug
returns in a different shape. The user confirmed the sub-dimension's inversion note was a
temporary workaround, superseded by this design's permanent, code-only fix — safe to remove.

**Goal:** add a general-purpose `inverse` marker to `SubDimension`, teach
`_compute_weighted_score` to flip an inverted sub-dimension's contribution around its max score,
and make the juror-facing rubric identical for inverted and non-inverted sub-dimensions — the
inversion is entirely a Python-side aggregation concern, invisible to the LLM.

## 2. Data Model

**`psalm/dimensions/base.py` — `SubDimension`:**
```python
class SubDimension(BaseModel):
    name: str
    description: str
    importance: Importance = Importance.MEDIUM
    inverse: bool = False
```
Defaults to `False`, so every existing sub-dimension across all dimension files (~30 today) is
unaffected without any changes to those files.

## 3. Scènes à Faire's Sub-Dimension

**`psalm/dimensions/literature/exceptions/scenes_a_faire.py`:**
```python
SubDimension(
    name="Creative Elaboration",
    description=(
        "Distinctive voice/style (unique authorial tone, specific creative expression "
        "patterns), original descriptive detail (particular sensory richness, unique "
        "observational depth), psychological depth (complex character interiority, "
        "specific emotional nuance), unique dialogue (particular speech patterns, specific "
        "conversational styles), innovative structure (unique narrative architectures, "
        "specific formal experiments), creative worldbuilding (particular imaginative "
        "constructions, unique setting details)."
    ),
    importance=Importance.HIGH,
    # HIGH textual similarity here means the shared passage is highly original/creatively
    # elaborate — the strongest possible infringement signal, not scenes-à-faire material.
    # _compute_weighted_score flips this sub-dimension's contribution accordingly. The juror
    # is never told about this — it scores this sub-dimension exactly like any other, using
    # the same pure-textual-similarity rubric (see psalm/agents/juror.py's
    # _VOTE_SYSTEM_PROMPT); the inversion is applied only during aggregation, in code.
    inverse=True,
),
```
Changes from today: the name drops the `" (INVERSE)"` suffix; the description drops the trailing
`"Note: HIGH originality reduces scènes à faire score, indicating more protectable content."`
sentence (the temporary workaround the user confirmed is now superseded). Both were juror-visible
via `_format_sub_dimension_rubric` and are removed so the juror sees a plain content description,
identical in kind to every other sub-dimension it scores. The semantic reasoning moves into a
code comment, visible only to maintainers reading the source.

## 4. Aggregation

**`psalm/phases/deliberation.py` — `_compute_weighted_score`:**
```python
def _compute_weighted_score(votes: list[JurorVote], dimension: Dimension) -> float:
    """Average juror scores per sub-dimension, weight by importance, normalise to [0, 1]."""
    if not votes:
        return 0.0

    sub_dim_map = {sd.name: sd for sd in dimension.sub_dimensions}
    if not sub_dim_map:
        return 0.0

    scores_by_sub: dict[str, list[int]] = {name: [] for name in sub_dim_map}
    for vote in votes:
        for ds in vote.dimension_scores:
            if ds.sub_dimension in scores_by_sub:
                scores_by_sub[ds.sub_dimension].append(_SCORE_VALUES[ds.score])

    weighted_total = 0.0
    max_possible = 0.0
    for sub_name, sub_dim in sub_dim_map.items():
        multiplier = _IMPORTANCE_MULTIPLIERS[sub_dim.importance]
        raw_scores = scores_by_sub[sub_name]
        avg = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
        max_score = 3  # SimilarityScore.CLEAR
        contribution = (max_score - avg) if sub_dim.inverse else avg
        weighted_total += contribution * multiplier
        max_possible += max_score * multiplier

    if max_possible == 0.0:
        return 0.0
    return weighted_total / max_possible
```

Only the `contribution` line changes. `max_possible`'s calculation is untouched — a flipped
`avg` still ranges `[0, 3]`, the same range as an unflipped one, so the denominator's meaning
(the maximum possible weighted total) is unaffected by inversion.

Worked example: source and target share a near-verbatim passage that's highly original prose.
Jurors score "Creative Elaboration" as `clear` (avg=3). Unflipped, this would contribute `3 ×
1.5 = 4.5` toward "this is excused" — backwards. Flipped: `contribution = 3 - 3 = 0`, contributing
nothing toward the excuse — correct, since verbatim copying of original prose is not scenes-à-
faire material. Conversely, if jurors find no creative elaboration at all (avg=0, the passage
reads as generic/formulaic), flipped contribution is `3 - 0 = 3`, the maximum — correct, since
genuinely generic content is exactly what this exception should excuse.

## 5. Juror Prompt

No changes. `_VOTE_SYSTEM_PROMPT` and `_format_sub_dimension_rubric` are untouched — a sub-
dimension marked `inverse=True` is rendered and scored identically to any other. This is the
core of the fix: the juror's job stays "rate textual similarity for the sub-dimension I'm shown,"
full stop; interpreting what a given score means for the exception's own semantics is entirely
`_compute_weighted_score`'s job.

## 6. Data Flow

No new data flows. `inverse` is read once, inside `_compute_weighted_score`, from the
`Dimension`/`SubDimension` objects already passed into it — no new parameters, no new fields on
`JurorVote`, `DimensionScore`, or any result model.

## 7. Error Handling

None needed. `inverse` defaults to `False` and is a plain field read, not user input — no new
failure modes.

## 8. Testing

- `SubDimension` accepts and defaults `inverse` correctly (`inverse=False` by default;
  `inverse=True` when explicitly set).
- `_compute_weighted_score` with a synthetic dimension containing one `inverse=True`
  sub-dimension: confirm a `clear` (avg=3) score contributes 0, a `none` (avg=0) score
  contributes the sub-dimension's full weight, and a mixed dimension (one normal + one inverted
  sub-dimension) blends both correctly — hand-traced expected values, not just "doesn't crash."
- `SCENES_A_FAIRE`'s "Creative Elaboration" sub-dimension has `inverse=True`, and its `name` no
  longer contains `"INVERSE"` and its `description` no longer contains `"reduces"` (regression
  guard against the juror-visible hint being reintroduced).
- `_format_sub_dimension_rubric(SCENES_A_FAIRE)`'s output does not contain the word `"inverse"`
  (case-insensitive) anywhere — confirms the juror-facing prompt text carries no trace of the
  inversion, the core guarantee this design depends on.
- Full existing suite re-run after changes; since `inverse` defaults to `False`, every other
  dimension's `_compute_weighted_score` behavior is provably unchanged (the `contribution` branch
  is only reachable when `sub_dim.inverse` is `True`, which no other sub-dimension sets).

## 9. Breaking Changes

- `SubDimension` gains a new field with a default — source-compatible, no existing construction
  site breaks.
- `SCENES_A_FAIRE`'s "Creative Elaboration" sub-dimension's `name` and `description` change —
  any test asserting on the old `"Creative Elaboration (INVERSE)"` string or the old "Note: HIGH
  originality..." sentence needs updating. A grep-based check during implementation should
  confirm no other file references either string.
- `_compute_weighted_score`'s output changes for any dimension verdict computed over Scènes à
  Faire specifically, when jurors score "Creative Elaboration" away from a flat 0/no-scores
  baseline — this is the intended fix, not a regression, but any stored example or golden-value
  test tied to a specific Scènes à Faire `weighted_score` needs re-checking.

## 10. Files Added / Modified

**Modified:**
- `psalm/dimensions/base.py` — `SubDimension.inverse` field (§2)
- `psalm/dimensions/literature/exceptions/scenes_a_faire.py` — `inverse=True`, name/description
  cleanup (§3)
- `psalm/phases/deliberation.py` — `_compute_weighted_score`'s `contribution` calculation (§4)
- Corresponding test files under `tests/unit/dimensions/`, `tests/unit/phases/`,
  `tests/unit/agents/` (§8)

**Unchanged:** `psalm/agents/juror.py` (no prompt changes, per §5), every other dimension file
(no other sub-dimension sets `inverse=True`), `psalm/courtroom/default.py` (dimension-level
aggregation is unaffected — this fix operates entirely within one dimension's own
`_compute_weighted_score` call, upstream of `_aggregate_verdict`), the web backend/frontend (no
API shape changes).
