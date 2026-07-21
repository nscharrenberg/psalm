# Exception-Dimension Vote Framing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the juror's and judge's own reasoning correctly framed as "does this exception
apply" (not "is this guilty of infringement") when scoring or tiebreaking an exception dimension,
without changing any stored vote value, type, or downstream consumer.

**Architecture:** Two prompt-only conditional additions (juror's sub-dimension rubric, judge's
tiebreak prompt), plus threading an optional `dimension` parameter through the
`VotingStrategy.apply()` interface so the judge's tiebreak call can receive it from
`psalm/phases/deliberation.py`'s existing voting-strategy loop.

**Tech Stack:** Python 3, pytest.

## Global Constraints

- No stored vote value, Pydantic model field, or type changes anywhere. `JurorVote.vote`,
  `DimensionVerdict.verdict`, `_TiebreakDecision`, `_aggregate_verdict`, and the web API shape all
  stay exactly as they are today — only prompt text changes, conditioned on
  `dimension.dimension_type`.
- Every new parameter (`dimension` on `Judge.tiebreak` and on every `VotingStrategy.apply`
  implementation) is optional with a `None` default — no existing call site, production or test,
  should need to change to keep passing.
- For an infringement dimension (or no `dimension` at all), every changed prompt must produce
  byte-identical output to today — the new conditional block only fires for
  `dimension_type == "exception"`.
- Full suite baseline before this plan: **362 passed, 1 skipped** (verified via
  `python -m pytest tests/ -q`). Confirm this baseline before starting Task 1.

---

### Task 1: Exception framing in the juror's sub-dimension rubric

**Files:**
- Modify: `psalm/agents/juror.py:157-161`
- Test: `tests/unit/agents/test_juror.py`

**Interfaces:**
- Consumes: `Dimension.dimension_type` (already exists).
- Produces: nothing new consumed elsewhere — `_format_sub_dimension_rubric`'s signature and
  return type (`str`) are unchanged.

- [ ] **Step 1: Write the failing tests**

Baseline for this file today: **30 passed** (verify with
`python -m pytest tests/unit/agents/test_juror.py -q`). Append these two tests at the end of
`tests/unit/agents/test_juror.py`, bringing the file to **32**:

```python
def test_format_sub_dimension_rubric_infringement_has_no_exception_framing():
    from psalm.agents.juror import _format_sub_dimension_rubric
    from psalm.dimensions import CHARACTER
    text = _format_sub_dimension_rubric(CHARACTER)
    assert "EXCEPTION dimension" not in text


def test_format_sub_dimension_rubric_exception_has_exception_framing():
    from psalm.agents.juror import _format_sub_dimension_rubric
    from psalm.dimensions import SCENES_A_FAIRE
    text = _format_sub_dimension_rubric(SCENES_A_FAIRE)
    assert "EXCEPTION dimension" in text
    assert 'Vote "Guilty" if the exception applies' in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror" && python -m pytest tests/unit/agents/test_juror.py -q`
Expected: the second new test FAILS (`_format_sub_dimension_rubric` doesn't mention "EXCEPTION
dimension" for any dimension yet). The first new test already passes against today's code (there
is no such text anywhere yet) — that's expected, it becomes a real regression guard once Step 3
lands.

- [ ] **Step 3: Add the conditional framing**

In `psalm/agents/juror.py`, replace `_format_sub_dimension_rubric` (currently lines 157-161):

```python
def _format_sub_dimension_rubric(dimension: Dimension) -> str:
    lines = [f"Dimension: {dimension.name} — {dimension.description}", "Sub-dimensions to score:"]
    for sd in dimension.sub_dimensions:
        lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")
    return "\n".join(lines)
```

with:

