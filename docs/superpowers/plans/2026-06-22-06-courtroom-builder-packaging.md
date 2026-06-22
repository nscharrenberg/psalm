# Courtroom, Builder & Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire all components together via `DefaultCourtroom`, expose a fluent builder API (`PSALM` class), finalize the public `__init__.py` exports, set up GitHub Actions for PyPI publishing, and add an end-to-end integration test.

**Architecture:** `DefaultCourtroom` receives pre-built phase instances and runs them sequentially. The `PSALM` builder accumulates config via chained methods, validates and pings LLMs in `async .build()`, then constructs and returns a `DefaultCourtroom`. `.evaluate()` is a sync wrapper around `asyncio.run(self.aevaluate(...))`. Public API exports only `PSALM`, `AgentConfig`, `PSALMResult`, `PSALMError`, `PSALMConfigError`.

**Tech Stack:** Python 3.14+, uv, hatchling, GitHub Actions, pytest-asyncio

## Global Constraints

- `requires-python = ">=3.14"`
- `await .build()` pings every configured LLM with a test call before returning
- `.build()` raises `PSALMConfigError` if any validation or LLM ping fails
- Minimum jury size: 3 (validated in `.build()`)
- `.evaluate()` calls `asyncio.run()` internally — must not be called from within an async context
- `.aevaluate()` is the async equivalent — safe in any async context
- Identical texts: return `"Guilty"` immediately (no agents run), verdict set in `PSALMResult`
- Empty texts: raise `PSALMValidationError` immediately

---

### Task 1: CourtroomSetup Base and DefaultCourtroom

**Files:**
- Create: `psalm/courtroom/base.py`
- Create: `psalm/courtroom/default.py`

**Interfaces:**
- Consumes: `ArgumentationPhase`, `DeliberationPhase`, `PSALMResult`, `ResultMetadata`
- Produces:
  - `CourtroomSetup` — abstract with `async run(case_input) -> PSALMResult`
  - `DefaultCourtroom(argumentation_phase, deliberation_phase)` — wires both phases, measures timing, builds `PSALMResult`

- [ ] **Step 1: Implement `psalm/courtroom/base.py`**

```python
from abc import ABC, abstractmethod
from psalm.models.config import CaseInput
from psalm.models.result import PSALMResult


class CourtroomSetup(ABC):
    @abstractmethod
    async def run(self, case_input: CaseInput) -> PSALMResult: ...
```

- [ ] **Step 2: Implement `psalm/courtroom/default.py`**

```python
from __future__ import annotations
import time
from psalm.courtroom.base import CourtroomSetup
from psalm.models.config import CaseInput
from psalm.models.result import PSALMResult, ResultMetadata
from psalm.phases.argumentation import ArgumentationPhase
from psalm.phases.deliberation import DeliberationPhase


class DefaultCourtroom(CourtroomSetup):
    def __init__(
        self,
        argumentation_phase: ArgumentationPhase,
        deliberation_phase: DeliberationPhase,
    ) -> None:
        self._argumentation_phase = argumentation_phase
        self._deliberation_phase = deliberation_phase

    async def run(self, case_input: CaseInput) -> PSALMResult:
        start = time.monotonic()

        arg_log = await self._argumentation_phase.run(case_input)
        verdict, debate_log = await self._deliberation_phase.run(arg_log)

        duration = time.monotonic() - start
        metadata = ResultMetadata(
            duration_seconds=round(duration, 3),
            argumentation_rounds_used=len(arg_log.rounds),
            deliberation_rounds_used=len(debate_log.rounds),
            voting_strategy_applied=debate_log.final_voting_strategy_applied,
        )
        rationale = self._synthesize_rationale(verdict, arg_log, debate_log)
        return PSALMResult(
            verdict=verdict,
            rationale=rationale,
            argumentation_log=arg_log,
            debate_log=debate_log,
            metadata=metadata,
        )

    def _synthesize_rationale(self, verdict, arg_log, debate_log) -> str:
        arg_count = sum(len(r.arguments) for r in arg_log.rounds)
        counter_count = sum(len(r.counter_arguments) for r in arg_log.rounds)
        delib_rounds = len(debate_log.rounds)
        return (
            f"Verdict: {verdict}. "
            f"Based on {arg_count} prosecution argument(s) and {counter_count} defense counter-argument(s) "
            f"across {len(arg_log.rounds)} argumentation round(s), followed by {delib_rounds} deliberation round(s). "
            f"Final voting strategy applied: {debate_log.final_voting_strategy_applied}."
        )
```

