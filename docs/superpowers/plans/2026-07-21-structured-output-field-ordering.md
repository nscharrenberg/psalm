# Structured-Output Field Ordering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder every LLM-facing structured-output model so evidence/reasoning fields are
declared before the conclusion field they support, and add one reinforcing sentence to each
prompt that requests one of these models, so the schema order and the prompt's own wording both
push the same direction.

**Architecture:** Six independent, file-scoped edits: model field reorders in
`psalm/models/result.py` and `psalm/models/evidence.py`, a new required `reasoning` field on
`ValidationResult`, and one added sentence to each of five prompts across
`psalm/agents/juror.py`, `psalm/agents/judge.py`, `psalm/agents/defense.py`, and
`psalm/agents/prosecutor.py`.

**Tech Stack:** Python 3, Pydantic v2 (field order in a `BaseModel` does not require
required-before-optional — this codebase already mixes them, e.g. `DimensionVerdict.dimension_type`
has a default and sits before the required `importance` field — so reordering is always safe for
existing keyword-argument construction), pytest.

## Global Constraints

- No runtime logic changes anywhere except `ValidationResult` gaining one new required field
  (`reasoning: str`) and its two production construction sites in `psalm/agents/judge.py`
  supplying it. Every other model's fields keep the same names and types — only declaration
  order changes.
- Every Pydantic model construction in this codebase's production and test code uses keyword
  arguments exclusively (verified across every file this plan touches) — reordering fields is
  therefore safe everywhere except the one new required field, which needs its 16 call sites
  (2 production, 14 test/integration/e2e) updated to supply `reasoning=...`.
- Each reordered model gets exactly one order-assertion regression test:
  `assert list(Model.model_fields) == [...]` in the new order — this is the only test that can
  meaningfully verify this plan's actual change, since reordering does not change any other
  observable behavior. Do not skip these even though the class body edit looks sufficient at a
  glance.
- Full suite baseline before this plan: **343 passed, 1 skipped**
  (`python -m pytest tests/ -q`). Confirm this baseline before starting Task 1.

---

### Task 1: Reorder `DimensionScore` and `JurorVote` (`psalm/models/result.py`)

**Files:**
- Modify: `psalm/models/result.py:43-54`
- Test: `tests/unit/models/test_result.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new consumed by other tasks — field names/types are unchanged, only order.

- [ ] **Step 1: Write the failing tests**

Baseline for this file today: **23 passed** (verify with
`python -m pytest tests/unit/models/test_result.py -q`). Append these two tests at the end of
`tests/unit/models/test_result.py`, bringing the file to **25**:

```python
def test_dimension_score_field_order():
    from psalm.models.result import DimensionScore
    assert list(DimensionScore.model_fields) == ["sub_dimension", "reasoning", "score"]