```python
def _format_sub_dimension_rubric(dimension: Dimension) -> str:
    lines = [f"Dimension: {dimension.name} — {dimension.description}"]
    if dimension.dimension_type == "exception":
        lines.append(
            "This is an EXCEPTION dimension, not an infringement dimension: you are not "
            "deciding whether the target text infringes copyright here. You are deciding "
            "whether this specific legal exception applies to the shared content. Vote "
            "\"Guilty\" if the exception applies, \"Not Guilty\" if it does not."
        )
    lines.append("Sub-dimensions to score:")
    for sd in dimension.sub_dimensions:
        lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_juror.py -q`
Expected: `32 passed`

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `364 passed, 1 skipped` (362 baseline + 2 new — the new block only fires for
`dimension_type == "exception"`, so every existing test using `CHARACTER`/`PLOT` and every other
infringement dimension produces byte-identical prompt text; confirm this, don't just assume).

- [ ] **Step 6: Commit**

```bash
git add psalm/agents/juror.py tests/unit/agents/test_juror.py
git commit -m "feat: frame exception-dimension sub-dimension rubric as an exception question"
```

---

### Task 2: Exception framing in the judge's tiebreak prompt

**Files:**
- Modify: `psalm/agents/judge.py:185-213`
- Test: `tests/unit/agents/test_judge.py`

**Interfaces:**
- Consumes: `Dimension.dimension_type` (already exists).
- Produces: `Judge.tiebreak` gains a new optional keyword parameter
  `dimension: Dimension | None = None` (default `None`, meaning "no exception framing" — existing
  callers that omit it are unaffected). Task 3's `JudgeTiebreakerVoting.apply` will call
  `judge.tiebreak(votes, argumentation_log, dimension=dimension)`.

- [ ] **Step 1: Write the failing tests**

Baseline for this file today: **29 passed** (verify with
`python -m pytest tests/unit/agents/test_judge.py -q`). This file already imports `CHARACTER` and
`SCENES_A_FAIRE` from `psalm.dimensions` at the top — no new imports needed. Append these three
tests at the end of `tests/unit/agents/test_judge.py`, bringing the file to **32**:

```python
async def test_tiebreak_infringement_dimension_has_no_exception_framing(judge, minimal_argumentation_log):
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
        await judge.tiebreak(votes, minimal_argumentation_log, dimension=CHARACTER)

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "EXCEPTION dimension" not in system_content


async def test_tiebreak_no_dimension_has_no_exception_framing(judge, minimal_argumentation_log):
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
    assert "EXCEPTION dimension" not in system_content


async def test_tiebreak_exception_dimension_has_exception_framing(judge, minimal_argumentation_log):
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
        await judge.tiebreak(votes, minimal_argumentation_log, dimension=SCENES_A_FAIRE)

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "EXCEPTION dimension" in system_content
    assert 'Cast "Guilty" if the exception applies' in system_content
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_judge.py -q`
Expected: `test_tiebreak_infringement_dimension_has_no_exception_framing` and
`test_tiebreak_exception_dimension_has_exception_framing` FAIL — `tiebreak()` doesn't accept a
`dimension` keyword argument yet (`TypeError`). `test_tiebreak_no_dimension_has_no_exception_framing`
already passes against today's code (no such text exists yet) — expected, becomes a real
regression guard once Step 3 lands.

- [ ] **Step 3: Add the `dimension` parameter and conditional framing**

In `psalm/agents/judge.py`, replace the `tiebreak` method (currently lines 185-213):

```python
    async def tiebreak(
        self, votes: list[JurorVote], argumentation_log: ArgumentationLog
    ) -> Literal["Guilty", "Not Guilty", "Undecided"]:
        structured_llm = self._llm.with_structured_output(_TiebreakDecision)
        votes_text = "\n".join(f"- {v.juror_id}: {v.vote} — {v.rationale}" for v in votes)
        rounds_text = "\n".join(
            f"Round {r.round}: {len(r.prosecution_arguments)} prosecution arguments, "
            f"{len(r.defense_counters)} defense counters, "
            f"{len(r.defense_arguments)} defense arguments, "
            f"{len(r.prosecution_counters)} prosecution counters"
            for r in argumentation_log.rounds
        )
        system_content = (
            "You are a judge casting a tiebreaker vote in a copyright case. Base your "
            "decision on the totality of the evidence and arguments. Explain your reasoning "
            "before stating the verdict — the verdict should follow from the reasoning, not "
            "precede it."
        )
        user_content = (
            f"Jury votes (tied):\n{votes_text}\n\nArgumentation summary:\n{rounds_text}\n\n"
            "Cast your tiebreaker verdict."
        )
        prompt = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.verdict
        except Exception:
            return "Undecided"  # safe fallback
```

with:

```python
    async def tiebreak(
        self,
        votes: list[JurorVote],
        argumentation_log: ArgumentationLog,
        dimension: Dimension | None = None,
    ) -> Literal["Guilty", "Not Guilty", "Undecided"]:
        structured_llm = self._llm.with_structured_output(_TiebreakDecision)
        votes_text = "\n".join(f"- {v.juror_id}: {v.vote} — {v.rationale}" for v in votes)
        rounds_text = "\n".join(
            f"Round {r.round}: {len(r.prosecution_arguments)} prosecution arguments, "
            f"{len(r.defense_counters)} defense counters, "
            f"{len(r.defense_arguments)} defense arguments, "
            f"{len(r.prosecution_counters)} prosecution counters"
            for r in argumentation_log.rounds
        )
        system_content = (
            "You are a judge casting a tiebreaker vote in a copyright case. Base your "
            "decision on the totality of the evidence and arguments. Explain your reasoning "
            "before stating the verdict — the verdict should follow from the reasoning, not "
            "precede it."
        )
        if dimension is not None and dimension.dimension_type == "exception":
            system_content += (
                "\n\nThis is an EXCEPTION dimension, not an infringement dimension: you are not "
                "deciding whether the target text infringes copyright here. You are deciding "
                "whether this specific legal exception applies to the shared content. Cast "
                "\"Guilty\" if the exception applies, \"Not Guilty\" if it does not."
            )
        user_content = (
            f"Jury votes (tied):\n{votes_text}\n\nArgumentation summary:\n{rounds_text}\n\n"
            "Cast your tiebreaker verdict."
        )
        prompt = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.verdict
        except Exception:
            return "Undecided"  # safe fallback
```

`Dimension` is already imported in this file (`from psalm.dimensions.base import Dimension`) —
no new import needed.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_judge.py -q`
Expected: `32 passed`

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `367 passed, 1 skipped` (364 from Task 1 + 3 new).

- [ ] **Step 6: Commit**

```bash
git add psalm/agents/judge.py tests/unit/agents/test_judge.py
git commit -m "feat: frame exception-dimension tiebreak as an exception question"
```

---

### Task 3: Thread `dimension` through the voting-strategy chain

**Files:**
- Modify: `psalm/voting/base.py:16-20`
- Modify: `psalm/voting/simple_majority.py:10-13`
- Modify: `psalm/voting/trust_weighted.py:14-17`
- Modify: `psalm/voting/judge_tiebreaker.py:10-16`
- Modify: `psalm/phases/deliberation.py:165-168`
- Test: `tests/unit/voting/test_judge_tiebreaker.py`
- Test: `tests/unit/voting/test_simple_majority.py`
- Test: `tests/unit/voting/test_trust_weighted.py`

**Interfaces:**
- Consumes: `Judge.tiebreak(votes, argumentation_log, dimension=...)` (Task 2).
- Produces: `VotingStrategy.apply` (and all three implementations) gain a new optional
  `dimension: Any = None` parameter, appended last. `_apply_voting_strategy` passes
  `state.current_dimension` (already a live `Dimension` object at this point in the graph, the
  same one `_jury_vote` already passes to every `juror.vote(dimension=...)` call earlier in the
  same run) as the 4th positional argument to every `strategy.apply(...)` call.

- [ ] **Step 1: Write the failing tests**

Baseline today: `tests/unit/voting/test_judge_tiebreaker.py` **3 passed**,
`tests/unit/voting/test_simple_majority.py` **5 passed**,
`tests/unit/voting/test_trust_weighted.py` **3 passed** (verify with
`python -m pytest tests/unit/voting/ -q`).

Append this test at the end of `tests/unit/voting/test_judge_tiebreaker.py`, bringing it to **4**:

```python
async def test_tiebreaker_forwards_dimension_to_judge(strategy, mock_judge, minimal_argumentation_log):
    from psalm.dimensions import SCENES_A_FAIRE
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="r1"),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="r2"),
    ]
    await strategy.apply(
        votes, judge=mock_judge, argumentation_log=minimal_argumentation_log,
        dimension=SCENES_A_FAIRE,
    )
    mock_judge.tiebreak.assert_called_once_with(
        votes, minimal_argumentation_log, dimension=SCENES_A_FAIRE,
    )