- [ ] **Step 3: Run existing tests**

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add psalm/courtroom/base.py psalm/courtroom/default.py
git commit -m "feat: add CourtroomSetup base and DefaultCourtroom"
```

---

### Task 2: PSALM Builder

**Files:**
- Create: `psalm/builder.py`
- Create: `tests/unit/test_builder.py`

**Interfaces:**
- Produces:
  - `PSALM` — fluent builder class
  - `PSALM.with_prosecutor(base_url, api_key, org_id, model, **llm_kwargs) -> PSALM`
  - `PSALM.with_defense(...)` — same signature
  - `PSALM.with_judge(...)` — same signature
  - `PSALM.with_jury(configs: list[dict | AgentConfig]) -> PSALM`
  - `PSALM.with_dimensions(dimensions: list[str]) -> PSALM`
  - `PSALM.with_debate(rounds, time_limit_seconds) -> PSALM`
  - `PSALM.with_voting(strategies: list[str]) -> PSALM`
  - `await PSALM.build() -> DefaultCourtroom` — validates config + pings LLMs
  - `DefaultCourtroom.evaluate(source_text, target_text) -> PSALMResult`
  - `await DefaultCourtroom.aevaluate(source_text, target_text) -> PSALMResult`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_builder.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from psalm.builder import PSALM
from psalm.exceptions import PSALMConfigError, PSALMValidationError
from psalm.models.config import AgentConfig


def _agent_kwargs():
    return {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o"}


def _jury_configs(n=3):
    return [{"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o", "seed": i} for i in range(n)]


async def _build_psalm(ping_ok=True):
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_dimensions(["character"])
        .with_debate(rounds=2, time_limit_seconds=60)
        .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        return await builder.build()


async def test_build_returns_courtroom():
    courtroom = await _build_psalm()
    assert courtroom is not None


async def test_build_raises_without_prosecutor():
    builder = PSALM().with_defense(**_agent_kwargs()).with_judge(**_agent_kwargs()).with_jury(_jury_configs())
    with pytest.raises(PSALMConfigError) as exc_info:
        with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
            await builder.build()
    assert "PSALM-C001" in str(exc_info.value)


async def test_build_raises_with_small_jury():
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs(n=2))
    )
    with pytest.raises(PSALMConfigError) as exc_info:
        with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
            await builder.build()
    assert "PSALM-C002" in str(exc_info.value)


async def test_build_raises_on_llm_ping_failure():
    builder = (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
    )
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(side_effect=Exception("connection refused"))):
        with pytest.raises(PSALMConfigError) as exc_info:
            await builder.build()
    assert "PSALM-C006" in str(exc_info.value)


async def test_evaluate_raises_on_empty_source():
    courtroom = await _build_psalm()
    with patch.object(courtroom, "run", new=AsyncMock()):
        with pytest.raises(PSALMValidationError) as exc_info:
            courtroom.evaluate(source_text="", target_text="some text")
    assert "PSALM-V001" in str(exc_info.value)


async def test_evaluate_raises_on_empty_target():
    courtroom = await _build_psalm()
    with pytest.raises(PSALMValidationError) as exc_info:
        courtroom.evaluate(source_text="some text", target_text="")
    assert "PSALM-V002" in str(exc_info.value)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/test_builder.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/builder.py`**