def test_juror_vote_field_order():
    from psalm.models.result import JurorVote
    assert list(JurorVote.model_fields) == [
        "juror_id", "dimension", "dimension_scores", "rationale", "vote",
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror" && python -m pytest tests/unit/models/test_result.py -q`
Expected: the 2 new tests FAIL — `DimensionScore.model_fields` is currently
`["sub_dimension", "score", "reasoning"]` and `JurorVote.model_fields` is currently
`["juror_id", "vote", "rationale", "dimension_scores", "dimension"]`.

- [ ] **Step 3: Reorder the two classes**

In `psalm/models/result.py`, replace lines 43-54 (the `DimensionScore` and `JurorVote` class
bodies) with:

```python
class DimensionScore(BaseModel):
    sub_dimension: str
    reasoning: str
    score: SimilarityScore


class JurorVote(BaseModel):
    juror_id: str
    dimension: str | None = None
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    rationale: str
    vote: Literal["Guilty", "Not Guilty", "Undecided"]
```

`juror_id` and `dimension` are stamped over by calling code after every LLM call returns
(`psalm/agents/juror.py`'s `Juror.vote()`/`deliberate()` construct the returned `JurorVote` with
`juror_id=self._juror_id`, never the LLM's own value; `vote_all_dimensions()` sets `dimension` via
`.model_copy(update={"dimension": dim.name})`) — they stay first as pure context, not reordered
around the evidence/conclusion pair.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/models/test_result.py -q`
Expected: `25 passed`

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `345 passed, 1 skipped` (343 baseline + 2 new — every other test in the suite
constructs these two models with keyword arguments, so reordering breaks nothing else; confirm
this, don't just assume it).

- [ ] **Step 6: Commit**

```bash
git add psalm/models/result.py tests/unit/models/test_result.py
git commit -m "refactor: reorder DimensionScore/JurorVote fields, reasoning before conclusion"
```

---

### Task 2: Reinforce sequencing in the juror's vote prompt (`psalm/agents/juror.py`)

**Files:**
- Modify: `psalm/agents/juror.py:46-51`
- Test: `tests/unit/agents/test_juror.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — prompt text only.

- [ ] **Step 1: Write the failing test**

Baseline for this file today: **28 passed** (verify with
`python -m pytest tests/unit/agents/test_juror.py -q`). Append this test at the end of
`tests/unit/agents/test_juror.py`, bringing the file to **29**:

```python
def test_vote_prompt_specifies_reasoning_before_vote_order():
    from psalm.agents.juror import _VOTE_SYSTEM_PROMPT
    prompt = _VOTE_SYSTEM_PROMPT.lower()
    assert "score every sub-dimension first" in prompt
    assert "should follow from the rationale you just wrote" in prompt
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/unit/agents/test_juror.py -q`
Expected: the new test FAILS — this sentence does not exist yet in `_VOTE_SYSTEM_PROMPT`.

- [ ] **Step 3: Add the sequencing paragraph**

In `psalm/agents/juror.py`, inside `_VOTE_SYSTEM_PROMPT` (currently lines 11-52), replace:

```python
You MUST fill in a DimensionScore for every sub-dimension you are asked to evaluate.

If you have voted in a prior deliberation round, maintain your position unless a fellow juror
made a specific, compelling argument that changes your view — and explain exactly what
persuaded you.
Vote options: "Guilty", "Not Guilty", or "Undecided".
"""
```

with:

```python
You MUST fill in a DimensionScore for every sub-dimension you are asked to evaluate.

Work in this order: score every sub-dimension first, with reasoning grounded in the evidence
above. Then write your overall rationale, synthesizing those scores. Only after that, cast your
vote — it should follow from the rationale you just wrote, not precede it.

If you have voted in a prior deliberation round, maintain your position unless a fellow juror
made a specific, compelling argument that changes your view — and explain exactly what
persuaded you.
Vote options: "Guilty", "Not Guilty", or "Undecided".
"""
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/unit/agents/test_juror.py -q`
Expected: `29 passed`

- [ ] **Step 5: Commit**

```bash
git add psalm/agents/juror.py tests/unit/agents/test_juror.py
git commit -m "docs: reinforce reasoning-before-vote sequencing in juror vote prompt"
```

---

### Task 3: Reorder `ValidationResult`, add required `reasoning` field, fix every call site

**Files:**
- Modify: `psalm/models/result.py:11-13`
- Modify: `psalm/agents/judge.py:116-132`
- Modify: `tests/unit/models/test_result.py`
- Modify: `tests/unit/agents/test_judge.py`
- Modify: `tests/integration/test_argumentation_phase.py`
- Modify: `tests/integration/test_event_concurrency.py`
- Modify: `tests/e2e/test_full_evaluation.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ValidationResult` gains a new required field `reasoning: str`, declared first. Every
  later task that touches `ValidationResult` (none do) would need to supply it; no later task in
  this plan constructs `ValidationResult` directly.

This task is larger than the others because `reasoning` becomes a required field with no
default — every existing direct construction of `ValidationResult` (2 in production code, 14 in
tests) breaks at construction time until updated. There is no way to land the field without
updating all of them in the same commit; the suite would be red in between.

- [ ] **Step 1: Write the failing test**

Baseline for `tests/unit/models/test_result.py` after Task 1: **25 passed**. Append this test at
the end of the file, bringing it to **26**:

```python
def test_validation_result_field_order():
    from psalm.models.result import ValidationResult
    assert list(ValidationResult.model_fields) == ["reasoning", "is_valid", "rejection_reason"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/unit/models/test_result.py -q`
Expected: the new test FAILS — `ValidationResult.model_fields` is currently
`["is_valid", "rejection_reason"]` (no `reasoning` field at all yet).

- [ ] **Step 3: Reorder `ValidationResult` and add `reasoning`**

In `psalm/models/result.py`, replace lines 11-13:

```python
class ValidationResult(BaseModel):
    is_valid: bool
    rejection_reason: str | None = None
```

with:

```python
class ValidationResult(BaseModel):
    reasoning: str
    is_valid: bool
    rejection_reason: str | None = None
```

- [ ] **Step 4: Fix the two production construction sites**

In `psalm/agents/judge.py`, replace the `for proof in argument.proofs:` loop inside
`validate_argument` (currently lines 116-132):

```python
        for proof in argument.proofs:
            if not is_proof_authentic(proof.source_excerpt, source_text):
                return ValidationResult(
                    is_valid=False,
                    rejection_reason=(
                        "The cited source excerpt does not genuinely appear in the source "
                        f'text: "{proof.source_excerpt}"'
                    ),
                )
            if not is_proof_authentic(proof.target_excerpt, target_text):
                return ValidationResult(
                    is_valid=False,
                    rejection_reason=(
                        "The cited target excerpt does not genuinely appear in the target "
                        f'text: "{proof.target_excerpt}"'
                    ),
                )
```

with:

```python
        for proof in argument.proofs:
            if not is_proof_authentic(proof.source_excerpt, source_text):
                reason = (
                    "The cited source excerpt does not genuinely appear in the source "
                    f'text: "{proof.source_excerpt}"'
                )
                return ValidationResult(reasoning=reason, is_valid=False, rejection_reason=reason)
            if not is_proof_authentic(proof.target_excerpt, target_text):
                reason = (
                    "The cited target excerpt does not genuinely appear in the target "
                    f'text: "{proof.target_excerpt}"'
                )
                return ValidationResult(reasoning=reason, is_valid=False, rejection_reason=reason)
```

(This is a deterministic, non-LLM code path — the check's own reason string is both the
`reasoning` and the `rejection_reason`, so one computed string serves both fields rather than
duplicating the message.)

- [ ] **Step 5: Fix the two remaining `tests/unit/models/test_result.py` sites**

In `tests/unit/models/test_result.py`, replace:

```python
def test_validation_result_valid():
    r = ValidationResult(is_valid=True)
    assert r.rejection_reason is None


def test_validation_result_invalid():
    r = ValidationResult(is_valid=False, rejection_reason="No relevant excerpts provided.")
    assert r.rejection_reason == "No relevant excerpts provided."
```

with:

```python
def test_validation_result_valid():
    r = ValidationResult(reasoning="The proofs support the claim without contradiction.", is_valid=True)
    assert r.rejection_reason is None


def test_validation_result_invalid():
    r = ValidationResult(
        reasoning="No relevant excerpts were provided to support the claim.",
        is_valid=False,
        rejection_reason="No relevant excerpts provided.",
    )
    assert r.rejection_reason == "No relevant excerpts provided."
```

- [ ] **Step 6: Fix the eight `tests/unit/agents/test_judge.py` sites**

In `tests/unit/agents/test_judge.py`, apply these eight replacements (each is a distinct existing
line — replace each exactly once):

Line 42, in `test_validate_argument_accepts_role_parameter`:
```python
    mock_result = ValidationResult(is_valid=True)
```
→
```python
    mock_result = ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
```

Line 57, in `test_validate_argument_valid`:
```python
    mock_result = ValidationResult(is_valid=True)
```
→
```python
    mock_result = ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
```

Line 76, in `test_validate_argument_invalid`:
```python
    mock_result = ValidationResult(is_valid=False, rejection_reason="Proof contradicts the claim.")
```
→
```python
    mock_result = ValidationResult(
        reasoning="The cited proof shows the opposite of what the claim asserts.",
        is_valid=False,
        rejection_reason="Proof contradicts the claim.",
    )
```

Line 131, in `test_validate_argument_prompt_has_no_full_text_access`'s `capture_invoke`:
```python
        return ValidationResult(is_valid=True)
```
→
```python
        return ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
```

Line 259, in `test_defense_validation_rejects_unprotectable_idea_without_exception_dimension`'s
`capture_invoke`:
```python
        return ValidationResult(is_valid=False, rejection_reason="No exception dimension selected.")
```
→
```python
        return ValidationResult(
            reasoning="No exception dimension covers this argument.",
            is_valid=False,
            rejection_reason="No exception dimension selected.",
        )
```

Line 284, in `test_defense_validation_allows_exception_reasoning_when_dimension_selected`'s
`capture_invoke`:
```python
        return ValidationResult(is_valid=True)
```
→
```python
        return ValidationResult(reasoning="The exception dimension covers this argument.", is_valid=True)
```

Line 310, in `test_defense_validation_defaults_to_no_exceptions_when_dimensions_omitted`'s
`capture_invoke`:
```python
        return ValidationResult(is_valid=True)
```
→
```python
        return ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
```

Line 327, in `test_prosecution_validation_ignores_dimensions_argument`:
```python
    mock_result = ValidationResult(is_valid=True)
```
→
```python
    mock_result = ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
```

- [ ] **Step 7: Fix the two `tests/integration/test_argumentation_phase.py` sites**

In `tests/integration/test_argumentation_phase.py`, replace:

```python
    judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=True))
```
with:
```python
    judge.validate_argument = AsyncMock(
        return_value=ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
    )
```

and replace:
```python
    mock_judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=False, rejection_reason="No excerpts."))
```
with:
```python
    mock_judge.validate_argument = AsyncMock(
        return_value=ValidationResult(
            reasoning="No excerpts were provided.", is_valid=False, rejection_reason="No excerpts.",
        )
    )
```

- [ ] **Step 8: Fix the `tests/integration/test_event_concurrency.py` site**

In `tests/integration/test_event_concurrency.py`, replace:
```python
        patch("psalm.agents.judge.Judge.validate_argument", new=AsyncMock(return_value=ValidationResult(is_valid=True))),
```
with:
```python
        patch(
            "psalm.agents.judge.Judge.validate_argument",
            new=AsyncMock(
                return_value=ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
            ),
        ),
```

- [ ] **Step 9: Fix the `tests/e2e/test_full_evaluation.py` site**

In `tests/e2e/test_full_evaluation.py`, replace:
```python
            new=AsyncMock(return_value=ValidationResult(is_valid=True)),
```
with:
```python
            new=AsyncMock(
                return_value=ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
            ),
```

- [ ] **Step 10: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `347 passed, 1 skipped` (346 after Task 2 + 1 new order-assertion test; the 16 fixed
call sites keep their existing tests passing rather than adding new ones).

- [ ] **Step 11: Commit**

```bash
git add psalm/models/result.py psalm/agents/judge.py tests/unit/models/test_result.py tests/unit/agents/test_judge.py tests/integration/test_argumentation_phase.py tests/integration/test_event_concurrency.py tests/e2e/test_full_evaluation.py
git commit -m "refactor: add required reasoning field to ValidationResult, before is_valid"
```

---

### Task 4: Reorder `_TiebreakDecision`, reinforce sequencing in judge prompts (`psalm/agents/judge.py`)

**Files:**
- Modify: `psalm/agents/judge.py` (constant `_TiebreakDecision`, `_PROSECUTION_VALIDATION_PROMPT`,
  `_DEFENSE_VALIDATION_PROMPT`, `tiebreak()`'s inline `system_content`)
- Test: `tests/unit/agents/test_judge.py`

**Interfaces:**
- Consumes: `minimal_argumentation_log` fixture (already used elsewhere in this test file, defined
  in `tests/conftest.py`).
- Produces: nothing new — field order and prompt text only.

- [ ] **Step 1: Write the failing tests**

Baseline for this file after Task 3: **25 passed** (Task 3 only fixed existing call sites, it
added no new tests to this file). Append these four tests at the end of
`tests/unit/agents/test_judge.py`, bringing the file to **29**:

```python
def test_tiebreak_decision_field_order():
    from psalm.agents.judge import _TiebreakDecision
    assert list(_TiebreakDecision.model_fields) == ["rationale", "verdict"]


def test_prosecution_validation_prompt_specifies_reasoning_before_conclusion():
    from psalm.agents.judge import _PROSECUTION_VALIDATION_PROMPT
    prompt = _PROSECUTION_VALIDATION_PROMPT.lower()
    assert "state your reasoning first" in prompt


def test_defense_validation_prompt_specifies_reasoning_before_conclusion():
    from psalm.agents.judge import _DEFENSE_VALIDATION_PROMPT
    prompt = _DEFENSE_VALIDATION_PROMPT.lower()
    assert "state your reasoning first" in prompt


async def test_tiebreak_prompt_specifies_reasoning_before_verdict(judge, minimal_argumentation_log):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(rationale="r.", verdict="Guilty")

    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Strong evidence."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Weak similarity."),
    ]
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.tiebreak(votes, minimal_argumentation_log)

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "explain your reasoning before stating the verdict" in system_content.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_judge.py -q`
Expected: all 4 new tests FAIL — `_TiebreakDecision.model_fields` is currently
`["verdict", "rationale"]`; neither validation prompt contains "state your reasoning first"; the
tiebreak system prompt doesn't contain "explain your reasoning before stating the verdict".

- [ ] **Step 3: Reorder `_TiebreakDecision`**

In `psalm/agents/judge.py`, replace (currently lines 46-48):

```python
class _TiebreakDecision(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str
```

with:

```python
class _TiebreakDecision(BaseModel):
    rationale: str
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
```

- [ ] **Step 4: Add the sequencing sentence to both validation prompts**

Replace the end of `_PROSECUTION_VALIDATION_PROMPT` (currently lines 51-63):

```python
_PROSECUTION_VALIDATION_PROMPT = """\
You are a judge validating a prosecution argument in a copyright case governed by EU copyright law.
The cited proofs have already been verified as authentic (they genuinely appear in the source and
target text) — you do not need to and cannot re-check that; you are not shown the full text.

Reject the argument (is_valid=false) ONLY if the cited proofs contradict the claim they are
offered to support — e.g. a claim of similarity is not backed by proofs that actually correspond,
or an unrelated or opposite relationship is presented as if it supports the claim.

Do NOT reject for weak, interpretive, idea-level, or thematic reasoning, and do NOT reject merely
because a proof does not by itself sufficiently "prove" or "establish" the claim — argument
strength and sufficiency are for the opposing side to challenge, not grounds for you to reject.
"""
```

with:

```python
_PROSECUTION_VALIDATION_PROMPT = """\
You are a judge validating a prosecution argument in a copyright case governed by EU copyright law.
The cited proofs have already been verified as authentic (they genuinely appear in the source and
target text) — you do not need to and cannot re-check that; you are not shown the full text.

Reject the argument (is_valid=false) ONLY if the cited proofs contradict the claim they are
offered to support — e.g. a claim of similarity is not backed by proofs that actually correspond,
or an unrelated or opposite relationship is presented as if it supports the claim.

Do NOT reject for weak, interpretive, idea-level, or thematic reasoning, and do NOT reject merely
because a proof does not by itself sufficiently "prove" or "establish" the claim — argument
strength and sufficiency are for the opposing side to challenge, not grounds for you to reject.

State your reasoning first, then decide is_valid based on that reasoning — not the other way
around.
"""
```

Replace the end of `_DEFENSE_VALIDATION_PROMPT` (currently lines 65-79):

```python
_DEFENSE_VALIDATION_PROMPT = """\
You are a judge validating a defense argument in a copyright case governed by EU copyright law.
The cited proofs have already been verified as authentic (they genuinely appear in the source and
target text) — you do not need to and cannot re-check that; you are not shown the full text.

Reject the argument (is_valid=false) ONLY if the cited proofs contradict the claim they are
offered to support. In particular: if the claim asserts the texts are distinct or independently
created, an identical (or near-identical) passage in both texts is evidence of similarity, not
distinctness — such a proof undermines rather than supports the claim and must be rejected.

Defense arguments may challenge prosecution claims by showing differences in specific expression,
arguing independent creation, or making affirmative claims about the texts' distinctiveness. The
defense carries no burden to show similarity — that is the prosecution's alone. Do NOT reject for
weak or interpretive reasoning — that is the prosecution's job to challenge, not yours to discard.
"""
```

with:

```python
_DEFENSE_VALIDATION_PROMPT = """\
You are a judge validating a defense argument in a copyright case governed by EU copyright law.
The cited proofs have already been verified as authentic (they genuinely appear in the source and
target text) — you do not need to and cannot re-check that; you are not shown the full text.

Reject the argument (is_valid=false) ONLY if the cited proofs contradict the claim they are
offered to support. In particular: if the claim asserts the texts are distinct or independently
created, an identical (or near-identical) passage in both texts is evidence of similarity, not
distinctness — such a proof undermines rather than supports the claim and must be rejected.

Defense arguments may challenge prosecution claims by showing differences in specific expression,
arguing independent creation, or making affirmative claims about the texts' distinctiveness. The
defense carries no burden to show similarity — that is the prosecution's alone. Do NOT reject for
weak or interpretive reasoning — that is the prosecution's job to challenge, not yours to discard.

State your reasoning first, then decide is_valid based on that reasoning — not the other way
around.
"""
```

(`_defense_validation_prompt(exception_names)` appends its own clause after
`_DEFENSE_VALIDATION_PROMPT` — that function is unchanged; the new sentence lands in the base
text before that appended clause, unaffected.)

- [ ] **Step 5: Add the sequencing sentence to the tiebreak system prompt**

In `psalm/agents/judge.py`'s `tiebreak()` method, replace:

```python
        system_content = (
            "You are a judge casting a tiebreaker vote in a copyright case. Base your "
            "decision on the totality of the evidence and arguments."
        )
```

with:

```python
        system_content = (
            "You are a judge casting a tiebreaker vote in a copyright case. Base your "
            "decision on the totality of the evidence and arguments. Explain your reasoning "
            "before stating the verdict — the verdict should follow from the reasoning, not "
            "precede it."
        )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_judge.py -q`
Expected: `29 passed`

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `351 passed, 1 skipped` (347 from Task 3 + 4 new).

- [ ] **Step 8: Commit**

```bash
git add psalm/agents/judge.py tests/unit/agents/test_judge.py
git commit -m "refactor: reorder _TiebreakDecision, reinforce reasoning-before-conclusion in judge prompts"
```

---

### Task 5: Reorder `Argument` (`psalm/models/evidence.py`)

**Files:**
- Modify: `psalm/models/evidence.py:14-31`
- Test: `tests/unit/models/test_evidence.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new consumed by other tasks — field names/types unchanged, only order.

- [ ] **Step 1: Write the failing test**

Baseline for this file today: **11 passed** (verify with
`python -m pytest tests/unit/models/test_evidence.py -q`). Append this test at the end of the
file, bringing it to **12**:

```python
def test_argument_field_order():
    from psalm.models.evidence import Argument
    assert list(Argument.model_fields) == ["dimension", "proofs", "claim", "agent_role", "round"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/unit/models/test_evidence.py -q`
Expected: the new test FAILS — `Argument.model_fields` is currently
`["claim", "dimension", "proofs", "agent_role", "round"]`.

- [ ] **Step 3: Reorder the class**

In `psalm/models/evidence.py`, replace lines 14-19 (the field declarations only — the
`validate_proofs` validator below them is unchanged, it references `"proofs"` by name and does
not care about declaration order):

```python
class Argument(BaseModel):
    claim: str
    dimension: str
    proofs: list[Proof]
    agent_role: str
    round: int
```

with:

```python
class Argument(BaseModel):
    dimension: str
    proofs: list[Proof]
    claim: str
    agent_role: str
    round: int
```

`agent_role` and `round` are stamped over by calling code after every LLM call returns (every
call site in `psalm/agents/defense.py`/`psalm/agents/prosecutor.py` does
`.model_copy(update={"round": round, "agent_role": "..."})`) — they stay last, unchanged, exactly
like `JurorVote`'s `juror_id`/`dimension` in Task 1.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/unit/models/test_evidence.py -q`
Expected: `12 passed`

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `352 passed, 1 skipped` (351 from Task 4 + 1 new).

- [ ] **Step 6: Commit**

```bash
git add psalm/models/evidence.py tests/unit/models/test_evidence.py
git commit -m "refactor: reorder Argument fields, proofs before the claim they support"
```

---

### Task 6: Reinforce proof-before-claim sequencing in prosecutor/defense prompts

**Files:**
- Modify: `psalm/agents/defense.py:78-118`
- Modify: `psalm/agents/prosecutor.py:78-106`
- Test: `tests/unit/agents/test_defense.py`
- Test: `tests/unit/agents/test_prosecutor.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — prompt text only.

- [ ] **Step 1: Write the failing tests**

Baseline today: `test_defense.py` **23 passed**, `test_prosecutor.py` **19 passed** (verify with
`python -m pytest tests/unit/agents/test_defense.py tests/unit/agents/test_prosecutor.py -q`).

Append to the end of `tests/unit/agents/test_defense.py` (bringing it to **24**):

```python
def test_defense_prompt_specifies_proof_before_claim_order():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "identify the specific textual proof first" in prompt
```

Append to the end of `tests/unit/agents/test_prosecutor.py` (bringing it to **20**):

```python
def test_prosecutor_prompt_specifies_proof_before_claim_order():
    from psalm.agents.prosecutor import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "identify the specific textual proof first" in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_defense.py tests/unit/agents/test_prosecutor.py -q`
Expected: both new tests FAIL — neither `_SYSTEM_PROMPT` contains this sentence yet.

- [ ] **Step 3: Add the sentence to defense.py's `_SYSTEM_PROMPT`**

In `psalm/agents/defense.py`, replace:

```python
Only assert claims backed by clear, unambiguous textual evidence. If no such evidence exists for
a prosecution argument or a sub-dimension, do not argue it — omit it. Never present a guess,
inference, or possibility as if it were a settled fact. Quote as closely as possible to the
original; close approximations of the wording are acceptable, but the underlying claim must be
certain, not speculative.

For each prosecution argument, decide: does it rest on an available exception-based defense (see
above — only if applicable), or on specific expression and independent creation (challenge on the
merits)?
```

with:

```python
Only assert claims backed by clear, unambiguous textual evidence. If no such evidence exists for
a prosecution argument or a sub-dimension, do not argue it — omit it. Never present a guess,
inference, or possibility as if it were a settled fact. Quote as closely as possible to the
original; close approximations of the wording are acceptable, but the underlying claim must be
certain, not speculative.

For each argument, identify the specific textual proof first, then state the claim that proof
supports — not the other way around.

For each prosecution argument, decide: does it rest on an available exception-based defense (see
above — only if applicable), or on specific expression and independent creation (challenge on the
merits)?
```

- [ ] **Step 4: Add the sentence to prosecutor.py's `_SYSTEM_PROMPT`**

In `psalm/agents/prosecutor.py`, replace:

```python
Only assert claims backed by clear, unambiguous textual evidence. If no such evidence exists for
a sub-dimension, do not argue it — omit it. Never present a guess, inference, or possibility as
if it were a settled fact. Quote as closely as possible to the original; close approximations of
the wording are acceptable, but the underlying claim of similarity must be certain, not
speculative.

If you have nothing further that meets this bar — for this call, across every sub-dimension you
were asked to address — set no_further_arguments=True and provide a one-sentence
closing_statement explaining why (e.g. "All HIGH and CRITICAL sub-dimensions have been argued
with the available evidence" or "No further unambiguous similarities remain in the text"). Do
not pad with a weak or speculative claim just to appear productive.
If you are rebutting defense arguments from prior rounds, directly address their challenge.
```

with:

```python
Only assert claims backed by clear, unambiguous textual evidence. If no such evidence exists for
a sub-dimension, do not argue it — omit it. Never present a guess, inference, or possibility as
if it were a settled fact. Quote as closely as possible to the original; close approximations of
the wording are acceptable, but the underlying claim of similarity must be certain, not
speculative.

For each argument, identify the specific textual proof first, then state the claim that proof
supports — not the other way around.

If you have nothing further that meets this bar — for this call, across every sub-dimension you
were asked to address — set no_further_arguments=True and provide a one-sentence
closing_statement explaining why (e.g. "All HIGH and CRITICAL sub-dimensions have been argued
with the available evidence" or "No further unambiguous similarities remain in the text"). Do
not pad with a weak or speculative claim just to appear productive.
If you are rebutting defense arguments from prior rounds, directly address their challenge.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_defense.py tests/unit/agents/test_prosecutor.py -q`
Expected: `24 passed` and `20 passed` respectively.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `354 passed, 1 skipped` (352 from Task 5 + 2 new).

- [ ] **Step 7: Commit**

```bash
git add psalm/agents/defense.py psalm/agents/prosecutor.py tests/unit/agents/test_defense.py tests/unit/agents/test_prosecutor.py
git commit -m "docs: reinforce proof-before-claim sequencing in prosecutor/defense prompts"
```

---

### Task 7: Full suite and web backend verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full SDK suite**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror" && python -m pytest tests/ -q`
Expected: `354 passed, 1 skipped` (343 baseline + 2 from Task 1 + 1 from Task 2 + 1 from Task 3 +
4 from Task 4 + 1 from Task 5 + 2 from Task 6 = 354). If the actual count differs, trust the
actual run and investigate the discrepancy before proceeding.

- [ ] **Step 2: Run the web backend suite (unaffected, confirm no regression)**

Run: `cd examples/web/backend && python -m pytest -q`
Expected: `60 passed` (matches the pre-plan baseline — no file under `examples/web/` is touched
by this plan).

If either run shows unexpected failures, stop and investigate before considering this plan
complete.
