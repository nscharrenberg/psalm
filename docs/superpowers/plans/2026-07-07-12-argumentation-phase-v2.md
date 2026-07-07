# Argumentation Phase v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exception-dimension cross-application (scenes-a-faire usable as an argumentative tool inside every infringement dimension's pipeline while still getting its own independent verdict, excluded from the overall aggregation), an explicit "no further arguments" signal replacing silent empty lists, and a factual/unambiguous/no-guesswork evidentiary discipline enforced through both prompts and a Judge validation gate.

**Architecture:** `Dimension` and `DimensionVerdict` gain a `dimension_type: Literal["infringement", "exception"]` field (default `"infringement"`). The four `Prosecutor`/`Defense` gather methods change their return type from `list[Argument]` to a new `ArgumentBatch` model (`arguments`, `no_further_arguments`, `closing_statement`), which `ArgumentationPhase` routes through a new completeness-retry wrapper backed by a deterministic `Judge.validate_batch_completeness` check before falling through to the existing per-argument judge validation. `DefaultCourtroom._run_single_dimension` injects configured exception dimensions as auxiliary argumentation context for every infringement dimension under `FULLY_SEPARATE`, while exception dimensions still run their own standalone pipeline; `_aggregate_verdict`/`_synthesize_rationale` filter to infringement dimensions only.

**Tech Stack:** Python 3.11+, Pydantic v2, LangGraph, pytest-asyncio

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-07-07-argumentation-phase-v2-design.md` — this plan implements it in full; consult it for rationale behind any decision below.
- Argue-first order stays fixed (prosecution always argues first) — no reversal support is added.
- The existing round stop condition ("all four argument lists empty this round" OR stability detected) is unchanged — a well-formed `no_further_arguments=True` batch always produces an empty `arguments` list, so the existing check already covers it correctly.
- `Dimension.dimension_type` and `DimensionVerdict.dimension_type` both default to `"infringement"` — this keeps every existing test/fixture that constructs these models without the field working unchanged.
- `Argument` itself (in `psalm/models/evidence.py`) is NOT modified — it still requires non-empty `proofs`. A "nothing more to argue" response never constructs an `Argument`.
- `Judge.validate_batch_completeness` is `async def` (even though it does no I/O) to match the existing style of `Judge.detect_stability`, which is also a deterministic async method — keeps every `Judge` method awaitable uniformly.
- New `PSALMRuntimeError` codes: `PSALM-R004` (missing `closing_statement`), `PSALM-R005` (`no_further_arguments=True` with non-empty `arguments`). New `PSALMAgentError` code: `PSALM-A004` (completeness-retry exhausted).
- Run `pytest tests/unit/ -v` after every commit. Run `pytest tests/ -v` (full suite, including integration/e2e) at the end of Task 12.

---

### Task 1: `Dimension.dimension_type` + `SCENES_A_FAIRE` update

**Files:**
- Modify: `psalm/dimensions/base.py`
- Modify: `psalm/dimensions/scenes_a_faire.py`
- Modify: `tests/unit/dimensions/test_base.py`
- Modify: `tests/unit/dimensions/test_builtins.py`

**Interfaces:**
- Produces: `Dimension.dimension_type: Literal["infringement", "exception"] = "infringement"` — consumed by `_format_sub_dimensions` (Tasks 6, 7) and `DefaultCourtroom` (Task 10).

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/dimensions/test_base.py`:

```python
def test_dimension_defaults_to_infringement_type():
    dim = Dimension(
        name="test",
        description="A test dimension.",
        sub_dimensions=[SubDimension(name="Sub1", description="sub1")],
    )
    assert dim.dimension_type == "infringement"


def test_dimension_accepts_exception_type():
    dim = Dimension(
        name="test-exception",
        description="A test exception dimension.",
        dimension_type="exception",
        sub_dimensions=[SubDimension(name="Sub1", description="sub1")],
    )
    assert dim.dimension_type == "exception"
```

Add to `tests/unit/dimensions/test_builtins.py`:

```python
def test_scenes_a_faire_is_exception_type():
    assert SCENES_A_FAIRE.dimension_type == "exception"


def test_character_plot_world_building_are_infringement_type():
    assert CHARACTER.dimension_type == "infringement"
    assert PLOT.dimension_type == "infringement"
    assert WORLD_BUILDING.dimension_type == "infringement"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/dimensions/ -v -k "dimension_type or infringement_type or exception_type"
```
Expected: FAIL — `Dimension` has no `dimension_type` field.

- [ ] **Step 3: Update `psalm/dimensions/base.py`**

Change the import line and the `Dimension` class:

```python
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class Importance(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


_IMPORTANCE_MULTIPLIERS: dict[Importance, float] = {
    Importance.LOW:      0.5,
    Importance.MEDIUM:   1.0,
    Importance.HIGH:     1.5,
    Importance.CRITICAL: 2.0,
}


class SimilarityScore(str, Enum):
    NONE     = "none"
    GENERIC  = "generic"
    POSSIBLE = "possible"
    CLEAR    = "clear"


_SCORE_VALUES: dict[SimilarityScore, int] = {
    SimilarityScore.NONE:     0,
    SimilarityScore.GENERIC:  1,
    SimilarityScore.POSSIBLE: 2,
    SimilarityScore.CLEAR:    3,
}


class SubDimension(BaseModel):
    name: str
    description: str
    importance: Importance = Importance.MEDIUM


class Dimension(BaseModel):
    name: str
    description: str
    sub_dimensions: list[SubDimension]
    importance: Importance = Importance.MEDIUM
    dimension_type: Literal["infringement", "exception"] = "infringement"
```

- [ ] **Step 4: Update `psalm/dimensions/scenes_a_faire.py`**

Add `dimension_type="exception",` to the `SCENES_A_FAIRE` constructor call:

```python
from psalm.dimensions.base import Dimension, Importance, SubDimension

SCENES_A_FAIRE = Dimension(
    name="scenes-a-faire",
    description="Stock elements that are not copyright-protected.",
    importance=Importance.MEDIUM,
    dimension_type="exception",
    sub_dimensions=[
        SubDimension(
            name="Genre Conventions & Setting",
            description="Standard genre elements used.",
            importance=Importance.CRITICAL,
        ),
        SubDimension(
            name="Standard Characters & Archetypes",
            description="Whether characters are clichéd archetypes.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Standard Plot Devices & Tropes",
            description="Use of clichéd storylines.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Thematic Commonplaces",
            description="Whether themes are generic.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Necessary Technical Elements",
            description="Functionally necessary elements.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Creative Elaboration",
            description="How much original elaboration exists.",
            importance=Importance.LOW,
        ),
    ],
)
```

- [ ] **Step 5: Run tests**

```
pytest tests/unit/dimensions/ -v
```
Expected: all PASS

- [ ] **Step 6: Run full unit suite to catch regressions**

```
pytest tests/unit/ -v
```
Expected: all PASS (additive default field, no breakage expected)

- [ ] **Step 7: Commit**

```bash
git add psalm/dimensions/base.py psalm/dimensions/scenes_a_faire.py tests/unit/dimensions/test_base.py tests/unit/dimensions/test_builtins.py
git commit -m "feat: add Dimension.dimension_type (infringement/exception); mark SCENES_A_FAIRE as exception"
```

---

### Task 2: `DimensionVerdict.dimension_type`

**Files:**
- Modify: `psalm/models/result.py`
- Modify: `tests/unit/models/test_result.py`

**Interfaces:**
- Consumes: `Dimension.dimension_type` (Task 1)
- Produces: `DimensionVerdict.dimension_type: Literal["infringement", "exception"] = "infringement"` — consumed by `DefaultCourtroom` (Task 10)

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/models/test_result.py`:

```python
def test_dimension_verdict_defaults_to_infringement_type(minimal_argumentation_log, minimal_debate_log):
    from psalm.models.result import DimensionVerdict
    dv = DimensionVerdict(
        dimension="character",
        importance=Importance.HIGH,
        verdict="Guilty",
        weighted_score=0.75,
        argumentation_log=minimal_argumentation_log,
        debate_log=minimal_debate_log,
    )
    assert dv.dimension_type == "infringement"


def test_dimension_verdict_accepts_exception_type(minimal_argumentation_log, minimal_debate_log):
    from psalm.models.result import DimensionVerdict
    dv = DimensionVerdict(
        dimension="scenes-a-faire",
        dimension_type="exception",
        importance=Importance.MEDIUM,
        verdict="Not Guilty",
        weighted_score=0.2,
        argumentation_log=minimal_argumentation_log,
        debate_log=minimal_debate_log,
    )
    assert dv.dimension_type == "exception"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/models/test_result.py -v -k "dimension_verdict_defaults_to_infringement or dimension_verdict_accepts_exception"
```
Expected: FAIL — `DimensionVerdict` has no `dimension_type` field.

- [ ] **Step 3: Update `DimensionVerdict` in `psalm/models/result.py`**

`Literal` is already imported (`from typing import Any, Literal`). Update the class:

```python
class DimensionVerdict(BaseModel):
    dimension: str
    dimension_type: Literal["infringement", "exception"] = "infringement"
    importance: Importance
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    weighted_score: float
    argumentation_log: ArgumentationLog
    debate_log: DebateLog
```

- [ ] **Step 4: Run tests**

```
pytest tests/unit/models/test_result.py -v
```
Expected: all PASS

- [ ] **Step 5: Run full unit suite**

```
pytest tests/unit/ -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add psalm/models/result.py tests/unit/models/test_result.py
git commit -m "feat: add DimensionVerdict.dimension_type field"
```

---

### Task 3: `ArgumentBatch` + `ClosingStatement` models

**Files:**
- Modify: `psalm/models/evidence.py`
- Modify: `tests/unit/models/test_evidence.py`

**Interfaces:**
- Produces: `ArgumentBatch(arguments: list[Argument], no_further_arguments: bool, closing_statement: str | None)`, `ClosingStatement(round: int, statement: str)` — consumed by `Judge` (Task 5), `Prosecutor`/`Defense` (Tasks 6, 7), `ArgumentationPhase` (Task 8)

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/models/test_evidence.py`:

```python
def test_argument_batch_defaults():
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch()
    assert batch.arguments == []
    assert batch.no_further_arguments is False
    assert batch.closing_statement is None


def test_argument_batch_with_arguments(proof):
    from psalm.models.evidence import ArgumentBatch
    arg = Argument(claim="c", dimension="character", proofs=[proof], agent_role="prosecutor", round=1)
    batch = ArgumentBatch(arguments=[arg])
    assert len(batch.arguments) == 1
    assert batch.no_further_arguments is False


def test_argument_batch_no_further_arguments_requires_closing_statement():
    from psalm.exceptions import PSALMRuntimeError
    from psalm.models.evidence import ArgumentBatch
    with pytest.raises(PSALMRuntimeError) as exc_info:
        ArgumentBatch(no_further_arguments=True)
    assert exc_info.value.code == "PSALM-R004"


def test_argument_batch_no_further_arguments_valid_with_statement():
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further to add.")
    assert batch.no_further_arguments is True
    assert batch.closing_statement == "Nothing further to add."


def test_argument_batch_no_further_arguments_rejects_nonempty_arguments(proof):
    from psalm.exceptions import PSALMRuntimeError
    from psalm.models.evidence import ArgumentBatch
    arg = Argument(claim="c", dimension="character", proofs=[proof], agent_role="prosecutor", round=1)
    with pytest.raises(PSALMRuntimeError) as exc_info:
        ArgumentBatch(arguments=[arg], no_further_arguments=True, closing_statement="Done.")
    assert exc_info.value.code == "PSALM-R005"


def test_closing_statement_model():
    from psalm.models.evidence import ClosingStatement
    cs = ClosingStatement(round=1, statement="The prosecution rests.")
    assert cs.round == 1
    assert cs.statement == "The prosecution rests."
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/models/test_evidence.py -v -k "argument_batch or closing_statement"
```
Expected: `ImportError: cannot import name 'ArgumentBatch'`