```

Append this test at the end of `tests/unit/voting/test_simple_majority.py`, bringing it to **6**:

```python
async def test_apply_accepts_dimension_argument(strategy):
    from psalm.dimensions import CHARACTER
    votes = [
        JurorVote(juror_id=f"j{i}", vote="Guilty", rationale="Clear infringement.")
        for i in range(3)
    ]
    result = await strategy.apply(votes, judge=None, dimension=CHARACTER)
    assert result.verdict == "Guilty"
    assert result.is_tie is False
```

Append this test at the end of `tests/unit/voting/test_trust_weighted.py`, bringing it to **4**:

```python
async def test_apply_accepts_dimension_argument(strategy):
    from psalm.dimensions import CHARACTER
    votes = [
        JurorVote(
            juror_id=f"j{i}",
            vote="Guilty",
            rationale="The characters share blue eyes, silver cloaks, and a mentor relationship.",
        )
        for i in range(3)
    ]
    result = await strategy.apply(votes, judge=None, dimension=CHARACTER)
    assert result.verdict == "Guilty"
    assert result.is_tie is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/voting/ -q`
Expected: all 3 new tests FAIL — none of the three `apply()` implementations accept a `dimension`
keyword argument yet (`TypeError`).

- [ ] **Step 3: Update `VotingStrategy.apply`'s abstract signature**

In `psalm/voting/base.py`, replace (currently lines 16-20):

```python
class VotingStrategy(ABC):
    @abstractmethod
    async def apply(
        self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None
    ) -> VoteResult: ...
