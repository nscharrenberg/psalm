# Exception-Dimension Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Protectability-based defenses (idea-expression dichotomy, unprotectable idea, genre
convention, parody, satire, pastiche, citation) become available only when the case explicitly
selects the matching exception dimension — instead of leaking unconditionally into every
infringement-dimension evaluation — and a selected exception dimension's jury-scored
`weighted_score` now actually discounts the infringement verdict, instead of being purely
informational.

**Architecture:** Four independent, file-scoped fixes: (1) the defense attorney's system prompt
and per-call instruction text stop offering exception-style defenses unconditionally; (2) the
judge's defense-argument validation prompt becomes a function of which exception dimensions are
actually selected for the case; (3) the juror's scoring rubric drops protectability language,
becoming a pure textual/expression-similarity scale; (4) `_aggregate_verdict` blends exception
dimensions' scores the same importance-weighted way infringement dimensions are already blended,
then applies that as a multiplicative discount to the infringement score.

**Tech Stack:** Python 3, Pydantic, pytest (`pytest-asyncio` auto mode — async test functions need
no decorator, matching the existing test files in this repo).

## Global Constraints

- No Pydantic model shape changes anywhere in this plan — `JurorVote`, `DimensionScore`,
  `SimilarityScore`, `DimensionVerdict`, `Argument`, `ArgumentBatch` are all unchanged.
- `SimilarityScore` enum literals stay `none`/`generic`/`possible`/`clear` — only their
  prompt-facing definitions change (per prior discussion; renaming was explicitly rejected to
  avoid rippling into `examples/web/frontend/src/api/types.ts` and existing tests).
- The discount is multiplicative: `effective = normalised * (1 - exception_score)`, where
  `exception_score` is the importance-weighted blend of exception `DimensionVerdict`s (0.0 when
  none are present) — exact formula fixed by prior design discussion, not to be changed during
  implementation.
- Every prompt/instruction edit must preserve existing passing tests in the same file unless a
  task step explicitly says to change that test's assertion — this plan calls out every test that
  needs to change; do not modify any test not named below.
- Full suite baseline before this plan: **327 passed, 1 skipped** (verified via
  `python -m pytest tests/ -q`). Confirm this baseline before starting Task 1.

---

### Task 1: Defense attorney — scope exception-based defenses to selected exception dimensions

**Files:**
- Modify: `psalm/agents/defense.py:78-148`
- Test: `tests/unit/agents/test_defense.py`

**Interfaces:**
- Consumes: nothing new — `Defense.gather_arguments`/`gather_counter_arguments` signatures are
  unchanged; `_format_sub_dimensions` (already dimension-scoped, in this same file) is unchanged.
- Produces: nothing new consumed by other tasks — this task only edits prompt/instruction text.

- [ ] **Step 1: Write the failing tests**

Baseline for this file today: **20 passed** (verify with
`python -m pytest tests/unit/agents/test_defense.py -q`). Add these three tests at the end of
`tests/unit/agents/test_defense.py` (after `test_deliver_closing_argument_empty_case_states_no_evidence`), bringing the file to **23**:

```python
def test_defense_prompt_exception_defenses_are_gated():
    from psalm.agents.defense import _SYSTEM_PROMPT
    assert "EXCEPTION-BASED DEFENSES" in _SYSTEM_PROMPT
    assert "AVAILABLE EXCEPTION TOOLS" in _SYSTEM_PROMPT
    assert "no exception-based defenses in this case" in _SYSTEM_PROMPT.lower()


def test_defense_prompt_primary_tools_no_longer_lead_with_idea_expression():
    from psalm.agents.defense import _SYSTEM_PROMPT
    assert "1. IDEA-EXPRESSION DICHOTOMY" not in _SYSTEM_PROMPT
    assert "1. LACK OF EXPRESSION-LEVEL SIMILARITY" in _SYSTEM_PROMPT


async def test_counter_instruction_does_not_unconditionally_offer_unprotectable_ideas(defense, sample_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[], no_further_arguments=True, closing_statement="Nothing further.")

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_argument], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "unprotectable" not in user_content.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror" && python -m pytest tests/unit/agents/test_defense.py -q`
Expected: the 3 new tests FAIL — `_SYSTEM_PROMPT` still has "1. IDEA-EXPRESSION DICHOTOMY" as its
first tool and no "EXCEPTION-BASED DEFENSES" section; the counter instruction still says
"unprotectable ideas" unconditionally.