```python
from __future__ import annotations
import asyncio
from typing import Any
from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.juror import Juror
from psalm.agents.prosecutor import Prosecutor
from psalm.courtroom.default import DefaultCourtroom
from psalm.exceptions import PSALMConfigError, PSALMValidationError
from psalm.models.config import AgentConfig, CaseInput, DebateConfig
from psalm.models.result import PSALMResult
from psalm.phases.argumentation import ArgumentationPhase
from psalm.phases.deliberation import DeliberationPhase
from psalm.voting.judge_tiebreaker import JudgeTiebreakerVoting
from psalm.voting.simple_majority import SimpleMajorityVoting
from psalm.voting.trust_weighted import TrustWeightedVoting

_STRATEGY_MAP = {
    "simple_majority": SimpleMajorityVoting,
    "trust_weighted": TrustWeightedVoting,
    "judge_tiebreaker": JudgeTiebreakerVoting,
}


class PSALM:
    def __init__(self) -> None:
        self._prosecutor_config: AgentConfig | None = None
        self._defense_config: AgentConfig | None = None
        self._judge_config: AgentConfig | None = None
        self._jury_configs: list[AgentConfig] = []
        self._debate_config = DebateConfig()

    def with_prosecutor(self, base_url: str, api_key: str, model: str, **kwargs: Any) -> PSALM:
        self._prosecutor_config = AgentConfig(base_url=base_url, api_key=api_key, model=model, **kwargs)
        return self

    def with_defense(self, base_url: str, api_key: str, model: str, **kwargs: Any) -> PSALM:
        self._defense_config = AgentConfig(base_url=base_url, api_key=api_key, model=model, **kwargs)
        return self

    def with_judge(self, base_url: str, api_key: str, model: str, **kwargs: Any) -> PSALM:
        self._judge_config = AgentConfig(base_url=base_url, api_key=api_key, model=model, **kwargs)
        return self

    def with_jury(self, configs: list[dict[str, Any] | AgentConfig]) -> PSALM:
        self._jury_configs = [
            c if isinstance(c, AgentConfig) else AgentConfig(**c)
            for c in configs
        ]
        return self

    def with_dimensions(self, dimensions: list[str]) -> PSALM:
        self._debate_config = self._debate_config.model_copy(update={"dimensions": dimensions})
        return self

    def with_debate(self, rounds: int = 5, time_limit_seconds: int = 180) -> PSALM:
        self._debate_config = self._debate_config.model_copy(
            update={"rounds": rounds, "time_limit_seconds": time_limit_seconds}
        )
        return self

    def with_voting(self, strategies: list[str]) -> PSALM:
        self._debate_config = self._debate_config.model_copy(update={"voting_strategies": strategies})
        return self

    async def build(self) -> _BuiltPSALM:
        self._validate_config()
        await self._ping_all_llms()
        return self._assemble()

    def _validate_config(self) -> None:
        if self._prosecutor_config is None:
            raise PSALMConfigError(
                code="PSALM-C001",
                message="Missing required agent: prosecutor.",
                context={"missing": "prosecutor"},
                suggestion="Call .with_prosecutor(base_url=..., api_key=..., model=...) on the builder.",
            )
        if self._defense_config is None:
            raise PSALMConfigError(
                code="PSALM-C001",
                message="Missing required agent: defense.",
                context={"missing": "defense"},
                suggestion="Call .with_defense(base_url=..., api_key=..., model=...) on the builder.",
            )
        if self._judge_config is None:
            raise PSALMConfigError(
                code="PSALM-C001",
                message="Missing required agent: judge.",
                context={"missing": "judge"},
                suggestion="Call .with_judge(base_url=..., api_key=..., model=...) on the builder.",
            )
        if len(self._jury_configs) < 3:
            raise PSALMConfigError(
                code="PSALM-C002",
                message=f"Jury requires a minimum of 3 members, got {len(self._jury_configs)}.",
                context={"jury_size": len(self._jury_configs), "minimum_required": 3},
                suggestion="Add at least one more AgentConfig to .with_jury([...]).",
            )

    async def _ping_llm(self, config: AgentConfig, role: str) -> None:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            organization=config.org_id,
            model=config.model,
            max_tokens=1,
        )
        try:
            await llm.ainvoke([{"role": "user", "content": "ping"}])
        except Exception as exc:
            raise PSALMConfigError(
                code="PSALM-C006",
                message=f"LLM connection failed for agent '{role}'.",
                context={"role": role, "base_url": config.base_url, "model": config.model},
                suggestion="Check api_key, base_url, and network connectivity.",
                cause=exc,
            ) from exc

    async def _ping_all_llms(self) -> None:
        configs = [
            (self._prosecutor_config, "prosecutor"),
            (self._defense_config, "defense"),
            (self._judge_config, "judge"),
        ] + [(c, f"juror-{i}") for i, c in enumerate(self._jury_configs)]
        await asyncio.gather(*[self._ping_llm(cfg, role) for cfg, role in configs])

    def _assemble(self) -> _BuiltPSALM:
        prosecutor = Prosecutor(config=self._prosecutor_config)
        defense = Defense(config=self._defense_config)
        judge = Judge(config=self._judge_config)
        jury = [Juror(juror_id=f"juror-{i}", config=c) for i, c in enumerate(self._jury_configs)]
        voting_strategies = [
            _STRATEGY_MAP[name]() for name in self._debate_config.voting_strategies
        ]
        arg_phase = ArgumentationPhase(prosecutor, defense, judge, self._debate_config)
        delib_phase = DeliberationPhase(jury, voting_strategies, judge, self._debate_config)
        courtroom = DefaultCourtroom(arg_phase, delib_phase)
        return _BuiltPSALM(courtroom=courtroom, debate_config=self._debate_config)


class _BuiltPSALM:
    def __init__(self, courtroom: DefaultCourtroom, debate_config: DebateConfig) -> None:
        self._courtroom = courtroom
        self._debate_config = debate_config

    def evaluate(self, source_text: str, target_text: str) -> PSALMResult:
        self._validate_inputs(source_text, target_text)
        if source_text.strip() == target_text.strip():
            return self._identical_texts_result(source_text)
        return asyncio.run(self.aevaluate(source_text, target_text))

    async def aevaluate(self, source_text: str, target_text: str) -> PSALMResult:
        self._validate_inputs(source_text, target_text)
        if source_text.strip() == target_text.strip():
            return self._identical_texts_result(source_text)
        case_input = CaseInput(
            source_text=source_text,
            target_text=target_text,
            dimensions=self._debate_config.dimensions,
        )
        return await self._courtroom.run(case_input)

    def _validate_inputs(self, source_text: str, target_text: str) -> None:
        if not source_text or not source_text.strip():
            raise PSALMValidationError(
                code="PSALM-V001",
                message="Source text cannot be empty.",
                context={"source_text_length": len(source_text)},
                suggestion="Provide a non-empty source text to .evaluate().",
            )
        if not target_text or not target_text.strip():
            raise PSALMValidationError(
                code="PSALM-V002",
                message="Target text cannot be empty.",
                context={"target_text_length": len(target_text)},
                suggestion="Provide a non-empty target text to .evaluate().",
            )

    def _identical_texts_result(self, text: str) -> PSALMResult:
        from psalm.models.result import ArgumentationLog, DebateLog, ResultMetadata
        return PSALMResult(
            verdict="Guilty",
            rationale="Source and target texts are identical — infringement confirmed without agent evaluation.",
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="none"),
            metadata=ResultMetadata(
                duration_seconds=0.0,
                argumentation_rounds_used=0,
                deliberation_rounds_used=0,
                voting_strategy_applied="none",
            ),
        )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_builder.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/builder.py tests/unit/test_builder.py
git commit -m "feat: add PSALM builder and _BuiltPSALM with sync/async evaluate"
```