```

with:

```python
class VotingStrategy(ABC):
    @abstractmethod
    async def apply(
        self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None,
        dimension: Any = None,
    ) -> VoteResult: ...
```

- [ ] **Step 4: Update `SimpleMajorityVoting.apply`**

In `psalm/voting/simple_majority.py`, replace (currently lines 10-13):

```python
class SimpleMajorityVoting(VotingStrategy):
    async def apply(
        self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None
    ) -> VoteResult:
```

with:

```python
class SimpleMajorityVoting(VotingStrategy):
    async def apply(
        self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None,
        dimension: Any = None,
    ) -> VoteResult:
```

(The method body is unchanged — `dimension` is accepted but not used by this strategy.)

- [ ] **Step 5: Update `TrustWeightedVoting.apply`**

In `psalm/voting/trust_weighted.py`, replace (currently lines 14-17):

```python
class TrustWeightedVoting(VotingStrategy):
    async def apply(
        self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None
    ) -> VoteResult:
```

with:

```python
class TrustWeightedVoting(VotingStrategy):
    async def apply(
        self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None,
        dimension: Any = None,
    ) -> VoteResult:
```

(The method body is unchanged — `dimension` is accepted but not used by this strategy.)

- [ ] **Step 6: Update `JudgeTiebreakerVoting.apply` to forward `dimension`**

In `psalm/voting/judge_tiebreaker.py`, replace (currently lines 10-25):

```python
class JudgeTiebreakerVoting(VotingStrategy):
    async def apply(
        self,
        votes: list[JurorVote],
        judge: Any,
        argumentation_log: ArgumentationLog | None = None,
    ) -> VoteResult:
        if judge is None:
            raise PSALMConfigError(
                code="PSALM-C005",
                message="JudgeTiebreakerVoting requires a Judge instance.",
                context={},
                suggestion="Ensure .with_judge(...) is called on the builder before .build().",
            )
        verdict = await judge.tiebreak(votes, argumentation_log)
        return VoteResult(verdict=verdict, is_tie=False)