- [ ] **Step 3: Update `psalm/models/evidence.py`**

```python
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from psalm.exceptions import PSALMRuntimeError


class Proof(BaseModel):
    source_excerpt: str
    target_excerpt: str
    relevance: str


class Argument(BaseModel):
    claim: str
    dimension: str
    proofs: list[Proof]
    agent_role: str
    round: int

    @field_validator("proofs")
    @classmethod
    def validate_proofs(cls, v: list[Proof]) -> list[Proof]:
        if not v:
            raise PSALMRuntimeError(
                code="PSALM-R003",
                message="Argument must have at least one proof.",
                context={},
                suggestion="Ensure the agent provides source/target excerpts with each claim.",
            )
        return v


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
            raise PSALMRuntimeError(
                code="PSALM-R004",
                message="closing_statement is required when no_further_arguments=True.",
                context={"no_further_arguments": self.no_further_arguments},
                suggestion=(
                    "Provide a one-sentence closing_statement explaining why there is nothing "
                    "further to argue."
                ),
            )
        if self.no_further_arguments and self.arguments:
            raise PSALMRuntimeError(
                code="PSALM-R005",
                message="no_further_arguments=True must not include arguments.",
                context={"argument_count": len(self.arguments)},
                suggestion="Either clear no_further_arguments or remove the arguments list.",
            )
        return self
```

- [ ] **Step 4: Run tests**

```
pytest tests/unit/models/test_evidence.py -v
```
Expected: all PASS

- [ ] **Step 5: Run full unit suite**

```
pytest tests/unit/ -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add psalm/models/evidence.py tests/unit/models/test_evidence.py
git commit -m "feat: add ArgumentBatch and ClosingStatement models"
```

---

### Task 4: `RoundArguments` closing-statement fields + `ArgumentationState` accumulators

**Files:**
- Modify: `psalm/models/result.py`
- Modify: `psalm/models/state.py`
- Modify: `tests/unit/models/test_result.py`
- Modify: `tests/unit/models/test_state.py`

**Interfaces:**
- Produces: `RoundArguments` gains `prosecution_closing_statement`, `defense_counter_closing_statement`, `defense_closing_statement`, `prosecution_counter_closing_statement` (all `str | None = None`). `ArgumentationState` gains `prosecution_closing_statements`, `defense_counter_closing_statements`, `defense_closing_statements`, `prosecution_counter_closing_statements` (all `list[dict[str, Any]] = Field(default_factory=list)`) — consumed by `ArgumentationPhase` (Task 8).

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/models/test_result.py`:

```python
def test_round_arguments_closing_statements_default_none():
    from psalm.models.result import RoundArguments
    ra = RoundArguments(
        round=1,
        prosecution_arguments=[],
        defense_counters=[],
        defense_arguments=[],
        prosecution_counters=[],
    )
    assert ra.prosecution_closing_statement is None
    assert ra.defense_counter_closing_statement is None
    assert ra.defense_closing_statement is None
    assert ra.prosecution_counter_closing_statement is None


def test_round_arguments_accepts_closing_statements():
    from psalm.models.result import RoundArguments
    ra = RoundArguments(
        round=1,
        prosecution_arguments=[],
        prosecution_closing_statement="The prosecution rests.",
        defense_counters=[],
        defense_counter_closing_statement="No counters to offer.",
        defense_arguments=[],
        defense_closing_statement="The defense rests.",
        prosecution_counters=[],
        prosecution_counter_closing_statement="No rebuttal needed.",
    )
    assert ra.prosecution_closing_statement == "The prosecution rests."
    assert ra.defense_counter_closing_statement == "No counters to offer."
    assert ra.defense_closing_statement == "The defense rests."
    assert ra.prosecution_counter_closing_statement == "No rebuttal needed."
```

Add to `tests/unit/models/test_state.py`:

```python
def test_argumentation_state_has_closing_statement_accumulators():
    state = ArgumentationState(
        source_text="src", target_text="tgt", dimensions=[CHARACTER], max_rounds=3
    )
    assert state.prosecution_closing_statements == []
    assert state.defense_counter_closing_statements == []
    assert state.defense_closing_statements == []
    assert state.prosecution_counter_closing_statements == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/models/test_result.py tests/unit/models/test_state.py -v -k "closing_statement"
```
Expected: FAIL — fields don't exist yet.

- [ ] **Step 3: Update `RoundArguments` in `psalm/models/result.py`**

```python
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

- [ ] **Step 4: Update `ArgumentationState` in `psalm/models/state.py`**

Add four new fields after the existing "Step 4" block:

```python
    # Step 4 — prosecution counters to defense
    pending_prosecution_counters: list[dict[str, Any]] = Field(default_factory=list)
    prosecution_counters: list[Argument] = Field(default_factory=list)

    # Closing statements — round-tagged, one accumulator per step
    prosecution_closing_statements: list[dict[str, Any]] = Field(default_factory=list)
    defense_counter_closing_statements: list[dict[str, Any]] = Field(default_factory=list)
    defense_closing_statements: list[dict[str, Any]] = Field(default_factory=list)
    prosecution_counter_closing_statements: list[dict[str, Any]] = Field(default_factory=list)
```

(This replaces the final two lines of the existing `ArgumentationState` class — the four new fields are appended after `prosecution_counters`.)

- [ ] **Step 5: Run tests**

```
pytest tests/unit/models/test_result.py tests/unit/models/test_state.py -v
```
Expected: all PASS

- [ ] **Step 6: Run full unit suite**

```
pytest tests/unit/ -v
```
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add psalm/models/result.py psalm/models/state.py tests/unit/models/test_result.py tests/unit/models/test_state.py
git commit -m "feat: add closing-statement fields to RoundArguments and ArgumentationState"
```

---

### Task 5: `Judge` — hedging/speculation criterion + `validate_batch_completeness`

**Files:**
- Modify: `psalm/agents/judge.py`
- Modify: `tests/unit/agents/test_judge.py`

**Interfaces:**
- Consumes: `ArgumentBatch` (Task 3)
- Produces: `Judge.validate_batch_completeness(batch: ArgumentBatch) -> bool` — consumed by `ArgumentationPhase` (Task 8)

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/agents/test_judge.py`:

```python
def test_prosecution_validation_prompt_rejects_hedging_language():
    from psalm.agents.judge import _PROSECUTION_VALIDATION_PROMPT
    prompt = _PROSECUTION_VALIDATION_PROMPT.lower()
    assert "hedg" in prompt or "speculat" in prompt
    assert "might" in prompt or "possibly" in prompt


def test_defense_validation_prompt_rejects_hedging_language():
    from psalm.agents.judge import _DEFENSE_VALIDATION_PROMPT
    prompt = _DEFENSE_VALIDATION_PROMPT.lower()
    assert "hedg" in prompt or "speculat" in prompt


async def test_validate_batch_completeness_true_when_has_arguments(judge, sample_argument):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch(arguments=[sample_argument])
    assert await judge.validate_batch_completeness(batch) is True


async def test_validate_batch_completeness_true_when_no_further_arguments(judge):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")
    assert await judge.validate_batch_completeness(batch) is True


async def test_validate_batch_completeness_false_when_empty_and_not_declared(judge):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch()
    assert await judge.validate_batch_completeness(batch) is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/agents/test_judge.py -v -k "hedging or batch_completeness"
```
Expected: FAIL — `validate_batch_completeness` doesn't exist; hedging criterion absent from prompts.

- [ ] **Step 3: Update `psalm/agents/judge.py`**

Replace the whole file:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument, ArgumentBatch
from psalm.models.result import ArgumentationLog, JurorVote, ValidationResult


class _StabilityDecision(BaseModel):
    stability_detected: bool
    reasoning: str


