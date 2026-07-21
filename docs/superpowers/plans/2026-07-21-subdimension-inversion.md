# Sub-Dimension Score Inversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `_compute_weighted_score` not handling Scènes à Faire's inverted "Creative
Elaboration" sub-dimension, which is now load-bearing since exception dimensions genuinely
discount the infringement verdict.

**Architecture:** A new general-purpose `inverse: bool = False` field on `SubDimension`, read
only by `_compute_weighted_score`'s aggregation math — the juror-facing prompt is unchanged for
every sub-dimension regardless of its `inverse` value, so the inversion is invisible to the LLM
and lives entirely in Python.

**Tech Stack:** Python 3, Pydantic v2, pytest.

## Global Constraints

- The juror-facing rubric prompt (`psalm/agents/juror.py`'s `_VOTE_SYSTEM_PROMPT` and
  `_format_sub_dimension_rubric`) must not change at all in this plan, and must never mention
  inversion for any sub-dimension — the juror scores every sub-dimension identically regardless
  of `inverse`. This is the core guarantee the design depends on to avoid a double-inversion risk
  (a juror manually compensating for inversion while the code also compensates would cancel out).
- `SubDimension.inverse` defaults to `False`, so every existing sub-dimension across every
  dimension file is unaffected without modification.
- Full suite baseline before this plan: **354 passed, 1 skipped** (verified via
  `python -m pytest tests/ -q`). Confirm this baseline before starting Task 1.

---

### Task 1: Add `SubDimension.inverse`, mark Scènes à Faire's "Creative Elaboration", strip the juror-visible inversion hint

**Files:**
- Modify: `psalm/dimensions/base.py:39-42`
- Modify: `psalm/dimensions/literature/exceptions/scenes_a_faire.py:7-20`
- Modify: `tests/unit/dimensions/test_base.py`
- Modify: `tests/unit/dimensions/test_builtins.py:48-52`
- Modify: `tests/unit/agents/test_juror.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `SubDimension.inverse: bool` (default `False`) — Task 2's `_compute_weighted_score`
  reads this field directly off the `SubDimension` objects already passed into it (no new
  parameters needed there).

- [ ] **Step 1: Write the failing tests**

Baseline for `tests/unit/dimensions/test_base.py` today: **10 passed**. Append these two tests
at the end of the file, bringing it to **12**:

```python
def test_sub_dimension_inverse_defaults_to_false():
    sd = SubDimension(name="Test Sub", description="A test sub-dimension.")
    assert sd.inverse is False


def test_sub_dimension_accepts_inverse():
    sd = SubDimension(name="Test", description="desc", inverse=True)
    assert sd.inverse is True
```

Baseline for `tests/unit/dimensions/test_builtins.py` today: **10 passed**. Replace the existing
`test_scenes_a_faire_creative_elaboration_is_high` test (currently lines 48-52, which looks up
the sub-dimension by its old name and will otherwise keep passing against stale text after Step
3 silently, masking the rename) with:

```python
def test_scenes_a_faire_creative_elaboration_is_high_and_inverse():
    elaboration = next(
        sd for sd in SCENES_A_FAIRE.sub_dimensions if sd.name == "Creative Elaboration"
    )
    assert elaboration.importance == Importance.HIGH
    assert elaboration.inverse is True


def test_scenes_a_faire_creative_elaboration_name_has_no_inverse_suffix():
    # The juror-facing name must not hint at inversion — see Task 1 of the
    # 2026-07-21-subdimension-inversion plan for why.
    names = {sd.name for sd in SCENES_A_FAIRE.sub_dimensions}
    assert "Creative Elaboration (INVERSE)" not in names
    assert "Creative Elaboration" in names


def test_scenes_a_faire_creative_elaboration_description_has_no_inversion_note():
    elaboration = next(
        sd for sd in SCENES_A_FAIRE.sub_dimensions if sd.name == "Creative Elaboration"
    )
    assert "reduces" not in elaboration.description.lower()
    assert "inverse" not in elaboration.description.lower()
```

This brings `test_builtins.py` to **12** (removed 1, added 3).

Baseline for `tests/unit/agents/test_juror.py` today: **29 passed** (per the prior plan's final
state). Append this test at the end of the file, bringing it to **30**:

```python
def test_format_sub_dimension_rubric_carries_no_inversion_hint():
    from psalm.agents.juror import _format_sub_dimension_rubric
    from psalm.dimensions import SCENES_A_FAIRE
    text = _format_sub_dimension_rubric(SCENES_A_FAIRE)
    assert "inverse" not in text.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror" && python -m pytest tests/unit/dimensions/test_base.py tests/unit/dimensions/test_builtins.py tests/unit/agents/test_juror.py -q`