- [ ] **Step 3: Rewrite `_SYSTEM_PROMPT`**

In `psalm/agents/defense.py`, replace the entire `_SYSTEM_PROMPT` constant (currently lines 78-118)
with:

```python
_SYSTEM_PROMPT = """\
You are a defense attorney in a copyright infringement case governed by EU copyright law.
Challenge the prosecutor's arguments AND make proactive affirmative claims about the texts.

PRIMARY TOOLS for countering prosecution arguments:

1. LACK OF EXPRESSION-LEVEL SIMILARITY: Even where concepts overlap, show that the specific
   wording, imagery, and narrative choices differ — different words, different details,
   different emotional register.

2. INDEPENDENT CREATION: Show that the specific wording differs enough from the source that
   independent, coincidental arrival at similar content is plausible — i.e. this was not copied.

EXCEPTION-BASED DEFENSES (unprotectable idea / idea-expression dichotomy, genre convention,
parody, satire, pastiche, permitted quotation or citation) are available ONLY when a matching
entry appears under AVAILABLE EXCEPTION TOOLS in the case details below, and must be argued
strictly under that named dimension. If no such entry appears below, you have no exception-based
defenses in this case — rely only on the two tools above and the affirmative arguments below.

AFFIRMATIVE ARGUMENTS — you may also proactively argue why the texts are distinct:
- Point to specific passages where the writing styles, structures, or narrative choices
  diverge significantly, even if the prosecution has not raised those passages.
- Highlight distinctive elements in each text that have no counterpart in the other.
- Argue that the overall creative expression is so different that no reasonable reader
  would confuse the two works.

Only assert claims backed by clear, unambiguous textual evidence. If no such evidence exists for
a prosecution argument or a sub-dimension, do not argue it — omit it. Never present a guess,
inference, or possibility as if it were a settled fact. Quote as closely as possible to the
original; close approximations of the wording are acceptable, but the underlying claim must be
certain, not speculative.

For each prosecution argument, decide: does it rest on an available exception-based defense (see
above — only if applicable), or on specific expression and independent creation (challenge on the
merits)?

If you have nothing further that meets this bar — for this call, across every prosecution
argument and sub-dimension you were asked to address — set no_further_arguments=True and provide
a one-sentence closing_statement explaining why. Do not pad with a weak or speculative claim just
to appear productive.
"""
```

- [ ] **Step 4: Fix the per-call instruction leak in `gather_counter_arguments`**

In `psalm/agents/defense.py`, inside `gather_counter_arguments` (around line 140-148), replace:

```python
        if prosecutor_arguments:
            instruction = (
                "Counter each prosecution argument where you have clear grounds (unprotectable "
                "ideas, lack of expression-level similarity, independent creation). "
                "Additionally, you may make an affirmative argument about why the texts are "
                "independently created — cite specific passages where the expression and "
                "creative choices diverge. If no clear grounds exist anywhere, declare "
                "no_further_arguments."
            )
```

with:

```python
        if prosecutor_arguments:
            instruction = (
                "Counter each prosecution argument where you have clear grounds (lack of "
                "expression-level similarity, independent creation, or an applicable "
                "exception-based defense if one is listed above). "
                "Additionally, you may make an affirmative argument about why the texts are "
                "independently created — cite specific passages where the expression and "
                "creative choices diverge. If no clear grounds exist anywhere, declare "
                "no_further_arguments."
            )
```