class _TiebreakDecision(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str


_PROSECUTION_VALIDATION_PROMPT = """\
You are a judge validating a prosecution argument in a copyright case governed by EU copyright law.
Reject the argument (is_valid=false) if ANY of the following criteria fails:

(1) The argument includes at least one proof with relevant passages from both texts.
(2) The passages are derived from the provided texts — close approximations and paraphrases are
    acceptable; reject only if the passage appears completely fabricated (not based on anything
    in the actual texts).
(3) The reasoning is relevant to the claimed dimension.
(4) The passages show some connection to the argument's claim — even a weak connection passes;
    the defense will challenge it. Reject only if the described similarity is entirely absent
    from the passages (factually false claim).
(5) The claim is stated as a clear, unambiguous assertion — reject if it uses hedging or
    speculative language ("might", "could suggest", "possibly", "perhaps", "may indicate") or
    otherwise presents an inference or guess as settled fact without clear textual grounding.

Note: Do NOT reject arguments solely because they argue idea-level or thematic similarity.
Those are legally weak and the defense will rebut them.
"""

_DEFENSE_VALIDATION_PROMPT = """\
You are a judge validating a defense argument in a copyright case governed by EU copyright law.
Reject the argument (is_valid=false) if ANY of the following criteria fails:

(1) The argument includes at least one proof with relevant passages from both texts.
(2) The passages are derived from the provided texts — close approximations and paraphrases are
    acceptable; reject only if a passage appears completely fabricated (not based on anything
    in the actual texts).
(3) The reasoning is relevant either to a prosecution argument being challenged, or to
    establishing why the texts differ or are independently created.
(4) The claim is stated as a clear, unambiguous assertion — reject if it uses hedging or
    speculative language ("might", "could suggest", "possibly", "perhaps", "may indicate") or
    otherwise presents an inference or guess as settled fact without clear textual grounding.

Defense arguments may challenge prosecution claims as legally insufficient (unprotectable ideas,
genre conventions), show differences in specific expression, argue independent creation, or
make affirmative claims about the texts' distinctiveness. They are NOT required to demonstrate
similarity — that is the prosecution's burden.
"""


class Judge(BaseAgent):
    @property
    def role(self) -> str:
        return "judge"

    async def validate_argument(
        self,
        argument: Argument,
        source_text: str,
        target_text: str,
        role: str = "prosecution",
    ) -> ValidationResult:
        structured_llm = self._llm.with_structured_output(ValidationResult)
        validation_prompt = (
            _DEFENSE_VALIDATION_PROMPT if role == "defense" else _PROSECUTION_VALIDATION_PROMPT
        )
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
                    f"Proofs:\n{proofs_text}\n\n"
                    f"Full source text:\n{source_text}\n\n"
                    f"Full target text:\n{target_text}"
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

    async def validate_batch_completeness(self, batch: ArgumentBatch) -> bool:
        if batch.no_further_arguments:
            return True  # pydantic validator already enforced closing_statement is present
        return bool(batch.arguments)

    async def detect_stability(
        self, current_arguments: list[Argument], previous_arguments: list[Argument]
    ) -> bool:
        if not previous_arguments:
            return False
        current_claims = {a.claim for a in current_arguments}
        previous_claims = {a.claim for a in previous_arguments}
        return current_claims == previous_claims

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
            "decision on the totality of the evidence and arguments."
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

- [ ] **Step 4: Run tests**

```
pytest tests/unit/agents/test_judge.py -v
```
Expected: all PASS

- [ ] **Step 5: Run full unit suite**

```
pytest tests/unit/ -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add psalm/agents/judge.py tests/unit/agents/test_judge.py
git commit -m "feat: add hedging/speculation validation criterion and Judge.validate_batch_completeness"
```

---

### Task 6: `Prosecutor` rewrite — `ArgumentBatch`, type-aware sub-dimensions, factual discipline

**Files:**
- Modify: `psalm/agents/prosecutor.py`
- Modify: `tests/unit/agents/test_prosecutor.py`

**Interfaces:**
- Consumes: `ArgumentBatch` (Task 3), `Dimension.dimension_type` (Task 1)
- Produces: `Prosecutor.gather_arguments(source_text, target_text, dimensions, round, prior_defense_arguments=None, retry_hint=None) -> ArgumentBatch`, `Prosecutor.gather_counter_arguments(source_text, target_text, dimensions, defense_arguments, round, retry_hint=None) -> ArgumentBatch` — consumed by `ArgumentationPhase` (Task 8)

- [ ] **Step 1: Update `psalm/agents/prosecutor.py`**

Replace the whole file:

```python
from __future__ import annotations

from psalm.agents.base import BaseAgent
from psalm.dimensions.base import Dimension
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument, ArgumentBatch


def _format_sub_dimensions(dimensions: list[Dimension]) -> str:
    lines: list[str] = []
    infringement_dims = [d for d in dimensions if d.dimension_type == "infringement"]
    exception_dims = [d for d in dimensions if d.dimension_type == "exception"]

    for dim in infringement_dims:
        lines.append(f"\nPRIMARY DIMENSION (must argue): {dim.name} — {dim.description}")
        lines.append(
            "Sub-dimensions (argue ALL marked HIGH or CRITICAL where factually supportable):"
        )
        for sd in dim.sub_dimensions:
            lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")

    for dim in exception_dims:
        lines.append(
            f"\nAVAILABLE EXCEPTION TOOLS (optional, cite only if relevant): "
            f"{dim.name} — {dim.description}"
        )
        for sd in dim.sub_dimensions:
            lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")

    return "\n".join(lines)


_SYSTEM_PROMPT = """\
You are a legal prosecutor in a copyright infringement case governed by EU copyright law.
Your goal is to argue that the target text infringes the source's copyright.

Surface all genuine similarities between the texts — the court filters; you argue.

PRIORITIZE these argument types (strongest first):
1. Near-verbatim or closely paraphrased passages — the same distinctive words or phrases appear
   in both texts, even with minor substitutions.
2. A unique metaphor, image, or narrative detail that appears in both texts.
3. Highly specific plot details that could not be independently invented — same names, same
   events, same distinctive sequence of choices.
4. Structural or expression-level similarities (genre conventions, shared archetypes) — the
   debate must proceed even when only weaker signals exist, but never fabricate a signal that
   isn't there.

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
"""


class Prosecutor(BaseAgent):
    @property
    def role(self) -> str:
        return "prosecutor"

    async def gather_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[Dimension],
        round: int,
        prior_defense_arguments: list[Argument] | None = None,
        retry_hint: str | None = None,
    ) -> ArgumentBatch:
        structured_llm = self._llm.with_structured_output(ArgumentBatch)
        rebuttal_section = ""
        if prior_defense_arguments:
            rebuttals = "\n".join(
                f"- [{a.dimension}] {a.claim}" for a in prior_defense_arguments
            )
            rebuttal_section = (
                f"\n\nDefense counter-arguments from prior rounds (rebut these directly):\n"
                f"{rebuttals}\n"
                "Address these challenges in your arguments — explain why the defense is wrong "
                "or present new evidence they did not counter."
            )
        sub_dim_block = _format_sub_dimensions(dimensions)
        retry_section = f"\n\n{retry_hint}" if retry_hint else ""
        content = (
            f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
            f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}{rebuttal_section}{retry_section}\n\n"
            "Provide arguments with relevant passages from both texts, for every sub-dimension "
            "where clear, unambiguous evidence exists. If none exists anywhere, declare "
            "no_further_arguments."
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            arguments = [
                a.model_copy(update={"round": round, "agent_role": "prosecutor"})
                for a in result.arguments
            ]
            return ArgumentBatch(
                arguments=arguments,
                no_further_arguments=result.no_further_arguments,
                closing_statement=result.closing_statement,
            )
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Prosecutor failed to return valid structured arguments.",
                context={"role": self.role, "round": round, "dimensions": [d.name for d in dimensions]},
                suggestion=(
                    "Check the LLM model supports structured output and the prompt is not too "
                    "long."
                ),
                cause=exc,
            ) from exc

    async def gather_counter_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[Dimension],
        defense_arguments: list[Argument],
        round: int,
        retry_hint: str | None = None,
    ) -> ArgumentBatch:
        """Step 4: Prosecution counters defense's affirmative arguments."""
        structured_llm = self._llm.with_structured_output(ArgumentBatch)
        dim_names = ", ".join(d.name for d in dimensions)
        defense_text = "\n".join(
            f"- [{a.dimension}] {a.claim}" for a in defense_arguments
        )
        retry_section = f"\n\n{retry_hint}" if retry_hint else ""
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
                    f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
                    f"Dimensions: {dim_names}\nRound: {round}\n\n"
                    f"Defense affirmative arguments to rebut:\n{defense_text}\n\n"
                    "Counter each defense argument only where you have clear, unambiguous "
                    "grounds: show why their claimed differences are insufficient to rule out "
                    "infringement, or present additional similarities the defense ignored. If "
                    f"no such grounds exist, declare no_further_arguments.{retry_section}"
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            arguments = [
                a.model_copy(update={"round": round, "agent_role": "prosecutor"})
                for a in result.arguments
            ]
            return ArgumentBatch(
                arguments=arguments,
                no_further_arguments=result.no_further_arguments,
                closing_statement=result.closing_statement,
            )
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Prosecutor failed to counter defense arguments.",
                context={"role": self.role, "round": round, "dimensions": [d.name for d in dimensions]},
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc
```

- [ ] **Step 2: Replace `tests/unit/agents/test_prosecutor.py`**

Replace the whole file:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.prosecutor import Prosecutor
from psalm.dimensions import CHARACTER, SCENES_A_FAIRE


@pytest.fixture
def prosecutor(agent_config):
    return Prosecutor(config=agent_config)


async def test_gather_arguments_returns_batch(prosecutor, sample_argument, agent_config):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(
            arguments=[sample_argument], no_further_arguments=False, closing_statement=None
        )
    )

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=[CHARACTER],
            round=1,
        )

    assert len(result.arguments) == 1
    assert result.arguments[0].agent_role == "prosecutor"
    assert result.arguments[0].dimension == "character"
    assert result.no_further_arguments is False


def test_prosecutor_prompt_prioritizes_expression_over_idea_arguments():
    # Prosecutor should prioritize expression-level arguments but is allowed to make weaker
    # idea/genre/archetype arguments so the debate can proceed — defense will rebut them.
    from psalm.agents.prosecutor import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "prioritize" in prompt or "strongest" in prompt
    assert "archetype" in prompt or "theme" in prompt or "genre" in prompt
    assert "debate must proceed" in prompt  # weaker args still allowed to proceed