Expected: the 2 new `test_base.py` tests FAIL (`SubDimension` has no `inverse` field yet — a
`TypeError`/validation error on the keyword). The 3 new `test_builtins.py` tests FAIL (the
sub-dimension is still named `"Creative Elaboration (INVERSE)"` with the old description, and has
no `inverse` field). The new `test_juror.py` test FAILS (`_format_sub_dimension_rubric` renders
the old name/description verbatim, which currently contains "INVERSE").

- [ ] **Step 3: Add the `inverse` field to `SubDimension`**

In `psalm/dimensions/base.py`, replace (currently lines 39-42):

```python
class SubDimension(BaseModel):
    name: str
    description: str
    importance: Importance = Importance.MEDIUM
```

with:

```python
class SubDimension(BaseModel):
    name: str
    description: str
    importance: Importance = Importance.MEDIUM
    inverse: bool = False
```

- [ ] **Step 4: Update Scènes à Faire's "Creative Elaboration" sub-dimension**

In `psalm/dimensions/literature/exceptions/scenes_a_faire.py`, replace the first
`SubDimension(...)` entry (currently lines 7-20):

```python
        SubDimension(
            name="Creative Elaboration (INVERSE)",
            description=(
                "Distinctive voice/style (unique authorial tone, specific creative expression "
                "patterns), original descriptive detail (particular sensory richness, unique "
                "observational depth), psychological depth (complex character interiority, "
                "specific emotional nuance), unique dialogue (particular speech patterns, specific "
                "conversational styles), innovative structure (unique narrative architectures, "
                "specific formal experiments), creative worldbuilding (particular imaginative "
                "constructions, unique setting details). Note: HIGH originality reduces scènes à "
                "faire score, indicating more protectable content."
            ),
            importance=Importance.HIGH,
        ),
```

with:

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
            # elaborate -- the strongest possible infringement signal, not scenes-à-faire
            # material. _compute_weighted_score (psalm/phases/deliberation.py) flips this
            # sub-dimension's contribution accordingly. The juror is never told about this --
            # it scores this sub-dimension exactly like any other, using the same
            # pure-textual-similarity rubric (_VOTE_SYSTEM_PROMPT in psalm/agents/juror.py);
            # the inversion is applied only during aggregation, in code.
            inverse=True,
        ),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/dimensions/test_base.py tests/unit/dimensions/test_builtins.py tests/unit/agents/test_juror.py -q`
Expected: `12 passed` (test_base.py), `12 passed` (test_builtins.py), `30 passed` (test_juror.py)

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `359 passed, 1 skipped` (354 baseline + 2 in test_base.py + net +2 in test_builtins.py
[removed 1, added 3] + 1 in test_juror.py = +5; every other test constructs `SubDimension` and
references `SCENES_A_FAIRE` in ways unaffected by this change — confirm this, don't just assume).

- [ ] **Step 7: Commit**

```bash
git add psalm/dimensions/base.py psalm/dimensions/literature/exceptions/scenes_a_faire.py tests/unit/dimensions/test_base.py tests/unit/dimensions/test_builtins.py tests/unit/agents/test_juror.py
git commit -m "feat: add SubDimension.inverse, mark Scenes a Faire's Creative Elaboration"
```

---

### Task 2: Teach `_compute_weighted_score` to flip inverted sub-dimensions

**Files:**
- Modify: `psalm/phases/deliberation.py:205-233`
- Modify: `tests/unit/phases/test_weighted_score.py`

**Interfaces:**
- Consumes: `SubDimension.inverse` (Task 1).
- Produces: nothing new consumed elsewhere — `_compute_weighted_score`'s signature and return
  type (`float`) are unchanged.

- [ ] **Step 1: Write the failing tests**

Baseline for this file today: **5 passed** (verify with
`python -m pytest tests/unit/phases/test_weighted_score.py -q`). Append these three tests at the
end of the file, bringing it to **8**:

```python
def test_inverse_sub_dimension_clear_score_contributes_zero():
    from psalm.dimensions.base import Dimension, Importance, SubDimension
    dim = Dimension(
        name="test-exception",
        description="A test exception dimension with one inverted sub-dimension.",
        dimension_type="exception",
        sub_dimensions=[
            SubDimension(name="Inverted Sub", description="d.", importance=Importance.HIGH, inverse=True),
        ],
    )
    votes = [_vote([("Inverted Sub", SimilarityScore.CLEAR)])]
    score = _compute_weighted_score(votes, dim)
    # clear (avg=3) on an inverted sub-dimension flips to (3 - 3) = 0 contribution.
    assert score == 0.0