---

### Task 3: Public API and Exports

**Files:**
- Modify: `psalm/__init__.py`
- Create: `tests/unit/test_public_api.py`

**Interfaces:**
- Produces: `from psalm import PSALM, AgentConfig, PSALMResult, PSALMError, PSALMConfigError` works

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_public_api.py
def test_public_imports():
    from psalm import PSALM, AgentConfig, PSALMConfigError, PSALMError, PSALMResult

    assert PSALM is not None
    assert AgentConfig is not None
    assert PSALMResult is not None
    assert PSALMError is not None
    assert PSALMConfigError is not None


def test_internal_modules_not_exported():
    import psalm
    assert not hasattr(psalm, "ArgumentationPhase")
    assert not hasattr(psalm, "DeliberationPhase")
    assert not hasattr(psalm, "SimpleMajorityVoting")
    assert not hasattr(psalm, "Prosecutor")
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/test_public_api.py -v
```

Expected: `ImportError` (empty `__init__.py`).

- [ ] **Step 3: Update `psalm/__init__.py`**

```python
from psalm.builder import PSALM
from psalm.exceptions import PSALMConfigError, PSALMError
from psalm.models.config import AgentConfig
from psalm.models.result import PSALMResult

__all__ = ["PSALM", "AgentConfig", "PSALMResult", "PSALMError", "PSALMConfigError"]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_public_api.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/__init__.py tests/unit/test_public_api.py
git commit -m "feat: expose public API via psalm/__init__.py"
```

---

### Task 4: End-to-End Integration Test

**Files:**
- Create: `tests/e2e/test_full_evaluation.py`
- Create: `tests/e2e/fixtures/cases.json`

**Interfaces:**
- Produces: full pipeline smoke test with mock LLMs; real LLM test gated behind `PSALM_E2E=true`

- [ ] **Step 1: Create synthetic test case fixture**

```json
[
  {
    "id": "clear_infringement",
    "source": "Elara had silver hair that shimmered like moonlight and eyes the colour of a summer sky. She carried a staff carved from the ancient oak of the Forbidden Grove.",
    "target": "Alara possessed shimmering silver locks and sky-blue eyes. In her hand she bore a staff hewn from the oak of the Ancient Grove.",
    "expected_verdict": "Guilty"
  },
  {
    "id": "clear_non_infringement",
    "source": "The dragon spread its wings over the mountain valley, its scales gleaming in the dawn light.",
    "target": "Maria walked through the city park, her umbrella shielding her from the afternoon rain.",
    "expected_verdict": "Not Guilty"
  },
  {
    "id": "borderline",
    "source": "A young orphan discovers they have magical powers and is sent to a school where they learn to control them.",
    "target": "A parentless teenager finds they can move objects with their mind and joins an academy for gifted students.",
    "expected_verdict": "Undecided"
  }
]
```

- [ ] **Step 2: Write the e2e test**

```python
# tests/e2e/test_full_evaluation.py
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from psalm import PSALM, PSALMResult
from psalm.models.result import JurorVote, ValidationResult