async def test_gather_arguments_role():
    from psalm.models.config import AgentConfig
    config = AgentConfig(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    prosecutor = Prosecutor(config=config)
    assert prosecutor.role == "prosecutor"


async def test_prosecutor_includes_prior_defense_arguments_in_prompt(prosecutor, sample_argument, sample_counter_argument):
    # In rounds 2+, the prosecutor must receive prior defense counter-arguments so it can rebut
    # them — not just re-argue the same points ignoring what the defense said.
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        await prosecutor.gather_arguments(
            source_text="src",
            target_text="tgt",
            dimensions=[CHARACTER],
            round=2,
            prior_defense_arguments=[sample_counter_argument],
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Eye color is a generic trait" in user_content or "defense" in user_content.lower()


async def test_gather_arguments_retries_on_failure(prosecutor, sample_argument):
    call_count = 0

    async def failing_then_success(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("temporary failure")
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = AsyncMock()
    mock_chain.ainvoke = failing_then_success

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_arguments("src", "tgt", [CHARACTER], 1)

    assert call_count == 3
    assert len(result.arguments) == 1


async def test_prosecutor_gather_counter_arguments(prosecutor, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_counter_arguments(
            source_text="src",
            target_text="tgt",
            dimensions=[CHARACTER],
            defense_arguments=[sample_counter_argument],
            round=1,
        )
    assert len(result.arguments) == 1
    assert result.arguments[0].agent_role == "prosecutor"


async def test_prosecutor_counter_prompt_mentions_defense_args(prosecutor, sample_argument, sample_counter_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_counter_argument], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Eye color is a generic trait" in user_content or "defense" in user_content.lower()


async def test_prosecutor_prompt_includes_sub_dimension_context(agent_config, sample_argument):
    from psalm.agents.prosecutor import Prosecutor
    prosecutor = Prosecutor(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_arguments("src", "tgt", [CHARACTER], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Identity & Properties" in user_content
    assert "CRITICAL" in user_content or "HIGH" in user_content


def test_prosecutor_system_prompt_no_self_censorship():
    from psalm.agents.prosecutor import _SYSTEM_PROMPT
    assert "be aware the defense will challenge" not in _SYSTEM_PROMPT
    assert "surface" in _SYSTEM_PROMPT.lower() or "all" in _SYSTEM_PROMPT.lower()


def test_prosecutor_system_prompt_forbids_padding_and_guesswork():
    from psalm.agents.prosecutor import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "including generic or weak ones" not in prompt
    assert "unambiguous" in prompt
    assert "guess" in prompt or "speculative" in prompt
    assert "no_further_arguments" in prompt


async def test_prosecutor_prompt_separates_infringement_and_exception_dimensions(agent_config, sample_argument):
    prosecutor = Prosecutor(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_arguments("src", "tgt", [CHARACTER, SCENES_A_FAIRE], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "PRIMARY DIMENSION (must argue): character" in user_content
    assert "AVAILABLE EXCEPTION TOOLS" in user_content
    assert "scenes-a-faire" in user_content


async def test_prosecutor_retry_hint_appears_in_prompt(agent_config, sample_argument):
    prosecutor = Prosecutor(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(prosecutor._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await prosecutor.gather_arguments(
            "src", "tgt", [CHARACTER], 1, retry_hint="You must either argue or declare done."
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "You must either argue or declare done." in user_content


async def test_gather_arguments_returns_no_further_arguments(prosecutor):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(
            arguments=[],
            no_further_arguments=True,
            closing_statement="No further unambiguous similarities remain.",
        )
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(prosecutor._llm), "with_structured_output", mock_with_structured):
        result = await prosecutor.gather_arguments("src", "tgt", [CHARACTER], 1)

    assert result.arguments == []
    assert result.no_further_arguments is True
    assert result.closing_statement == "No further unambiguous similarities remain."
```

- [ ] **Step 3: Run prosecutor tests**

```
pytest tests/unit/agents/test_prosecutor.py -v
```
Expected: all PASS

- [ ] **Step 4: Run full unit suite**

```
pytest tests/unit/ -v
```
Expected: FAIL in `tests/unit/agents/test_defense.py` and `tests/unit/phases/test_argumentation_phase.py` (they still use the old list-returning mocks/agents) — expected, fixed in Tasks 7–8.

- [ ] **Step 5: Commit**

```bash
git add psalm/agents/prosecutor.py tests/unit/agents/test_prosecutor.py
git commit -m "feat: rewrite Prosecutor to return ArgumentBatch with type-aware sub-dimensions and factual-only prompt"
```

---

### Task 7: `Defense` rewrite — `ArgumentBatch`, type-aware sub-dimensions, factual discipline

**Files:**
- Modify: `psalm/agents/defense.py`
- Modify: `tests/unit/agents/test_defense.py`

**Interfaces:**
- Consumes: `ArgumentBatch` (Task 3), `Dimension.dimension_type` (Task 1)
- Produces: `Defense.gather_counter_arguments(source_text, target_text, dimensions, prosecutor_arguments, round, retry_hint=None) -> ArgumentBatch`, `Defense.gather_arguments(source_text, target_text, dimensions, round, retry_hint=None) -> ArgumentBatch` — consumed by `ArgumentationPhase` (Task 8)

- [ ] **Step 1: Update `psalm/agents/defense.py`**

Replace the whole file:

```python
from __future__ import annotations

from psalm.agents.base import BaseAgent
from psalm.dimensions.base import Dimension
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument, ArgumentBatch


def _format_sub_dimensions(dimensions: list[Dimension]) -> str:
    lines: list[str] = []
    infringement_dims = [d for d in dimensions if d.dimension_type == "infringement"]
    exception_dims = [d for d in dimensions if d.dimension_type == "exception"]

    for dim in infringement_dims:
        lines.append(f"\nPRIMARY DIMENSION (must argue): {dim.name} — {dim.description}")
        lines.append(
            "Sub-dimensions (argue ALL marked HIGH or CRITICAL where factually supportable):"
        )
        for sd in dim.sub_dimensions:
            lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")

    for dim in exception_dims:
        lines.append(
            f"\nAVAILABLE EXCEPTION TOOLS (optional, cite only if relevant): "
            f"{dim.name} — {dim.description}"
        )
        for sd in dim.sub_dimensions:
            lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")

    return "\n".join(lines)


_SYSTEM_PROMPT = """\
You are a defense attorney in a copyright infringement case governed by EU copyright law.
Challenge the prosecutor's arguments AND make proactive affirmative claims about the texts.

PRIMARY TOOLS for countering prosecution arguments:

1. IDEA-EXPRESSION DICHOTOMY (most powerful): Under EU copyright law, only specific creative
   expression is protected — not ideas, themes, concepts, or genre conventions. When the
   prosecution argues that both texts share a character type, theme, setting, or plot device,
   explicitly name this as an unprotectable idea and explain why it is not infringement.
   Examples to challenge: "both characters are liars", "both experience betrayal",
   "both set in an industrial city", "both have a mentor figure".

2. LACK OF EXPRESSION-LEVEL SIMILARITY: Even where concepts overlap, show that the specific
   wording, imagery, and narrative choices differ — different words, different details,
   different emotional register.

3. INDEPENDENT CREATION: Show that the claimed similarities are genre conventions or common
   literary devices that any author could independently create without access to the source.

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

For each prosecution argument, decide: does it rest on an unprotectable idea (challenge as
legally insufficient) or on specific expression (challenge on the merits)?

If you have nothing further that meets this bar — for this call, across every prosecution
argument and sub-dimension you were asked to address — set no_further_arguments=True and provide
a one-sentence closing_statement explaining why. Do not pad with a weak or speculative claim just
to appear productive.
"""


class Defense(BaseAgent):
    @property
    def role(self) -> str:
        return "defense"

    async def gather_counter_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[Dimension],
        prosecutor_arguments: list[Argument],
        round: int,
        retry_hint: str | None = None,
    ) -> ArgumentBatch:
        structured_llm = self._llm.with_structured_output(ArgumentBatch)
        args_text = "\n".join(
            f"- [{a.dimension}] {a.claim} (proofs: {len(a.proofs)})"
            for a in prosecutor_arguments
        )
        if prosecutor_arguments:
            instruction = (
                "Counter each prosecution argument where you have clear grounds (unprotectable "
                "ideas, lack of expression-level similarity, independent creation). "
                "Additionally, you may make an affirmative argument about why the texts are "
                "independently created — cite specific passages where the expression and "
                "creative choices diverge. If no clear grounds exist anywhere, declare "
                "no_further_arguments."
            )
        else:
            instruction = (
                "The prosecution has not yet raised any arguments. You may make affirmative "
                "arguments about why the target text does NOT infringe the source — highlight "
                "specific passages where the wording, imagery, and creative choices are "
                "independently created. If no clear, unambiguous grounds exist, declare "
                "no_further_arguments."
            )
        sub_dim_block = _format_sub_dimensions(dimensions)
        retry_section = f"\n\n{retry_hint}" if retry_hint else ""
        content = (
            f"SOURCE TEXT:\n{source_text}\n\n"
            f"TARGET TEXT:\n{target_text}\n\n"
            f"Prosecutor's arguments:\n{args_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}\n\n"
            f"{instruction}{retry_section}"
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            arguments = [
                a.model_copy(update={"round": round, "agent_role": "defense"})
                for a in result.arguments
            ]
            return ArgumentBatch(
                arguments=arguments,
                no_further_arguments=result.no_further_arguments,
                closing_statement=result.closing_statement,
            )
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Defense failed to return valid structured counter-arguments.",
                context={"role": self.role, "round": round},
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc

    async def gather_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[Dimension],
        round: int,
        retry_hint: str | None = None,
    ) -> ArgumentBatch:
        """Step 3: Defense makes independent affirmative arguments (no prosecution args to counter)."""
        structured_llm = self._llm.with_structured_output(ArgumentBatch)
        sub_dim_block = _format_sub_dimensions(dimensions)
        retry_section = f"\n\n{retry_hint}" if retry_hint else ""
        content = (
            f"SOURCE TEXT:\n{source_text}\n\n"
            f"TARGET TEXT:\n{target_text}\n\n"
            f"{sub_dim_block}\n"
            f"Round: {round}\n\n"
            "Make affirmative arguments about why the target text does NOT infringe the "
            "source, for each HIGH and CRITICAL sub-dimension where clear, unambiguous evidence "
            "exists. Highlight specific passages where the wording, imagery, and creative "
            "choices are distinctly different. If no such evidence exists anywhere, declare "
            f"no_further_arguments.{retry_section}"
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            arguments = [
                a.model_copy(update={"round": round, "agent_role": "defense"})
                for a in result.arguments
            ]
            return ArgumentBatch(
                arguments=arguments,
                no_further_arguments=result.no_further_arguments,
                closing_statement=result.closing_statement,
            )
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Defense failed to produce affirmative arguments.",
                context={"role": self.role, "round": round},
                suggestion="Check the LLM model supports structured output.",
                cause=exc,
            ) from exc
```

- [ ] **Step 2: Replace `tests/unit/agents/test_defense.py`**

Replace the whole file:

```python
# tests/unit/agents/test_defense.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.defense import Defense
from psalm.dimensions import CHARACTER, SCENES_A_FAIRE


@pytest.fixture
def defense(agent_config):
    return Defense(config=agent_config)


def test_defense_prompt_allows_affirmative_arguments():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "affirmative" in prompt or "proactive" in prompt or "you may also" in prompt


def test_defense_prompt_includes_idea_expression_doctrine():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "idea" in prompt and "expression" in prompt
    assert "unprotectable" in prompt or "not protected" in prompt


def test_defense_prompt_does_not_demand_strictly_verbatim():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "must include verbatim" not in prompt
    assert "passage" in prompt or "excerpt" in prompt or "quote" in prompt


def test_defense_system_prompt_forbids_padding_and_guesswork():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "unambiguous" in prompt
    assert "guess" in prompt or "speculative" in prompt
    assert "no_further_arguments" in prompt


async def test_defense_role(defense):
    assert defense.role == "defense"


async def test_gather_counter_arguments(defense, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(
            arguments=[sample_counter_argument], no_further_arguments=False, closing_statement=None
        )
    )

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        result = await defense.gather_counter_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=[CHARACTER],
            prosecutor_arguments=[sample_argument],
            round=1,
        )

    assert len(result.arguments) == 1
    assert result.arguments[0].agent_role == "defense"


async def test_defense_instruction_always_includes_both_types(defense, sample_argument):
    for prosecutor_arguments in [[], [sample_argument]]:
        captured: list = []

        async def capture_invoke(prompt, **kwargs):
            captured.extend(prompt)
            return MagicMock(arguments=[], no_further_arguments=False, closing_statement=None)

        mock_chain = MagicMock()
        mock_chain.ainvoke = capture_invoke
        mock_with_structured = MagicMock(return_value=mock_chain)
        captured.clear()
        with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
            await defense.gather_counter_arguments(
                "src", "tgt", [CHARACTER],
                prosecutor_arguments=prosecutor_arguments,
                round=1,
            )

        user_content = next(
            (m["content"] for m in captured if m["role"] == "user"), ""
        )
        label = "empty prosecution" if not prosecutor_arguments else "non-empty prosecution"
        assert (
            "affirmative" in user_content.lower()
            or "independently" in user_content.lower()
            or "proactive" in user_content.lower()
        ), f"Expected affirmative instruction with {label}: {user_content[:300]}"


async def test_counter_argument_includes_prosecutor_args_in_prompt(defense, sample_argument):
    captured_prompt = []

    async def capture_invoke(prompt, **kwargs):
        captured_prompt.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        await defense.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_argument], 1)

    user_content = next(m["content"] for m in captured_prompt if m["role"] == "user")
    assert "prosecutor" in user_content.lower() or "argument" in user_content.lower()


async def test_defense_gather_arguments_affirmative(defense, sample_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        result = await defense.gather_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=[CHARACTER],
            round=1,
        )
    assert len(result.arguments) == 1
    assert result.arguments[0].agent_role == "defense"


async def test_defense_gather_arguments_prompt_mentions_affirmative(defense, sample_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_arguments("src", "tgt", [CHARACTER], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "affirmative" in user_content.lower() or "distinct" in user_content.lower()


async def test_defense_counter_prompt_includes_sub_dimension_context(agent_config, sample_argument, sample_counter_argument):
    defense = Defense(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_counter_argument], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Identity & Properties" in user_content or "character" in user_content.lower()


async def test_defense_prompt_separates_infringement_and_exception_dimensions(agent_config, sample_argument):
    defense = Defense(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_arguments("src", "tgt", [CHARACTER, SCENES_A_FAIRE], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "PRIMARY DIMENSION (must argue): character" in user_content
    assert "AVAILABLE EXCEPTION TOOLS" in user_content
    assert "scenes-a-faire" in user_content


async def test_defense_retry_hint_appears_in_prompt(agent_config, sample_argument):
    defense = Defense(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_arguments(
            "src", "tgt", [CHARACTER], 1, retry_hint="You must either argue or declare done."
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "You must either argue or declare done." in user_content


async def test_gather_arguments_returns_no_further_arguments(defense):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(
            arguments=[], no_further_arguments=True, closing_statement="The defense rests."
        )
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        result = await defense.gather_arguments("src", "tgt", [CHARACTER], 1)

    assert result.arguments == []
    assert result.no_further_arguments is True
    assert result.closing_statement == "The defense rests."
```

- [ ] **Step 3: Run defense tests**

```
pytest tests/unit/agents/test_defense.py -v
```
Expected: all PASS

- [ ] **Step 4: Run full unit suite**

```
pytest tests/unit/ -v
```
Expected: FAIL only in `tests/unit/phases/test_argumentation_phase.py` (fixed in Task 8).

- [ ] **Step 5: Commit**

```bash
git add psalm/agents/defense.py tests/unit/agents/test_defense.py
git commit -m "feat: rewrite Defense to return ArgumentBatch with type-aware sub-dimensions and factual-only prompt"
```

---

### Task 8: `ArgumentationPhase` rewrite — completeness retry, closing statements, `_finalize_arguments`

**Files:**
- Modify: `psalm/phases/argumentation.py`
- Modify: `tests/unit/phases/test_argumentation_phase.py`

**Interfaces:**
- Consumes: `ArgumentBatch`, `ClosingStatement` (Task 3), `Judge.validate_batch_completeness` (Task 5), `Prosecutor`/`Defense` returning `ArgumentBatch` (Tasks 6, 7), `RoundArguments`/`ArgumentationState` closing-statement fields (Task 4)
- Produces: `ArgumentationPhase.run(case_input) -> ArgumentationLog` (unchanged signature; behavior extended)

- [ ] **Step 1: Update `psalm/phases/argumentation.py`**

Replace the whole file:

```python
from __future__ import annotations

from typing import Any, Awaitable, Callable

from langgraph.graph import END, StateGraph

from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.prosecutor import Prosecutor
from psalm.exceptions import PSALMAgentError
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import Argument, ArgumentBatch, ClosingStatement
from psalm.models.result import ArgumentationLog, RoundArguments
from psalm.models.state import ArgumentationState
from psalm.phases.base import BasePhase

_COMPLETENESS_RETRY_ATTEMPTS = 2
_COMPLETENESS_RETRY_HINT = (
    "Your previous response provided no arguments and did not declare "
    "no_further_arguments. You MUST either provide at least one factually-grounded "
    "argument, or explicitly set no_further_arguments=True with a closing_statement "
    "explaining why you have nothing further to add."
)


class ArgumentationPhase(BasePhase):
    def __init__(
        self,
        prosecutor: Prosecutor,
        defense: Defense,
        judge: Judge,
        config: DebateConfig,
    ) -> None:
        self._prosecutor = prosecutor
        self._defense = defense
        self._judge = judge
        self._config = config
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ArgumentationState)

        graph.add_node("prosecution_argue", self._prosecution_argue)
        graph.add_node("judge_validate_prosecution", self._judge_validate_prosecution)
        graph.add_node("defense_counter", self._defense_counter)
        graph.add_node("judge_validate_defense_counter", self._judge_validate_defense_counter)
        graph.add_node("defense_argue", self._defense_argue)
        graph.add_node("judge_validate_defense", self._judge_validate_defense)
        graph.add_node("prosecution_counter", self._prosecution_counter)
        graph.add_node("judge_validate_prosecution_counter", self._judge_validate_prosecution_counter)
        graph.add_node("check_next_round", self._check_next_round)
        graph.add_node("finalize_arguments", self._finalize_arguments)

        graph.set_entry_point("prosecution_argue")
        graph.add_edge("prosecution_argue", "judge_validate_prosecution")
        graph.add_edge("judge_validate_prosecution", "defense_counter")
        graph.add_edge("defense_counter", "judge_validate_defense_counter")
        graph.add_edge("judge_validate_defense_counter", "defense_argue")
        graph.add_edge("defense_argue", "judge_validate_defense")
        graph.add_edge("judge_validate_defense", "prosecution_counter")
        graph.add_edge("prosecution_counter", "judge_validate_prosecution_counter")
        graph.add_edge("judge_validate_prosecution_counter", "check_next_round")
        graph.add_conditional_edges(
            "check_next_round",
            self._route_next_round,
            {"continue": "prosecution_argue", "done": "finalize_arguments"},
        )
        graph.add_edge("finalize_arguments", END)

        return graph.compile()

    async def run(self, case_input: CaseInput) -> ArgumentationLog:
        initial_state = ArgumentationState(
            source_text=case_input.source_text,
            target_text=case_input.target_text,
            dimensions=case_input.dimensions,
            max_rounds=self._config.argumentation_rounds,
        )
        final_state = await self._graph.ainvoke(initial_state.model_dump())
        log_data = final_state["argumentation_log"]
        if isinstance(log_data, dict):
            return ArgumentationLog(**log_data)
        return log_data

    # --- Completeness-gated agent call wrapper ---

    async def _call_with_completeness_retry(
        self, call: Callable[[str | None], Awaitable[ArgumentBatch]]
    ) -> ArgumentBatch:
        hint: str | None = None
        for _attempt in range(_COMPLETENESS_RETRY_ATTEMPTS + 1):
            batch = await call(hint)
            if await self._judge.validate_batch_completeness(batch):
                return batch
            hint = _COMPLETENESS_RETRY_HINT
        raise PSALMAgentError(
            code="PSALM-A004",
            message="Agent failed to provide arguments or declare no_further_arguments after retries.",
            context={"attempts": _COMPLETENESS_RETRY_ATTEMPTS + 1},
            suggestion="Check the LLM model's instruction-following reliability.",
        )

    # --- Step 1: Prosecution affirmative arguments ---

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

    async def _judge_validate_prosecution(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_prosecution_arguments]
        valid = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg.model_dump())
        existing = [a.model_dump() for a in state.prosecution_arguments]
        return {
            "validated_prosecution_arguments": valid,
            "prosecution_arguments": existing + valid,
        }

    # --- Step 2: Defense counters prosecution ---

    async def _defense_counter(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        prosecution_args = [Argument(**a) for a in state.validated_prosecution_arguments]
        batch = await self._call_with_completeness_retry(
            lambda hint: self._defense.gather_counter_arguments(
                source_text=state.source_text,
                target_text=state.target_text,
                dimensions=state.dimensions,
                prosecutor_arguments=prosecution_args,
                round=round_num,
                retry_hint=hint,
            )
        )
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_defense_counters": [a.model_dump() for a in batch.arguments],
            "defense_counter_closing_statements": state.defense_counter_closing_statements + closing,
        }

    async def _judge_validate_defense_counter(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_defense_counters]
        valid = []
        for arg in pending:
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense"
            )
            if result.is_valid:
                valid.append(arg.model_dump())
        existing = [a.model_dump() for a in state.defense_counters]
        return {
            "defense_counters": existing + valid,
        }

    # --- Step 3: Defense affirmative arguments ---

    async def _defense_argue(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        batch = await self._call_with_completeness_retry(
            lambda hint: self._defense.gather_arguments(
                source_text=state.source_text,
                target_text=state.target_text,
                dimensions=state.dimensions,
                round=round_num,
                retry_hint=hint,
            )
        )
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_defense_arguments": [a.model_dump() for a in batch.arguments],
            "defense_closing_statements": state.defense_closing_statements + closing,
        }

    async def _judge_validate_defense(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_defense_arguments]
        valid = []
        for arg in pending:
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense"
            )
            if result.is_valid:
                valid.append(arg.model_dump())
        existing = [a.model_dump() for a in state.defense_arguments]
        return {
            "validated_defense_arguments": valid,
            "defense_arguments": existing + valid,
        }

    # --- Step 4: Prosecution counters defense ---

    async def _prosecution_counter(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        defense_args = [Argument(**a) for a in state.validated_defense_arguments]
        batch = await self._call_with_completeness_retry(
            lambda hint: self._prosecutor.gather_counter_arguments(
                source_text=state.source_text,
                target_text=state.target_text,
                dimensions=state.dimensions,
                defense_arguments=defense_args,
                round=round_num,
                retry_hint=hint,
            )
        )
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_prosecution_counters": [a.model_dump() for a in batch.arguments],
            "prosecution_counter_closing_statements": state.prosecution_counter_closing_statements + closing,
        }

    async def _judge_validate_prosecution_counter(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_prosecution_counters]
        valid = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg.model_dump())
        existing = [a.model_dump() for a in state.prosecution_counters]
        return {
            "prosecution_counters": existing + valid,
        }

    # --- Round control ---

    async def _check_next_round(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        pros_this_round = [a for a in state.prosecution_arguments if a.round == round_num]
        def_counters_this_round = [a for a in state.defense_counters if a.round == round_num]
        def_this_round = [a for a in state.defense_arguments if a.round == round_num]
        pros_counters_this_round = [a for a in state.prosecution_counters if a.round == round_num]
        both_empty = (
            len(pros_this_round) == 0
            and len(def_counters_this_round) == 0
            and len(def_this_round) == 0
            and len(pros_counters_this_round) == 0
        )
        stability = await self._judge.detect_stability(
            [Argument(**a) for a in state.validated_prosecution_arguments],
            [a for a in state.prosecution_arguments if a.round == state.current_round],
        )
        return {
            "current_round": state.current_round + 1,
            "stability_detected": stability or both_empty,
        }

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
            if (
                pros_args or def_counters or def_args or pros_counters
                or pros_closing or def_counter_closing or def_closing or pros_counter_closing
            ):
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

    # --- Routing ---

    def _route_next_round(self, state: ArgumentationState) -> str:
        if state.stability_detected or state.current_round >= state.max_rounds:
            return "done"
        return "continue"
```

- [ ] **Step 2: Replace `tests/unit/phases/test_argumentation_phase.py`**

Replace the whole file:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from psalm.dimensions import CHARACTER
from psalm.exceptions import PSALMAgentError
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import Argument, ArgumentBatch, Proof
from psalm.models.result import ArgumentationLog
from psalm.phases.argumentation import ArgumentationPhase


def _make_arg(dimension: str = "character", round: int = 1, role: str = "prosecutor") -> Argument:
    return Argument(
        claim="Test claim.",
        dimension=dimension,
        proofs=[Proof(source_excerpt="src", target_excerpt="tgt", relevance="rel")],
        agent_role=role,
        round=round,
    )


def _make_batch(arguments: list[Argument] | None = None) -> ArgumentBatch:
    if arguments:
        return ArgumentBatch(arguments=arguments)
    return ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further to add.")


@pytest.fixture
def mock_prosecutor():
    p = MagicMock()
    p.gather_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="prosecutor")]))
    p.gather_counter_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="prosecutor")]))
    return p


@pytest.fixture
def mock_defense():
    d = MagicMock()
    d.gather_counter_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="defense")]))
    d.gather_arguments = AsyncMock(return_value=_make_batch([_make_arg(role="defense")]))
    return d


@pytest.fixture
def mock_judge():
    j = MagicMock()
    j.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    j.detect_stability = AsyncMock(return_value=False)
    j.validate_batch_completeness = AsyncMock(return_value=True)
    return j


@pytest.fixture
def argumentation_phase(mock_prosecutor, mock_defense, mock_judge):
    config = DebateConfig(
        dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1
    )
    return ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)


@pytest.fixture
def case_input():
    return CaseInput(source_text="source text", target_text="target text", dimensions=[CHARACTER])


async def test_run_returns_argumentation_log(argumentation_phase, case_input):
    result = await argumentation_phase.run(case_input)
    assert isinstance(result, ArgumentationLog)


async def test_round_has_four_argument_sets(argumentation_phase, case_input):
    result = await argumentation_phase.run(case_input)
    assert len(result.rounds) >= 1
    r = result.rounds[0]
    assert hasattr(r, "prosecution_arguments")
    assert hasattr(r, "defense_counters")
    assert hasattr(r, "defense_arguments")
    assert hasattr(r, "prosecution_counters")


async def test_all_four_agent_methods_called(argumentation_phase, case_input, mock_prosecutor, mock_defense):
    await argumentation_phase.run(case_input)
    mock_prosecutor.gather_arguments.assert_called()
    mock_defense.gather_counter_arguments.assert_called()
    mock_defense.gather_arguments.assert_called()
    mock_prosecutor.gather_counter_arguments.assert_called()


async def test_stop_when_both_sides_empty(mock_judge):
    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=5, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    await phase.run(case_input)
    assert mock_prosecutor.gather_arguments.call_count == 1


async def test_continues_when_only_one_side_empty(mock_judge):
    call_count = 0

    async def prosecution_with_falloff(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_batch([_make_arg(role="prosecutor")])
        return _make_batch()

    async def defense_argues_every_round(*args, **kwargs):
        return _make_batch([_make_arg(role="defense", round=kwargs["round"])])

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_with_falloff)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(side_effect=defense_argues_every_round)

    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=3, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    await phase.run(case_input)
    # both_empty requires ALL four steps empty; defense_arguments stays non-empty every
    # round, so the debate continues through round 3 (max_rounds).
    assert mock_prosecutor.gather_arguments.call_count == 3


async def test_continues_when_step_two_nonempty_but_steps_one_and_three_empty(mock_judge):
    async def prosecution_first_round_only(*args, **kwargs):
        if kwargs["round"] == 1:
            return _make_batch([_make_arg(role="prosecutor", round=1)])
        return _make_batch()

    async def defense_counters_every_round(*args, **kwargs):
        return _make_batch([_make_arg(role="defense", round=kwargs["round"])])

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_first_round_only)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(side_effect=defense_counters_every_round)
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())

    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=3, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    await phase.run(case_input)
    assert mock_prosecutor.gather_arguments.call_count == 3
    assert mock_defense.gather_counter_arguments.call_count == 3


async def test_closing_statement_recorded_in_round(mock_judge):
    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="The prosecution rests.")
    )
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    result = await phase.run(case_input)
    assert len(result.rounds) == 1
    assert result.rounds[0].prosecution_closing_statement == "The prosecution rests."


async def test_completeness_retry_triggers_on_ambiguous_batch(mock_judge):
    call_count = 0

    async def ambiguous_then_valid(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ArgumentBatch()  # empty, no_further_arguments=False — ambiguous
        return _make_batch([_make_arg(role="prosecutor")])

    completeness_calls = 0

    async def completeness_side_effect(batch):
        nonlocal completeness_calls
        completeness_calls += 1
        return completeness_calls > 1

    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(side_effect=ambiguous_then_valid)
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)
    mock_judge.validate_batch_completeness = AsyncMock(side_effect=completeness_side_effect)

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    await phase.run(case_input)
    assert call_count == 2  # retried once before succeeding


async def test_completeness_retry_exhausted_raises(mock_judge):
    mock_prosecutor = MagicMock()
    mock_prosecutor.gather_arguments = AsyncMock(return_value=ArgumentBatch())  # always ambiguous
    mock_prosecutor.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense = MagicMock()
    mock_defense.gather_counter_arguments = AsyncMock(return_value=_make_batch())
    mock_defense.gather_arguments = AsyncMock(return_value=_make_batch())
    mock_judge.validate_argument = AsyncMock(return_value=MagicMock(is_valid=True))
    mock_judge.detect_stability = AsyncMock(return_value=False)
    mock_judge.validate_batch_completeness = AsyncMock(return_value=False)  # never satisfied

    config = DebateConfig(dimensions=[CHARACTER], argumentation_rounds=1, deliberation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])

    with pytest.raises(PSALMAgentError) as exc_info:
        await phase.run(case_input)
    assert exc_info.value.code == "PSALM-A004"
```

- [ ] **Step 3: Run tests to confirm they fail first, then pass**

```
pytest tests/unit/phases/test_argumentation_phase.py -v
```
Run once before Step 1's implementation change to confirm failures (`AttributeError`/`ImportError` on `ArgumentBatch`), then again after — expected all PASS after the implementation is in place.

- [ ] **Step 4: Run full unit suite**

```
pytest tests/unit/ -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add psalm/phases/argumentation.py tests/unit/phases/test_argumentation_phase.py
git commit -m "feat: route ArgumentationPhase through ArgumentBatch with completeness-retry and closing statements"
```

---

### Task 9: Integration tests for `ArgumentationPhase`

**Files:**
- Modify: `tests/integration/test_argumentation_phase.py`

**Interfaces:**
- Consumes: `ArgumentationPhase` (Task 8), `ArgumentBatch` (Task 3)

- [ ] **Step 1: Replace `tests/integration/test_argumentation_phase.py`**

Replace the whole file:

```python
# tests/integration/test_argumentation_phase.py
from unittest.mock import AsyncMock

import pytest

from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.prosecutor import Prosecutor
from psalm.dimensions import CHARACTER
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import ArgumentBatch
from psalm.models.result import ValidationResult
from psalm.phases.argumentation import ArgumentationPhase


@pytest.fixture
def case_input():
    return CaseInput(
        source_text="The wizard had bright blue eyes and wore a silver cloak.",
        target_text="The sorcerer possessed azure irises and donned a grey mantle.",
        dimensions=[CHARACTER],
    )


@pytest.fixture
def mock_prosecutor(agent_config, sample_argument):
    prosecutor = AsyncMock(spec=Prosecutor)
    prosecutor.gather_arguments = AsyncMock(return_value=ArgumentBatch(arguments=[sample_argument]))
    prosecutor.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="No rebuttal needed.")
    )
    return prosecutor


@pytest.fixture
def mock_defense(agent_config, sample_counter_argument):
    defense = AsyncMock(spec=Defense)
    defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(arguments=[sample_counter_argument])
    )
    defense.gather_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="The defense rests.")
    )
    return defense


@pytest.fixture
def mock_judge(agent_config):
    judge = AsyncMock(spec=Judge)
    judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=True))
    judge.detect_stability = AsyncMock(return_value=False)
    judge.validate_batch_completeness = AsyncMock(return_value=True)
    return judge


@pytest.fixture
def argumentation_phase(mock_prosecutor, mock_defense, mock_judge):
    config = DebateConfig(argumentation_rounds=2)
    return ArgumentationPhase(
        prosecutor=mock_prosecutor,
        defense=mock_defense,
        judge=mock_judge,
        config=config,
    )


async def test_argumentation_phase_runs(argumentation_phase, case_input):
    log = await argumentation_phase.run(case_input)
    assert log is not None
    assert len(log.rounds) > 0


async def test_argumentation_phase_calls_prosecutor(argumentation_phase, case_input, mock_prosecutor):
    await argumentation_phase.run(case_input)
    assert mock_prosecutor.gather_arguments.called


async def test_argumentation_phase_calls_defense(argumentation_phase, case_input, mock_defense):
    await argumentation_phase.run(case_input)
    assert mock_defense.gather_counter_arguments.called


async def test_argumentation_phase_validates_arguments(argumentation_phase, case_input, mock_judge):
    await argumentation_phase.run(case_input)
    assert mock_judge.validate_argument.called


async def test_invalid_arguments_excluded(mock_prosecutor, mock_defense, mock_judge, case_input):
    # When judge rejects everything, a round is only recorded if it carries at least one
    # argument OR at least one closing statement.
    mock_judge.validate_argument = AsyncMock(return_value=ValidationResult(is_valid=False, rejection_reason="No excerpts."))
    mock_defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing to counter.")
    )
    config = DebateConfig(argumentation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    for round_rec in log.rounds:
        assert (
            round_rec.prosecution_arguments != []
            or round_rec.defense_counters != []
            or round_rec.defense_arguments != []
            or round_rec.prosecution_counters != []
            or round_rec.prosecution_closing_statement is not None
            or round_rec.defense_counter_closing_statement is not None
            or round_rec.defense_closing_statement is not None
            or round_rec.prosecution_counter_closing_statement is not None
        )


async def test_stability_terminates_early(mock_prosecutor, mock_defense, mock_judge, case_input):
    mock_judge.detect_stability = AsyncMock(return_value=True)
    config = DebateConfig(argumentation_rounds=5)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    assert len(log.rounds) == 1


async def test_empty_round_stops_loop(mock_prosecutor, mock_defense, mock_judge, case_input):
    mock_prosecutor.gather_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")
    )
    mock_defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing to counter.")
    )
    config = DebateConfig(argumentation_rounds=5)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    await phase.run(case_input)
    assert mock_prosecutor.gather_arguments.call_count == 1


async def test_closing_statement_rounds_are_recorded(mock_prosecutor, mock_defense, mock_judge, case_input, sample_argument):
    # A round where prosecution declares done but later rounds resume must be recorded
    # (not silently dropped) — the closing statement itself is round content.
    call_count = 0

    async def prosecution_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ArgumentBatch(no_further_arguments=True, closing_statement="Nothing yet.")
        return ArgumentBatch(arguments=[sample_argument])

    mock_prosecutor.gather_arguments = AsyncMock(side_effect=prosecution_side_effect)
    mock_defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing to counter.")
    )
    config = DebateConfig(argumentation_rounds=3)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    log = await phase.run(case_input)
    assert len(log.rounds) >= 1
    assert log.rounds[0].prosecution_closing_statement == "Nothing yet."


async def test_defense_is_always_called_regardless_of_prosecution(
    mock_prosecutor, mock_defense, mock_judge, case_input
):
    mock_prosecutor.gather_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")
    )
    mock_defense.gather_counter_arguments = AsyncMock(
        return_value=ArgumentBatch(no_further_arguments=True, closing_statement="Nothing to counter.")
    )
    config = DebateConfig(argumentation_rounds=1)
    phase = ArgumentationPhase(mock_prosecutor, mock_defense, mock_judge, config)
    await phase.run(case_input)
    assert mock_defense.gather_counter_arguments.called, "defense was never called"
```

- [ ] **Step 2: Run tests**

```
pytest tests/integration/test_argumentation_phase.py -v
```
Expected: all PASS

- [ ] **Step 3: Run full unit + integration suite**

```
pytest tests/unit/ tests/integration/ -v
```
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_argumentation_phase.py
git commit -m "test: update ArgumentationPhase integration tests for ArgumentBatch and closing statements"
```

---

### Task 10: `DefaultCourtroom` — exception-dimension scoping + aggregation filtering

**Files:**
- Modify: `psalm/courtroom/default.py`
- Modify: `tests/unit/courtroom/test_verdict_aggregation.py`
- Create: `tests/unit/courtroom/test_exception_dimension_scoping.py`

**Interfaces:**
- Consumes: `Dimension.dimension_type` (Task 1), `DimensionVerdict.dimension_type` (Task 2)
- Produces: `DefaultCourtroom._run_single_dimension` injects exception dimensions as auxiliary context under `FULLY_SEPARATE`; `_aggregate_verdict`/`_synthesize_rationale` filter to `dimension_type == "infringement"`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/courtroom/test_verdict_aggregation.py`:

```python
def test_exception_dimension_excluded_from_aggregation():
    from psalm.models.result import DimensionVerdict
    dvs = [
        _make_dv("character", Importance.HIGH, "Guilty", 0.9),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Guilty",
            weighted_score=0.1,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    # Only the infringement dimension (character, HIGH, 0.9) drives the aggregation; the
    # exception dimension's low weighted_score must not pull it down.
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Guilty"


def test_exception_only_verdicts_is_undecided():
    from psalm.models.result import DimensionVerdict
    dvs = [
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
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Undecided"


def test_exception_critical_guilty_does_not_trigger_hard_override():
    from psalm.models.result import DimensionVerdict
    dvs = [
        _make_dv("character", Importance.HIGH, "Not Guilty", 0.1),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.CRITICAL,
            verdict="Guilty",
            weighted_score=0.95,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    # CRITICAL + Guilty must NOT trigger the hard override when it's an exception dimension —
    # only infringement dimensions can trigger it.
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Not Guilty"


def test_synthesize_rationale_labels_exception_dimensions():
    from psalm.models.result import DimensionVerdict
    dvs = [
        _make_dv("character", Importance.HIGH, "Guilty", 0.8),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Not Guilty",
            weighted_score=0.2,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    rationale = _synthesize_rationale("Guilty", dvs)
    assert "scenes-a-faire" in rationale
    assert "excluded from verdict" in rationale
```

Create `tests/unit/courtroom/test_exception_dimension_scoping.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from psalm.courtroom.default import DefaultCourtroom
from psalm.dimensions import CHARACTER, SCENES_A_FAIRE
from psalm.models.config import CaseInput, DebateConfig, EvaluationStrategy
from psalm.models.result import DebateLog, ArgumentationLog


@pytest.fixture
def mock_argumentation_phase():
    phase = MagicMock()
    phase.run = AsyncMock(return_value=ArgumentationLog(rounds=[]))
    return phase


@pytest.fixture
def mock_deliberation_phases():
    phases = []
    for _ in range(2):
        p = MagicMock()
        p.run = AsyncMock(
            return_value=("Not Guilty", DebateLog(rounds=[], final_voting_strategy_applied="unanimous"), 0.2)
        )
        phases.append(p)
    return phases


async def test_infringement_dimension_gets_exception_dims_injected(mock_argumentation_phase, mock_deliberation_phases):
    config = DebateConfig(
        dimensions=[CHARACTER, SCENES_A_FAIRE],
        evaluation_strategy=EvaluationStrategy.FULLY_SEPARATE,
    )
    courtroom = DefaultCourtroom(mock_argumentation_phase, mock_deliberation_phases, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER, SCENES_A_FAIRE])

    await courtroom.run(case_input)

    scoped_inputs = [call.args[0] for call in mock_argumentation_phase.run.call_args_list]
    character_call = next(ci for ci in scoped_inputs if ci.dimensions[0].name == "character")
    assert {d.name for d in character_call.dimensions} == {"character", "scenes-a-faire"}


async def test_exception_dimension_runs_standalone(mock_argumentation_phase, mock_deliberation_phases):
    config = DebateConfig(
        dimensions=[CHARACTER, SCENES_A_FAIRE],
        evaluation_strategy=EvaluationStrategy.FULLY_SEPARATE,
    )
    courtroom = DefaultCourtroom(mock_argumentation_phase, mock_deliberation_phases, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER, SCENES_A_FAIRE])

    await courtroom.run(case_input)

    scoped_inputs = [call.args[0] for call in mock_argumentation_phase.run.call_args_list]
    exception_call = next(ci for ci in scoped_inputs if ci.dimensions[0].name == "scenes-a-faire")
    assert [d.name for d in exception_call.dimensions] == ["scenes-a-faire"]


async def test_dimension_verdicts_carry_dimension_type(mock_argumentation_phase, mock_deliberation_phases):
    config = DebateConfig(
        dimensions=[CHARACTER, SCENES_A_FAIRE],
        evaluation_strategy=EvaluationStrategy.FULLY_SEPARATE,
    )
    courtroom = DefaultCourtroom(mock_argumentation_phase, mock_deliberation_phases, config)
    case_input = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER, SCENES_A_FAIRE])

    result = await courtroom.run(case_input)

    by_name = {dv.dimension: dv.dimension_type for dv in result.dimension_verdicts}
    assert by_name["character"] == "infringement"
    assert by_name["scenes-a-faire"] == "exception"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/unit/courtroom/ -v
```
Expected: FAIL — `_aggregate_verdict` doesn't filter by `dimension_type` yet; `_run_single_dimension` doesn't inject exception dimensions yet.

- [ ] **Step 3: Update `psalm/courtroom/default.py`**

Replace the whole file:

```python
from __future__ import annotations

import asyncio
import time
from typing import Literal

from psalm.courtroom.base import CourtroomSetup
from psalm.dimensions.base import Dimension, Importance, _IMPORTANCE_MULTIPLIERS
from psalm.models.config import CaseInput, DebateConfig, EvaluationStrategy
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
    DimensionVerdict,
    PSALMResult,
    ResultMetadata,
)
from psalm.phases.argumentation import ArgumentationPhase
from psalm.phases.deliberation import DeliberationPhase


class DefaultCourtroom(CourtroomSetup):
    def __init__(
        self,
        argumentation_phase: ArgumentationPhase,
        deliberation_phases: list[DeliberationPhase],
        config: DebateConfig,
    ) -> None:
        self._argumentation_phase = argumentation_phase
        self._deliberation_phases = deliberation_phases
        self._config = config

    async def run(self, case_input: CaseInput) -> PSALMResult:
        start = time.monotonic()
        strategy = self._config.evaluation_strategy

        if strategy == EvaluationStrategy.FULLY_SEPARATE:
            dimension_verdicts = await self._run_fully_separate(case_input)
        elif strategy == EvaluationStrategy.SHARED_ARG_PER_DIM_DELIBERATION:
            dimension_verdicts = await self._run_shared_arg(case_input)
        else:  # SHARED_ALL
            dimension_verdicts = await self._run_shared_all(case_input)

        verdict = _aggregate_verdict(dimension_verdicts, self._config.guilty_threshold)
        rationale = _synthesize_rationale(verdict, dimension_verdicts)
        duration = time.monotonic() - start

        # Dimension verdicts may share the same ArgumentationLog instance (e.g. under
        # SHARED_ARG_PER_DIM_DELIBERATION / SHARED_ALL, one argumentation phase run is
        # reused across all dimensions). Dedup by object identity before summing rounds
        # so shared logs are not counted once per dimension.
        distinct_arg_logs = {id(dv.argumentation_log): dv.argumentation_log for dv in dimension_verdicts}
        total_arg_rounds = sum(len(log.rounds) for log in distinct_arg_logs.values())
        total_delib_rounds = sum(len(dv.debate_log.rounds) for dv in dimension_verdicts)
        strategy_applied = dimension_verdicts[0].debate_log.final_voting_strategy_applied if dimension_verdicts else "none"

        metadata = ResultMetadata(
            duration_seconds=round(duration, 3),
            argumentation_rounds_used=total_arg_rounds,
            deliberation_rounds_used=total_delib_rounds,
            voting_strategy_applied=strategy_applied,
        )
        return PSALMResult(
            verdict=verdict,
            rationale=rationale,
            dimension_verdicts=dimension_verdicts,
            metadata=metadata,
        )

    async def _run_fully_separate(self, case_input: CaseInput) -> list[DimensionVerdict]:
        tasks = [
            self._run_single_dimension(dim, delib_phase, case_input)
            for dim, delib_phase in zip(case_input.dimensions, self._deliberation_phases, strict=True)
        ]
        return list(await asyncio.gather(*tasks))

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
            scoped_dims = [dimension]
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

    async def _run_shared_arg(self, case_input: CaseInput) -> list[DimensionVerdict]:
        arg_log = await self._argumentation_phase.run(case_input)
        tasks = [
            self._deliberate_single(dim, delib_phase, arg_log)
            for dim, delib_phase in zip(case_input.dimensions, self._deliberation_phases, strict=True)
        ]
        return list(await asyncio.gather(*tasks))

    async def _deliberate_single(
        self,
        dimension: Dimension,
        delib_phase: DeliberationPhase,
        arg_log: ArgumentationLog,
    ) -> DimensionVerdict:
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

    async def _run_shared_all(self, case_input: CaseInput) -> list[DimensionVerdict]:
        arg_log = await self._argumentation_phase.run(case_input)
        delib_phase = self._deliberation_phases[0]
        tasks = [
            self._deliberate_single(dim, delib_phase, arg_log)
            for dim in case_input.dimensions
        ]
        return list(await asyncio.gather(*tasks))


def _aggregate_verdict(
    dimension_verdicts: list[DimensionVerdict],
    guilty_threshold: float,
) -> Literal["Guilty", "Not Guilty", "Undecided"]:
    infringement_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "infringement"]
    if not infringement_verdicts:
        return "Undecided"

    # Hard override: any CRITICAL infringement dimension that is Guilty → overall Guilty
    for dv in infringement_verdicts:
        if dv.importance == Importance.CRITICAL and dv.verdict == "Guilty":
            return "Guilty"

    # Weighted score aggregation — exception dimensions never contribute
    total_weighted = 0.0
    total_weight = 0.0
    for dv in infringement_verdicts:
        multiplier = _IMPORTANCE_MULTIPLIERS[dv.importance]
        total_weighted += dv.weighted_score * multiplier
        total_weight += multiplier

    if total_weight == 0.0:
        return "Undecided"

    normalised = total_weighted / total_weight
    if normalised >= guilty_threshold:
        return "Guilty"
    return "Not Guilty"


def _synthesize_rationale(
    verdict: str,
    dimension_verdicts: list[DimensionVerdict],
) -> str:
    lines = [f"Verdict: {verdict}."]
    for dv in dimension_verdicts:
        suffix = "" if dv.dimension_type == "infringement" else " [exception, excluded from verdict]"
        lines.append(
            f"  {dv.dimension} [{dv.importance.value}]{suffix}: {dv.verdict} "
            f"(weighted score: {dv.weighted_score:.2f})"
        )
    return " ".join(lines)
```

- [ ] **Step 4: Run courtroom tests**

```
pytest tests/unit/courtroom/ -v
```
Expected: all PASS

- [ ] **Step 5: Run full unit suite**

```
pytest tests/unit/ -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add psalm/courtroom/default.py tests/unit/courtroom/test_verdict_aggregation.py tests/unit/courtroom/test_exception_dimension_scoping.py
git commit -m "feat: inject exception dimensions as auxiliary context under FULLY_SEPARATE; exclude them from verdict aggregation"
```

---

### Task 11: `builder.py` identical-texts shortcut + e2e mock pipeline fix

**Files:**
- Modify: `psalm/builder.py`
- Modify: `tests/unit/test_builder.py`
- Modify: `tests/e2e/test_full_evaluation.py`

**Interfaces:**
- Consumes: `DimensionVerdict.dimension_type` (Task 2), `ArgumentBatch` (Task 3), `Judge.validate_batch_completeness` (Task 5)

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_builder.py`:

```python
async def test_identical_texts_result_sets_dimension_type():
    courtroom = await _build_psalm()
    result = courtroom._identical_texts_result("some text")
    assert result.dimension_verdicts[0].dimension_type == "infringement"
```

- [ ] **Step 2: Run test to confirm it fails**

```
pytest tests/unit/test_builder.py -v -k "identical_texts_result_sets_dimension_type"
```
Expected: FAIL — `DimensionVerdict` construction inside `_identical_texts_result` doesn't set `dimension_type` explicitly (it would currently default to `"infringement"` anyway via the Task 2 default, so this test actually documents the intended explicit wiring rather than catching a bug — confirm it passes trivially before Step 3, then keep it as a regression guard).

- [ ] **Step 3: Update `_identical_texts_result` in `psalm/builder.py`**

Add `dimension_type=dim.dimension_type,` to the `DimensionVerdict` construction inside `_identical_texts_result`:

```python
    def _identical_texts_result(self, text: str) -> PSALMResult:
        from psalm.dimensions.base import Importance
        from psalm.models.result import (
            ArgumentationLog,
            DebateLog,
            DimensionVerdict,
            ResultMetadata,
        )
        dim_verdicts = [
            DimensionVerdict(
                dimension=dim.name,
                dimension_type=dim.dimension_type,
                importance=dim.importance,
                verdict="Guilty",
                weighted_score=1.0,
                argumentation_log=ArgumentationLog(rounds=[]),
                debate_log=DebateLog(rounds=[], final_voting_strategy_applied="none"),
            )
            for dim in self._debate_config.dimensions
        ]
        return PSALMResult(
            verdict="Guilty",
            rationale=(
                "Source and target texts are identical — infringement confirmed without agent "
                "evaluation."
            ),
            dimension_verdicts=dim_verdicts,
            metadata=ResultMetadata(
                duration_seconds=0.0,
                argumentation_rounds_used=0,
                deliberation_rounds_used=0,
                voting_strategy_applied="none",
            ),
        )
```

- [ ] **Step 4: Run test**

```
pytest tests/unit/test_builder.py -v
```
Expected: all PASS

- [ ] **Step 5: Fix `tests/e2e/test_full_evaluation.py::test_e2e_mock_full_pipeline`**

This test was already stale before this plan (it asserts on `result.argumentation_log`/`result.debate_log`, which were removed from `PSALMResult` by an earlier plan and replaced with `dimension_verdicts`). It also patches `Prosecutor.gather_arguments`/`Defense.gather_counter_arguments` to return raw lists, which breaks under this plan's `ArgumentBatch` return type. Replace the whole `test_e2e_mock_full_pipeline` function:

```python
async def test_e2e_mock_full_pipeline(cases):
    from psalm.models.evidence import Argument, ArgumentBatch, Proof

    sample_proof = Proof(
        source_excerpt="silver hair that shimmered like moonlight",
        target_excerpt="shimmering silver locks",
        relevance="Both describe the same distinctive silver hair.",
    )
    sample_arg = Argument(
        claim="Characters share silver hair trait.",
        dimension="character",
        proofs=[sample_proof],
        agent_role="prosecutor",
        round=1,
    )
    sample_counter = Argument(
        claim="Silver hair is a generic fantasy trope.",
        dimension="character",
        proofs=[sample_proof],
        agent_role="defense",
        round=1,
    )
    no_further = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further to add.")

    with (
        patch(
            "psalm.agents.prosecutor.Prosecutor.gather_arguments",
            new=AsyncMock(return_value=ArgumentBatch(arguments=[sample_arg])),
        ),
        patch(
            "psalm.agents.prosecutor.Prosecutor.gather_counter_arguments",
            new=AsyncMock(return_value=no_further),
        ),
        patch(
            "psalm.agents.defense.Defense.gather_counter_arguments",
            new=AsyncMock(return_value=ArgumentBatch(arguments=[sample_counter])),
        ),
        patch(
            "psalm.agents.defense.Defense.gather_arguments",
            new=AsyncMock(return_value=no_further),
        ),
        patch(
            "psalm.agents.judge.Judge.validate_argument",
            new=AsyncMock(return_value=ValidationResult(is_valid=True)),
        ),
        patch(
            "psalm.agents.judge.Judge.detect_stability",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "psalm.agents.judge.Judge.validate_batch_completeness",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "psalm.agents.juror.Juror.discuss",
            new=AsyncMock(return_value="I believe this infringes."),
        ),
        patch(
            "psalm.agents.juror.Juror.vote",
            new=AsyncMock(
                return_value=JurorVote(
                    juror_id="juror-0", vote="Guilty", rationale="Strong evidence."
                )
            ),
        ),
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
    ):
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .with_dimensions([CHARACTER])
            .with_debate(argumentation_rounds=1, deliberation_rounds=1, time_limit_seconds=60)
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .build()
        )
        result = await psalm.aevaluate(
            source_text=cases[0]["source"],
            target_text=cases[0]["target"],
        )

    assert isinstance(result, PSALMResult)
    assert result.verdict in {"Guilty", "Not Guilty", "Undecided"}
    assert result.rationale
    assert len(result.dimension_verdicts) == 1
    assert len(result.dimension_verdicts[0].argumentation_log.rounds) > 0
    assert len(result.dimension_verdicts[0].debate_log.rounds) > 0
    assert result.metadata.duration_seconds >= 0
```

- [ ] **Step 6: Run e2e tests**

```
pytest tests/e2e/test_full_evaluation.py -v
```
Expected: `test_e2e_mock_full_pipeline` and `test_identical_texts_returns_guilty_immediately` PASS. `test_e2e_real_llm` is skipped unless `PSALM_E2E=true` is set (existing, unrelated behavior).

- [ ] **Step 7: Commit**

```bash
git add psalm/builder.py tests/unit/test_builder.py tests/e2e/test_full_evaluation.py
git commit -m "fix: set dimension_type in identical-texts shortcut; update stale e2e mock pipeline test for ArgumentBatch"
```

---

### Task 12: Full-suite verification

**Files:** None (verification only)

- [ ] **Step 1: Run the complete test suite**

```
pytest tests/ -v
```
Expected: ALL tests PASS (except `test_e2e_real_llm`, which is skipped by default — set `PSALM_E2E=true` only if you have live credentials to exercise it, not required for this plan).

- [ ] **Step 2: Spot-check the spec's key behaviors manually**

Confirm each of the following by reading the final code (no new test required — this is a design-intent sanity check):
- `psalm/agents/prosecutor.py` and `psalm/agents/defense.py` no longer contain the phrase "including generic or weak ones" or unconditional "You MUST produce at least one argument" language.
- `psalm/courtroom/default.py::_run_single_dimension` scopes infringement dimensions to `[dimension] + exception_dims` and exception dimensions to `[dimension]` alone.
- `psalm/courtroom/default.py::_aggregate_verdict` filters to `dimension_type == "infringement"` before computing the hard override and weighted sum.

- [ ] **Step 3: Confirm no regressions in dimension architecture or evaluation strategy tests**

```
pytest tests/integration/test_dimension_architecture.py tests/unit/test_builder.py -v
```
Expected: all PASS (these were not directly modified by this plan but exercise `Dimension`/`EvaluationStrategy` machinery this plan touches).

- [ ] **Step 4: Final commit (only if Step 2/3 surfaced fixes)**

```bash
git add -p
git commit -m "fix: address full-suite verification findings for argumentation phase v2"
```

If no fixes were needed, skip this step — Task 11's commit is the last one.

---

## Self-Review Checklist

1. **Spec §2 (Dimension type)** — Task 1 (`Dimension.dimension_type`), Task 2 (`DimensionVerdict.dimension_type`). ✓
2. **Spec §3.1–3.2 (Cross-dimension wiring, FULLY_SEPARATE)** — Task 10 (`_run_single_dimension`). ✓
3. **Spec §3.2 (SHARED_ARG/SHARED_ALL need no orchestration change)** — confirmed unchanged in Task 10; covered by the type-aware `_format_sub_dimensions` change in Tasks 6–7. ✓
4. **Spec §3.3 (Aggregation excludes exception dimensions)** — Task 10 (`_aggregate_verdict`, `_synthesize_rationale`) + new tests. ✓
5. **Spec §4 (Type-aware prompt formatting)** — Tasks 6–7 (`_format_sub_dimensions` in both `prosecutor.py`/`defense.py`). ✓
6. **Spec §5 (Explicit no-further-arguments signal)** — Task 3 (`ArgumentBatch`, `ClosingStatement`), Task 4 (`RoundArguments`/`ArgumentationState` fields), Tasks 6–7 (agent methods return `ArgumentBatch`), Task 8 (`ArgumentationPhase` wiring + `_finalize_arguments`). ✓
7. **Spec §5.5 (Stop condition unchanged)** — no code change made to `_check_next_round`; documented in Global Constraints. ✓
8. **Spec §6.1 (Factual/unambiguous prompts)** — Tasks 6–7 (`_SYSTEM_PROMPT` rewrites). ✓
9. **Spec §6.2 (Judge hedging/speculation gate)** — Task 5 (`_PROSECUTION_VALIDATION_PROMPT`/`_DEFENSE_VALIDATION_PROMPT`). ✓
10. **Spec §6.3 (Batch completeness gate)** — Task 5 (`Judge.validate_batch_completeness`), Task 8 (`_call_with_completeness_retry`, `PSALM-A004`). ✓
11. **User follow-up (Judge intervenes on ambiguous empty batch)** — Task 5 + Task 8, with dedicated retry-then-raise tests. ✓
12. **Placeholder scan** — no TBD/TODO; every step has complete, runnable code. ✓
13. **Type consistency** — `ArgumentBatch` used identically across Tasks 3, 5, 6, 7, 8, 9, 11; `dimension_type` literal values (`"infringement"`/`"exception"`) consistent across Tasks 1, 2, 10. ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-07-12-argumentation-phase-v2.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