def test_inverse_sub_dimension_none_score_contributes_max():
    from psalm.dimensions.base import Dimension, Importance, SubDimension
    dim = Dimension(
        name="test-exception",
        description="A test exception dimension with one inverted sub-dimension.",
        dimension_type="exception",
        sub_dimensions=[
            SubDimension(name="Inverted Sub", description="d.", importance=Importance.HIGH, inverse=True),
        ],
    )
    votes = [_vote([("Inverted Sub", SimilarityScore.NONE)])]
    score = _compute_weighted_score(votes, dim)
    # none (avg=0) on an inverted sub-dimension flips to (3 - 0) = 3 contribution, the max
    # possible for this sub-dimension -- normalised score is 1.0.
    assert abs(score - 1.0) < 1e-6


def test_mixed_normal_and_inverse_sub_dimensions_blend_correctly():
    from psalm.dimensions.base import Dimension, Importance, SubDimension
    dim = Dimension(
        name="test-exception",
        description="A test exception dimension mixing normal and inverted sub-dimensions.",
        dimension_type="exception",
        sub_dimensions=[
            SubDimension(name="Normal Sub", description="d.", importance=Importance.MEDIUM, inverse=False),
            SubDimension(name="Inverted Sub", description="d.", importance=Importance.MEDIUM, inverse=True),
        ],
    )
    votes = [_vote([("Normal Sub", SimilarityScore.CLEAR), ("Inverted Sub", SimilarityScore.CLEAR)])]
    score = _compute_weighted_score(votes, dim)
    # Normal Sub: clear (avg=3) contributes 3 * 1.0 = 3.
    # Inverted Sub: clear (avg=3) flips to (3-3) = 0, contributes 0 * 1.0 = 0.
    # weighted_total = 3, max_possible = 3*1.0 + 3*1.0 = 6 -> normalised = 0.5.
    assert abs(score - 0.5) < 1e-6
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/phases/test_weighted_score.py -q`
Expected: all 3 new tests FAIL — the current implementation always uses `avg` as the
contribution regardless of `inverse`, so `test_inverse_sub_dimension_clear_score_contributes_zero`
gets `1.0` instead of `0.0`, `test_inverse_sub_dimension_none_score_contributes_max` gets `0.0`
instead of `1.0`, and `test_mixed_normal_and_inverse_sub_dimensions_blend_correctly` gets `1.0`
instead of `0.5`.

- [ ] **Step 3: Implement the inversion**

In `psalm/phases/deliberation.py`, inside `_compute_weighted_score` (currently lines 205-233),
replace:

```python
    weighted_total = 0.0
    max_possible = 0.0
    for sub_name, sub_dim in sub_dim_map.items():
        multiplier = _IMPORTANCE_MULTIPLIERS[sub_dim.importance]
        raw_scores = scores_by_sub[sub_name]
        avg = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
        max_score = 3  # SimilarityScore.CLEAR
        weighted_total += avg * multiplier
        max_possible += max_score * multiplier
```

with:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/phases/test_weighted_score.py -q`
Expected: `8 passed`

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `362 passed, 1 skipped` (359 from Task 1 + 3 new). Since `inverse` defaults to `False`
and no other sub-dimension in the codebase sets it to `True`, every other dimension's
`_compute_weighted_score` behavior is provably unchanged by this edit — confirm the count matches
exactly rather than assuming.

- [ ] **Step 6: Commit**

```bash
git add psalm/phases/deliberation.py tests/unit/phases/test_weighted_score.py
git commit -m "fix: flip inverted sub-dimensions' contribution in _compute_weighted_score"
```

---

### Task 3: Full suite and web backend verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full SDK suite**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror" && python -m pytest tests/ -q`
Expected: `362 passed, 1 skipped` (354 baseline + 5 from Task 1 + 3 from Task 2 = 362). If the
actual count differs, trust the actual run and investigate before proceeding.

- [ ] **Step 2: Run the web backend suite (unaffected, confirm no regression)**

Run: `cd examples/web/backend && python -m pytest -q`
Expected: `60 passed` (matches the pre-plan baseline — no file under `examples/web/` is touched by
this plan).

If either run shows unexpected failures, stop and investigate before considering this plan
complete.