```

with:

```python
class JudgeTiebreakerVoting(VotingStrategy):
    async def apply(
        self,
        votes: list[JurorVote],
        judge: Any,
        argumentation_log: ArgumentationLog | None = None,
        dimension: Any = None,
    ) -> VoteResult:
        if judge is None:
            raise PSALMConfigError(
                code="PSALM-C005",
                message="JudgeTiebreakerVoting requires a Judge instance.",
                context={},
                suggestion="Ensure .with_judge(...) is called on the builder before .build().",
            )
        verdict = await judge.tiebreak(votes, argumentation_log, dimension=dimension)
        return VoteResult(verdict=verdict, is_tie=False)
```

- [ ] **Step 7: Pass `state.current_dimension` from `_apply_voting_strategy`**

In `psalm/phases/deliberation.py`, inside `_apply_voting_strategy` (currently lines 165-168),
replace:

```python
    async def _apply_voting_strategy(self, state: DeliberationState) -> dict[str, Any]:
        latest_votes = [JurorVote(**v) for v in state.vote_history[-1]["votes"]]
        for strategy in self._voting_strategies:
            result = await strategy.apply(latest_votes, self._judge, state.argumentation_log)
```

with:

```python
    async def _apply_voting_strategy(self, state: DeliberationState) -> dict[str, Any]:
        latest_votes = [JurorVote(**v) for v in state.vote_history[-1]["votes"]]
        for strategy in self._voting_strategies:
            result = await strategy.apply(
                latest_votes, self._judge, state.argumentation_log, state.current_dimension,
            )
```

(The rest of the method — the `await emit(...)` call and the `if not result.is_tie:` branch —
is unchanged.)

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/voting/ -q`
Expected: `4 passed` (test_judge_tiebreaker.py), `6 passed` (test_simple_majority.py),
`4 passed` (test_trust_weighted.py)

- [ ] **Step 9: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: `370 passed, 1 skipped` (367 from Task 2 + 3 new). Every existing call to
`strategy.apply(...)` across the whole suite (including `tests/integration/` and `tests/e2e/`,
which exercise the real `DeliberationPhase` graph end-to-end) omits `dimension` entirely, so they
all exercise the new parameter's default (`None`) — confirm the count matches exactly, since this
task's change reaches into the deliberation graph's live call path, not just isolated unit tests.

- [ ] **Step 10: Commit**

```bash
git add psalm/voting/base.py psalm/voting/simple_majority.py psalm/voting/trust_weighted.py psalm/voting/judge_tiebreaker.py psalm/phases/deliberation.py tests/unit/voting/test_judge_tiebreaker.py tests/unit/voting/test_simple_majority.py tests/unit/voting/test_trust_weighted.py
git commit -m "feat: thread dimension through VotingStrategy.apply to the judge's tiebreak"
```

---

### Task 4: Full suite and web backend verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full SDK suite**

Run: `cd "C:\Users\P70098761\Documents\projects\psalm-mirror" && python -m pytest tests/ -q`
Expected: `370 passed, 1 skipped` (362 baseline + 2 from Task 1 + 3 from Task 2 + 3 from Task 3 =
370). If the actual count differs, trust the actual run and investigate before proceeding.

- [ ] **Step 2: Run the web backend suite (unaffected, confirm no regression)**

Run: `cd examples/web/backend && python -m pytest -q`
Expected: `60 passed` (matches the pre-plan baseline — no file under `examples/web/` is touched
by this plan, and no stored vote value or API shape changed).

If either run shows unexpected failures, stop and investigate before considering this plan
complete.