CASES_PATH = Path(__file__).parent / "fixtures" / "cases.json"


@pytest.fixture
def cases():
    return json.loads(CASES_PATH.read_text())


def _agent_kwargs():
    return {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o"}


def _jury_configs():
    return [{"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o", "seed": i} for i in range(3)]


@pytest.mark.skipif(os.getenv("PSALM_E2E") != "true", reason="Set PSALM_E2E=true to run real LLM tests")
async def test_e2e_real_llm(cases):
    psalm = await (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_dimensions(["character", "world-building", "plot"])
        .with_debate(rounds=2, time_limit_seconds=120)
        .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
        .build()
    )
    for case in cases:
        result = await psalm.aevaluate(source_text=case["source"], target_text=case["target"])
        assert isinstance(result, PSALMResult)
        assert result.verdict in {"Guilty", "Not Guilty", "Undecided"}


async def test_e2e_mock_full_pipeline(cases):
    from psalm.models.evidence import Argument, Proof

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

    with (
        patch("psalm.agents.prosecutor.Prosecutor.gather_arguments", new=AsyncMock(return_value=[sample_arg])),
        patch("psalm.agents.defense.Defense.gather_counter_arguments", new=AsyncMock(return_value=[sample_counter])),
        patch("psalm.agents.judge.Judge.validate_argument", new=AsyncMock(return_value=ValidationResult(is_valid=True))),
        patch("psalm.agents.judge.Judge.should_cross_examine", new=AsyncMock(return_value=False)),
        patch("psalm.agents.judge.Judge.detect_stability", new=AsyncMock(return_value=False)),
        patch("psalm.agents.juror.Juror.discuss", new=AsyncMock(return_value="I believe this infringes.")),
        patch("psalm.agents.juror.Juror.vote", new=AsyncMock(return_value=JurorVote(juror_id="juror-0", vote="Guilty", rationale="Strong evidence."))),
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
    ):
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .with_dimensions(["character"])
            .with_debate(rounds=1, time_limit_seconds=60)
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
    assert len(result.argumentation_log.rounds) > 0
    assert len(result.debate_log.rounds) > 0
    assert result.metadata.duration_seconds >= 0


async def test_identical_texts_returns_guilty_immediately():
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .build()
        )
    text = "The wizard had blue eyes."
    result = await psalm.aevaluate(source_text=text, target_text=text)
    assert result.verdict == "Guilty"
    assert result.metadata.argumentation_rounds_used == 0