(The `else` branch below it, for when `prosecutor_arguments` is empty, is unchanged — it never
mentioned protectability.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_defense.py -q`
Expected: `23 passed`

- [ ] **Step 6: Commit**

```bash
git add psalm/agents/defense.py tests/unit/agents/test_defense.py
git commit -m "fix: scope defense exception-based defenses to selected exception dimensions"
```

---

### Task 2: Judge validation — scope defense-argument legal-insufficiency grounds to selected exception dimensions

**Files:**
- Modify: `psalm/agents/judge.py:1-12,64-143`
- Modify: `psalm/phases/argumentation.py:232-311`
- Test: `tests/unit/agents/test_judge.py`

**Interfaces:**
- Consumes: `Dimension` (from `psalm.dimensions.base`, existing type, unchanged).
- Produces: `Judge.validate_argument` gains a new optional keyword parameter
  `dimensions: list[Dimension] | None = None` (default `None`, meaning "no exception dimensions
  in scope" — existing callers that omit it are unaffected). `_defense_validation_prompt(exception_names: list[str]) -> str` is a new module-level function in `psalm/agents/judge.py`.

- [ ] **Step 1: Write the failing tests**

Baseline for this file today: **21 passed** (verify with
`python -m pytest tests/unit/agents/test_judge.py -q`). Add these four tests at the end of
`tests/unit/agents/test_judge.py`, bringing the file to **25**. First add this import at the top
of the file, alongside the existing imports:

```python
from psalm.dimensions import CHARACTER, SCENES_A_FAIRE
```

Then append:

```python
async def test_defense_validation_rejects_unprotectable_idea_without_exception_dimension(judge):
    from psalm.models.evidence import Argument, Proof
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return ValidationResult(is_valid=False, rejection_reason="No exception dimension selected.")

    arg = Argument(
        claim="This is an unprotectable idea / common archetype.",
        dimension="character",
        proofs=[Proof(source_excerpt="a", target_excerpt="a", relevance="r")],
        agent_role="defense",
        round=1,
    )
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.validate_argument(arg, "a", "a", role="defense", dimensions=[CHARACTER])

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "NO exception dimension is selected" in system_content
    assert "may NOT argue" in system_content


async def test_defense_validation_allows_exception_reasoning_when_dimension_selected(judge):
    from psalm.models.evidence import Argument, Proof
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return ValidationResult(is_valid=True)

    arg = Argument(
        claim="This is scenes à faire / unprotectable idea.",
        dimension="character",
        proofs=[Proof(source_excerpt="a", target_excerpt="a", relevance="r")],
        agent_role="defense",
        round=1,
    )
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.validate_argument(
            arg, "a", "a", role="defense", dimensions=[CHARACTER, SCENES_A_FAIRE],
        )

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "Scènes à Faire" in system_content
    assert "exception dimension(s)" in system_content


async def test_defense_validation_defaults_to_no_exceptions_when_dimensions_omitted(judge, sample_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return ValidationResult(is_valid=True)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.validate_argument(
            sample_argument,
            "The wizard had bright blue eyes.",
            "The sorcerer possessed striking azure irises.",
            role="defense",
        )

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "NO exception dimension is selected" in system_content


async def test_prosecution_validation_ignores_dimensions_argument(judge, sample_argument):
    mock_result = ValidationResult(is_valid=True)
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(
            sample_argument,
            "The wizard had bright blue eyes.",
            "The sorcerer possessed striking azure irises.",
            role="prosecution",
            dimensions=[CHARACTER],
        )
    assert result.is_valid is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_judge.py -q`
Expected: the 4 new tests FAIL — `validate_argument` does not yet accept a `dimensions` parameter
(`TypeError: validate_argument() got an unexpected keyword argument 'dimensions'`).

- [ ] **Step 3: Add the `Dimension` import**

In `psalm/agents/judge.py`, add this import alongside the existing ones at the top of the file:

```python
from psalm.dimensions.base import Dimension
```

- [ ] **Step 4: Rewrite `_DEFENSE_VALIDATION_PROMPT` and add `_defense_validation_prompt`**

Replace the existing `_DEFENSE_VALIDATION_PROMPT` constant (currently lines 64-79) with:

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


def _defense_validation_prompt(exception_names: list[str]) -> str:
    if exception_names:
        names = ", ".join(exception_names)
        clause = (
            f"\nThis case includes the following exception dimension(s): {names}. The defense "
            "may additionally argue legal insufficiency via those specific exceptions only "
            "(e.g. unprotectable idea / genre convention, parody, satire, pastiche, or permitted "
            "quotation/citation — whichever of these match the list above). Reject an argument "
            "that invokes an exception NOT in this list.\n"
        )
    else:
        clause = (
            "\nThis case has NO exception dimension selected. The defense may NOT argue legal "
            "insufficiency via unprotectable ideas, genre conventions, scenes à faire, parody, "
            "satire, pastiche, or citation exceptions — reject any argument that relies solely "
            "on such reasoning. Valid grounds here are differences in specific expression or "
            "independent creation only.\n"
        )
    return _DEFENSE_VALIDATION_PROMPT + clause
```

- [ ] **Step 5: Update `validate_argument`**

In `psalm/agents/judge.py`, replace the `validate_argument` method (currently lines 87-143):

```python
    async def validate_argument(
        self,
        argument: Argument,
        source_text: str,
        target_text: str,
        role: str = "prosecution",
        dimensions: list[Dimension] | None = None,
    ) -> ValidationResult:
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

        structured_llm = self._llm.with_structured_output(ValidationResult)
        if role == "defense":
            exception_names = [
                d.name for d in (dimensions or []) if d.dimension_type == "exception"
            ]
            validation_prompt = _defense_validation_prompt(exception_names)
        else:
            validation_prompt = _PROSECUTION_VALIDATION_PROMPT
        proofs_text = "\n".join(
            f"  Source: '{p.source_excerpt}'\n  Target: '{p.target_excerpt}'\n"
            f"  Relevance: {p.relevance}"
            for p in argument.proofs
        )
        prompt = [
            {"role": "system", "content": validation_prompt},
            {
                "role": "user",
                "content": (
                    f"Argument claim: {argument.claim}\n"
                    f"Dimension: {argument.dimension}\n"
                    f"Proofs (already verified authentic):\n{proofs_text}"
                ),
            },
        ]
        try:
            return await self._call_structured(structured_llm, prompt)
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Judge failed to validate argument.",
                context={"role": self.role, "claim": argument.claim},
                suggestion="Check LLM supports structured output.",
                cause=exc,
            ) from exc
```

- [ ] **Step 6: Thread `dimensions` through the two defense-role call sites in `argumentation.py`**

In `psalm/phases/argumentation.py`, inside `_judge_validate_defense_counter` (currently around
line 237), replace:

```python
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense"
            )
```

with:

```python
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense",
                dimensions=state.dimensions,
            )
```

Inside `_judge_validate_defense` (currently around line 294), replace the identical block with
the identical replacement:

```python
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense",
                dimensions=state.dimensions,
            )
```

The two `role="prosecution"` call sites (around lines 179 and 356) are unchanged.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_judge.py -q`
Expected: `25 passed`

Run: `python -m pytest tests/unit/phases/test_argumentation_phase.py -q`
Expected: unchanged pass count (these tests mock `validate_argument` with a bare
`AsyncMock(return_value=...)` and don't assert on call arguments, so the new keyword argument
does not break them) — confirm with
`python -m pytest tests/unit/phases/test_argumentation_phase.py -q` before and note the count is
identical.

- [ ] **Step 8: Commit**

```bash
git add psalm/agents/judge.py psalm/phases/argumentation.py tests/unit/agents/test_judge.py
git commit -m "fix: scope judge's defense-argument validation to selected exception dimensions"
```

---

### Task 3: Juror rubric — remove protectability language, keep pure textual-similarity scale

**Files:**
- Modify: `psalm/agents/juror.py:11-75`
- Test: `tests/unit/agents/test_juror.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new consumed by other tasks — prompt text only. `SimilarityScore` enum
  literals (`none`/`generic`/`possible`/`clear`) are unchanged.

- [ ] **Step 1: Write the failing tests**

Baseline for this file today: **25 passed** (verify with
`python -m pytest tests/unit/agents/test_juror.py -q`). Add these three tests at the end of
`tests/unit/agents/test_juror.py`, bringing the file to **28**:

```python
def test_vote_rubric_no_longer_mentions_protectability():
    from psalm.agents.juror import _VOTE_SYSTEM_PROMPT
    prompt = _VOTE_SYSTEM_PROMPT.lower()
    assert "unprotectable" not in prompt
    assert "scenes à faire" not in prompt
    assert "archetype" not in prompt


def test_vote_rubric_clear_no_longer_labeled_as_infringement():
    from psalm.agents.juror import _VOTE_SYSTEM_PROMPT
    assert "Clear infringement" not in _VOTE_SYSTEM_PROMPT
    assert "Clear similarity" in _VOTE_SYSTEM_PROMPT


def test_discuss_prompt_no_longer_names_protectability_labels():
    from psalm.agents.juror import _DISCUSS_SYSTEM_PROMPT
    prompt = _DISCUSS_SYSTEM_PROMPT.lower()
    assert "unprotectable" not in prompt
    assert "archetype" not in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_juror.py -q`
Expected: the 3 new tests FAIL — the current rubric still says "generic / unprotectable (scenes
à faire)", "Clear infringement", and the discuss prompt still names "archetype"/"unprotectable
idea".

- [ ] **Step 3: Rewrite `_VOTE_SYSTEM_PROMPT`**

In `psalm/agents/juror.py`, replace the entire `_VOTE_SYSTEM_PROMPT` constant (currently lines
11-55) with:

```python
_VOTE_SYSTEM_PROMPT = """\
You are a juror in a copyright infringement case governed by EU copyright law.
Evaluate the arguments and counter-arguments presented by the prosecution and defense attorneys.
You are a lay evaluator — the attorneys handle legal doctrine; your job is to weigh argument
quality.

The prosecution carries the burden of proof. Ask:
- Did the prosecution present concrete, specific textual similarities?
- Did the defense successfully challenge those arguments (showing they are generic, coincidental,
  or legally insufficient)?
- Which side made stronger, more evidence-grounded arguments?

Weigh the EVIDENCE itself, not just the labels attorneys attach to it:
- Near-verbatim or word-for-word identical wording across a substantial passage (more than a
  handful of words) is direct, strong evidence of expression-level copying. Coincidental
  independent creation of long identical wording is not plausible — score such sub-dimensions
  "clear" unless the defense presents genuine evidence of independent creation, not merely a label.
- A single differing detail (a renamed character, one added phrase or clause) inside an otherwise
  identical or near-identical passage does not make the whole passage distinct. It means that one
  detail differs; the surrounding identical wording remains evidence of copying.
- Reserve "possible" for cases where the wording itself genuinely differs in substantial ways, not
  merely for the presence of any defense rebuttal.

For each sub-dimension you evaluate, apply this RUBRIC — a pure measure of textual/expression
similarity, not a legal conclusion:

| Score  | Label    | Meaning |
|--------|----------|---------|
| none   | No similarity | No meaningful textual/expression similarity found |
| generic | Slight similarity | Only isolated common words or phrasing; not a meaningful shared passage |
| possible | Possible independent creation | The wording itself differs substantially;
independent, coincidental creation is genuinely plausible |
| clear  | Clear similarity | Near-verbatim or identical wording in a substantial passage;
independent creation is not a plausible explanation |

You MUST fill in a DimensionScore for every sub-dimension you are asked to evaluate.

If you have voted in a prior deliberation round, maintain your position unless a fellow juror
made a specific, compelling argument that changes your view — and explain exactly what
persuaded you.
Vote options: "Guilty", "Not Guilty", or "Undecided".
"""
```

- [ ] **Step 4: Trim `_DISCUSS_SYSTEM_PROMPT`**

In `psalm/agents/juror.py`, inside `_DISCUSS_SYSTEM_PROMPT` (currently lines 57-75), replace the
bullet:

```python
- Be skeptical of labels ("generic," "archetype," "unprotectable idea") that aren't backed by
  actually differing wording — identical or near-identical passages are strong evidence regardless
  of how the defense frames them, and a single differing detail does not launder an otherwise
  identical passage into a distinct one.
```

with:

```python
- Be skeptical of any claim of distinctness that isn't backed by actually differing wording —
  identical or near-identical passages are strong evidence regardless of how the defense frames
  them, and a single differing detail does not launder an otherwise identical passage into a
  distinct one.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_juror.py -q`
Expected: `28 passed`

- [ ] **Step 6: Commit**

```bash
git add psalm/agents/juror.py tests/unit/agents/test_juror.py
git commit -m "fix: remove protectability language from juror's textual-similarity rubric"
```

---

### Task 4: Aggregation — make a selected exception dimension's score discount the infringement verdict

**Files:**
- Modify: `psalm/courtroom/default.py:164-207`
- Test: `tests/unit/courtroom/test_verdict_aggregation.py`

**Interfaces:**
- Consumes: `DimensionVerdict` (existing, unchanged shape) — `dimension_type`, `importance`,
  `weighted_score`, `verdict` fields already exist and are already populated for exception
  dimensions today (just previously discarded by `_aggregate_verdict`).
- Produces: a new module-level helper `_blend(verdicts: list[DimensionVerdict]) -> float | None`
  in `psalm/courtroom/default.py`, used by `_aggregate_verdict` and `_synthesize_rationale`.

- [ ] **Step 1: Update the failing/changed tests**

Baseline for this file today: **11 passed** (verify with
`python -m pytest tests/unit/courtroom/test_verdict_aggregation.py -q`).

First, **replace** the existing `test_exception_dimension_excluded_from_aggregation` test
(currently lines 75-91) — its name and comment describe behavior this task intentionally changes
— with these three tests in its place:

```python
def test_exception_dimension_low_score_barely_discounts():
    dvs = [
        _make_dv("character", Importance.HIGH, "Guilty", 0.9),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Not Guilty",
            weighted_score=0.1,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    # 0.9 * (1 - 0.1) = 0.81 — still comfortably above threshold.
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Guilty"


def test_exception_dimension_high_score_flips_verdict_to_not_guilty():
    dvs = [
        _make_dv("character", Importance.HIGH, "Not Guilty", 0.52),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Guilty",
            weighted_score=0.9,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    # 0.52 * (1 - 0.9) = 0.052 — the previously-decorative exception score now genuinely
    # discounts the infringement score, flipping a borderline verdict.
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Not Guilty"


def test_no_exception_dimension_selected_leaves_verdict_unchanged():
    # A single infringement dimension at weighted_score 0.52 with NO exception dimension
    # selected still resolves via the infringement score alone — the discount only applies
    # when the case actually selected an exception dimension.
    dvs = [_make_dv("character", Importance.HIGH, "Not Guilty", 0.52)]
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Guilty"
```

Second, in `test_synthesize_rationale_labels_exception_dimensions` (currently lines 129-146),
change the final assertion from:

```python
    assert "excluded from verdict" in rationale
```

to:

```python
    assert "discounts infringement score" in rationale
```

Third, append this new test at the end of the file:

```python
def test_synthesize_rationale_shows_exception_discount_value():
    dvs = [
        _make_dv("character", Importance.HIGH, "Not Guilty", 0.52),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Guilty",
            weighted_score=0.9,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    rationale = _synthesize_rationale("Not Guilty", dvs)
    assert "Exception discount applied: 0.90" in rationale
```

Every other existing test in this file (`test_aggregate_guilty_when_score_above_threshold`,
`test_aggregate_not_guilty_when_score_below_threshold`,
`test_aggregate_critical_guilty_overrides_low_score`,
`test_aggregate_critical_not_guilty_does_not_override`,
`test_aggregate_empty_verdicts_is_undecided`, `test_aggregate_weighted_by_importance`,
`test_synthesize_rationale_contains_dimension_names`, `test_exception_only_verdicts_is_undecided`,
`test_exception_critical_guilty_does_not_trigger_hard_override`) is unchanged — do not modify
them; verify their assertions still hold under the new `_aggregate_verdict` (they do — none of
them include an exception dimension with a nonzero score alongside a borderline infringement
score, so `effective == normalised` in every one of them).

- [ ] **Step 2: Run the tests to verify the changed/new ones fail**

Run: `python -m pytest tests/unit/courtroom/test_verdict_aggregation.py -q`
Expected: `test_exception_dimension_high_score_flips_verdict_to_not_guilty` FAILS (current code
returns "Guilty" — 0.52 alone is already ≥ 0.5, and today's `_aggregate_verdict` never looks at
the exception dimension at all). `test_synthesize_rationale_labels_exception_dimensions` FAILS
(current rationale still says "excluded from verdict"). `test_synthesize_rationale_shows_exception_discount_value` FAILS (no such line exists yet). The other two replacement tests
(`test_exception_dimension_low_score_barely_discounts`,
`test_no_exception_dimension_selected_leaves_verdict_unchanged`) PASS already — that's expected,
since their specific numbers happen to produce the same result under both the old and new logic;
they still serve as regression coverage for the new code path once it exists.

- [ ] **Step 3: Rewrite `_aggregate_verdict` and add `_blend`**

In `psalm/courtroom/default.py`, replace the `_aggregate_verdict` function (currently lines
164-191) with:

```python
def _aggregate_verdict(
    dimension_verdicts: list[DimensionVerdict],
    guilty_threshold: float,
) -> Literal["Guilty", "Not Guilty", "Undecided"]:
    infringement_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "infringement"]
    if not infringement_verdicts:
        return "Undecided"

    # Hard override: any CRITICAL infringement dimension that is Guilty → overall Guilty.
    # Exception dimensions never trigger this, regardless of their own importance/verdict.
    for dv in infringement_verdicts:
        if dv.importance == Importance.CRITICAL and dv.verdict == "Guilty":
            return "Guilty"

    normalised = _blend(infringement_verdicts)
    if normalised is None:
        return "Undecided"

    exception_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "exception"]
    exception_score = _blend(exception_verdicts)
    if exception_score is None:
        exception_score = 0.0
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

- [ ] **Step 4: Update `_synthesize_rationale`**

In `psalm/courtroom/default.py`, replace the `_synthesize_rationale` function (currently lines
194-207) with:

```python
def _synthesize_rationale(
    verdict: str,
    dimension_verdicts: list[DimensionVerdict],
) -> str:
    lines = [f"Verdict: {verdict}."]
    for dv in dimension_verdicts:
        suffix = (
            "" if dv.dimension_type == "infringement"
            else " [exception, discounts infringement score]"
        )
        lines.append(
            f"  {dv.dimension} [{dv.importance.value}]{suffix}: {dv.verdict} "
            f"(weighted score: {dv.weighted_score:.2f})"
        )
    exception_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "exception"]
    exception_score = _blend(exception_verdicts)
    if exception_score:
        lines.append(f"  Exception discount applied: {exception_score:.2f}")
    return " ".join(lines)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/courtroom/test_verdict_aggregation.py -q`
Expected: `14 passed`

- [ ] **Step 6: Commit**

```bash
git add psalm/courtroom/default.py tests/unit/courtroom/test_verdict_aggregation.py
git commit -m "feat: discount infringement verdict by selected exception dimensions' scores"
```

---

### Task 5: Full suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full suite**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror" && python -m pytest tests/ -q`
Expected: `340 passed, 1 skipped` (327 baseline + 3 from Task 1 + 4 from Task 2 + 3 from Task 3 +
3 net from Task 4).

- [ ] **Step 2: Run the web backend suite (unaffected, confirm no regression)**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror\examples\web\backend" && python -m pytest -q`
Expected: same pass count as before this plan (no files in `examples/web/` were touched) — record
the count and confirm it matches the pre-plan baseline.

If either run shows unexpected failures, stop and investigate before considering this plan
complete — do not proceed to any follow-up work with a red suite.
