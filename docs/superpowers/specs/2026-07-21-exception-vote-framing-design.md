# Exception-Dimension Vote Framing — Design

## 1. Overview

The 2026-07-21 exception-dimension-scoping fix relabeled exception-dimension verdicts for
*display* only — the rationale text and the web `ResultsPage.tsx` badge show "Exception
Applies"/"Exception Does Not Apply" instead of "Guilty"/"Not Guilty". But the juror casting that
vote is never told any of this: `Juror.vote()`'s prompt doesn't say whether the dimension it's
scoring is an infringement or an exception dimension at all (the juror can only infer it from the
dimension's name/description), and the static vote-options instruction is unconditionally
"Guilty", "Not Guilty", or "Undecided" — framed as an infringement question regardless of what's
actually being evaluated. The same gap exists one level up: if the jury deadlocks on an exception
dimension, `Judge.tiebreak()` resolves it with the identical unconditional Guilty/Not-Guilty
framing, with no way to know it's tiebreaking an exception-dimension vote.

**Goal:** make the juror's and judge's own reasoning correctly framed as "does this exception
apply" for exception dimensions — fixing the actual question they're being asked, not just how
the answer is displayed afterward. This is deliberately the smaller of two options considered: it
does **not** change any stored vote value, type, or downstream consumer. `JurorVote.vote`,
`DimensionVerdict.verdict`, `_TiebreakDecision`, `_aggregate_verdict`, and the web API shape all
keep using `Literal["Guilty", "Not Guilty", "Undecided"]` exactly as today — only the prompt text
each agent is shown changes, conditioned on `dimension.dimension_type`. The categorical vote
already doesn't drive verdict aggregation (only `weighted_score` does, since Plan 11), so a full
type-level split would add real complexity across the voting-strategy pipeline for no behavioral
benefit here.

## 2. Juror Prompt

**`psalm/agents/juror.py` — `_format_sub_dimension_rubric`:**
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
For an infringement dimension, this produces byte-identical output to today (the new block is
appended only inside the `if`, `"Sub-dimensions to score:"` is still always appended right after
it either way). This is the sole call site (`Juror.vote()`); `vote_all_dimensions()` calls
`vote()` per dimension in a loop and so picks this up automatically for every dimension type
without further changes.

## 3. Judge Tiebreak Prompt

**`psalm/agents/judge.py` — `Judge.tiebreak`:**
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
        ...
```
The appended sentence is verbatim-identical in wording to the juror's, so the system explains
this concept the same way everywhere it comes up. `dimension` defaults to `None` (existing
callers that don't pass it — there are none in production code, but any future/test caller —
behave exactly as today, i.e. the unconditional infringement framing).

## 4. Threading `dimension` Through the Voting-Strategy Chain

`Judge.tiebreak()` is only ever called from `JudgeTiebreakerVoting.apply()`, which is one of
several interchangeable `VotingStrategy` implementations invoked uniformly from
`psalm/phases/deliberation.py`'s `_apply_voting_strategy`. `dimension` needs to reach
`JudgeTiebreakerVoting` through that same uniform call, so the shared interface gains the
parameter — even though only one of the three implementations uses it, matching how
`argumentation_log` is already a shared-but-not-universally-used parameter on this interface.

**`psalm/voting/base.py` — `VotingStrategy.apply`:**
```python
class VotingStrategy(ABC):
    @abstractmethod
    async def apply(
        self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None,
        dimension: Any = None,
    ) -> VoteResult: ...
```
`dimension: Any` (not `Dimension`) matches this file's existing convention of not importing
`psalm.agents.judge`/`psalm.dimensions` types into the voting package — `judge: Any` already
follows this pattern.

**`psalm/voting/simple_majority.py` and `psalm/voting/trust_weighted.py`:** both gain the same
`dimension: Any = None` parameter on their `apply()` overrides, unused in both bodies — needed
only so every concrete implementation's signature matches the shared interface uniformly.

**`psalm/voting/judge_tiebreaker.py` — `JudgeTiebreakerVoting.apply`:**
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

**`psalm/phases/deliberation.py` — `_apply_voting_strategy`:**
```python
    async def _apply_voting_strategy(self, state: DeliberationState) -> dict[str, Any]:
        latest_votes = [JurorVote(**v) for v in state.vote_history[-1]["votes"]]
        for strategy in self._voting_strategies:
            result = await strategy.apply(
                latest_votes, self._judge, state.argumentation_log, state.current_dimension,
            )
            await emit(VotingStrategyApplied(
                strategy_name=type(strategy).__name__, is_tie=result.is_tie, verdict=result.verdict,
            ))
            if not result.is_tie:
                return {
                    "final_verdict": result.verdict,
                    "voting_strategy_applied": type(strategy).__name__,
                }
        return {"final_verdict": "Undecided", "voting_strategy_applied": "fallback"}
```
`state.current_dimension` is already a live `Dimension` object at this point in the graph — it's
the same attribute `_jury_vote` already passes into every `juror.vote(dimension=...)` call earlier
in the same run.

## 5. Data Flow

No new data flows, no new fields on any Pydantic model. `dimension` is passed as a plain function
argument at each hop (`_apply_voting_strategy` → `VotingStrategy.apply` → `Judge.tiebreak`);
nothing is persisted, logged, or serialized differently. `JurorVote`, `DimensionVerdict`,
`PSALMResult`, and every event type are byte-for-byte unchanged.

## 6. Error Handling

None needed. `dimension` is optional everywhere it's threaded (`None` default), so no existing
call site can break, and there's no new failure mode — a missing `dimension` just means the
unconditional (today's) framing is used, which is always a safe fallback.

## 7. Testing

- `_format_sub_dimension_rubric(CHARACTER)` (infringement) — output unchanged from today (no
  "EXCEPTION dimension" text), confirming the existing juror-prompt tests need no changes.
- `_format_sub_dimension_rubric(SCENES_A_FAIRE)` (exception) — output contains the new sentence.
- `Judge.tiebreak(votes, log, dimension=SCENES_A_FAIRE)` — captured system prompt contains the new
  sentence. `Judge.tiebreak(votes, log)` (no `dimension`) and
  `Judge.tiebreak(votes, log, dimension=CHARACTER)` — captured system prompt does **not** contain
  it, confirming both the "not passed" and "infringement dimension" cases fall back to today's
  unconditional framing identically.
- `JudgeTiebreakerVoting.apply(votes, judge, log, dimension=SCENES_A_FAIRE)` — confirms `dimension`
  is forwarded to `judge.tiebreak(...)` as a keyword argument (spy on a mock judge).
- `SimpleMajorityVoting.apply(...)` and `TrustWeightedVoting.apply(...)` accept an extra
  `dimension=` keyword without erroring (they ignore it) — one test each, or extend an existing
  test to pass it.
- Full existing suite re-run after changes; every existing call site across
  `tests/unit/voting/*.py`, `tests/unit/agents/test_judge.py`, and `tests/unit/agents/test_juror.py`
  omits the new parameter entirely, so all of them exercise the default (`None`)/infringement path
  and should keep passing unchanged.

## 8. Breaking Changes

None. Every new parameter is optional with a safe default; every existing call site (production
and test) that doesn't pass it keeps behaving exactly as today. No Pydantic model, event type, or
web API shape changes.

## 9. Files Added / Modified

**Modified:**
- `psalm/agents/juror.py` — `_format_sub_dimension_rubric` (§2)
- `psalm/agents/judge.py` — `Judge.tiebreak` (§3)
- `psalm/voting/base.py` — `VotingStrategy.apply` abstract signature (§4)
- `psalm/voting/simple_majority.py`, `psalm/voting/trust_weighted.py` — `apply()` signature only,
  no body changes (§4)
- `psalm/voting/judge_tiebreaker.py` — `apply()` threads `dimension` to `judge.tiebreak` (§4)
- `psalm/phases/deliberation.py` — `_apply_voting_strategy` passes `state.current_dimension` (§4)
- Corresponding test files under `tests/unit/agents/`, `tests/unit/voting/` (§7)

**Unchanged:** `psalm/models/result.py` (`JurorVote`, `DimensionVerdict`, `_TiebreakDecision`
stay exactly as today), `psalm/courtroom/default.py` (`_aggregate_verdict` unaffected — it never
read the categorical vote for exception dimensions in the first place, only `weighted_score`),
the web backend/frontend (no API shape changes — the already-shipped display relabeling in
`ResultsPage.tsx` and `_synthesize_rationale` needs no further change since the underlying stored
values are unchanged).