```

- [ ] **Step 3: Run e2e mock test**

```bash
uv run pytest tests/e2e/test_full_evaluation.py -v -k "mock"
```

Expected: `test_e2e_mock_full_pipeline` and `test_identical_texts_returns_guilty_immediately` PASS. Real LLM test skipped.

- [ ] **Step 4: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/ 
git commit -m "test: add end-to-end integration tests with mock and real LLM paths"
```

---

### Task 5: GitHub Actions CI/CD and PyPI Packaging

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/publish.yml`
- Modify: `pyproject.toml` (add classifiers and metadata)

**Interfaces:**
- Produces: CI runs on every PR; publishing to PyPI on `v*` tag push

- [ ] **Step 1: Update `pyproject.toml` with full metadata**

Open `pyproject.toml` and add after the `[project]` section:

```toml
[project]
name = "psalm-eu"
version = "2.0.0"
description = "Courtroom-inspired multi-agent system for EU copyright infringement evaluation"
requires-python = ">=3.14"
license = { text = "MIT" }
authors = [{ name = "Noah Scharrenberg" }]
keywords = ["copyright", "multi-agent", "llm", "legal", "eu"]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.14",
    "Intended Audience :: Science/Research",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]
dependencies = [
    "langgraph>=1.2.6",
    "langchain>=1.3.10",
    "langchain-openai>=0.3.0",
    "pydantic>=2.13.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.1.1",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.15.18",
    "ty>=0.0.51",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main, thesis, v2]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
      - name: Install dependencies
        run: uv sync --extra dev
      - name: Lint
        run: uv run ruff check psalm/ tests/
      - name: Type check
        run: uv run ty check psalm/
      - name: Test
        run: uv run pytest tests/ -v --ignore=tests/e2e
```

- [ ] **Step 3: Create `.github/workflows/publish.yml`**

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
      - name: Build
        run: uv build
      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 4: Run lint and tests locally**

```bash
uv run ruff check psalm/ tests/
uv run pytest tests/ -v --ignore=tests/e2e
```

Expected: no lint errors, all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .github/
git commit -m "chore: add GitHub Actions CI/CD and finalize pyproject.toml metadata"
```
