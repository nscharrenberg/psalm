# PSALM 2.0 SDK Design Spec

**Date**: 2026-06-22
**Author**: Noah Scharrenberg
**Project**: psalm-eu v2.0.0

---

## 1. Overview

This document specifies the SDK design for PSALM 2.0 — a courtroom-inspired multi-agent system (MAS) for evaluating EU copyright infringement. The SDK wraps the MAS defined in `docs/design-document.md` into a clean, extensible Python library distributed on PyPI.

---

## 2. Package Structure

```
psalm/
├── __init__.py              # public exports only
├── builder.py               # PSALM builder class
├── exceptions.py            # PSALMError hierarchy
├── models/
│   ├── config.py            # AgentConfig, DebateConfig
│   ├── result.py            # PSALMResult, ArgumentationLog, DebateLog, ResultMetadata
│   └── state.py             # LangGraph state schemas (ArgumentationState, DeliberationState)
├── agents/
│   ├── base.py              # Abstract BaseAgent
│   ├── judge.py
│   ├── prosecutor.py
│   ├── defense.py
│   └── juror.py
├── phases/
│   ├── base.py              # Abstract BasePhase
│   ├── argumentation.py     # ArgumentationPhase (LangGraph subgraph)
│   └── deliberation.py      # DeliberationPhase (LangGraph subgraph)
├── voting/
│   ├── base.py              # Abstract VotingStrategy
│   ├── simple_majority.py
│   ├── trust_weighted.py
│   └── judge_tiebreaker.py
├── courtroom/
│   ├── base.py              # Abstract CourtroomSetup
│   └── default.py           # DefaultCourtroom (direct agent interaction)
└── communication/
    ├── base.py              # Abstract MessageQueue
    └── shared_queue.py      # In-memory SharedMessageQueue (default)
```

### Design principles applied

- **SRP**: `models/` holds schemas only (no logic), `agents/` holds agent behavior only (no orchestration), `voting/` holds voting logic only (no agent knowledge).
- **OCP**: New voting strategy → add a file in `voting/` implementing `VotingStrategy`. No existing code changes. Same for courtroom setups and communication protocols.
- **DIP**: `phases/` depends on `agents/base.py` and `communication/base.py` — never on concrete implementations.
- **Extensibility hooks**: `courtroom/` for alternative setups (e.g. Meta-LLM coordination); `communication/` for MCP/A2A protocols; `voting/` for ranked-choice, Borda count, etc.

---

## 3. Agent Architecture

### BaseAgent

```python
class BaseAgent(ABC):
    def __init__(self, config: AgentConfig): ...

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResponse: ...

    @property
    def role(self) -> str: ...  # "judge" | "prosecutor" | "defense" | "juror"
```

`AgentContext` is a typed Pydantic model containing: source text, target text, current phase, message queue snapshot, round number, and (for jurors) previous round aggregated results.

Agents are **stateless** — all mutable state lives in the LangGraph phase state, never on the agent instance.

### Concrete agents

| Agent | `run()` responsibility |
|---|---|
| `Prosecutor` | Gathers evidence per dimension, returns structured arguments |
| `Defense` | Reads prosecutor arguments, returns counter-arguments |
| `Judge` | Validates argument quality, triggers cross-examination when discrepancies exist |
| `Juror` | Reads full argumentation log + previous round results only, returns blind vote + rationale |

Cross-examination is triggered by the `Judge` — not by the attorneys. Judge controls all flow transitions.

---

## 4. Phase Architecture

Each phase is a LangGraph `StateGraph` compiled into a subgraph. Phases are wired together by `CourtroomSetup`.

### ArgumentationPhase

**State**: `ArgumentationState` — source/target texts, current round, message queue, accumulated arguments per dimension.

**Graph flow**:
```
prosecutor_gather → judge_validate → defense_gather → judge_validate
       ↑                                                      |
       └──────────── (cross-examination if triggered) ────────┘
       └──────────── (next round if limit not reached) ────────┘
                                                               ↓
                                                      finalize_arguments
```

**Termination**: round limit reached, or judge detects no new arguments (adaptive stability detection).

### DeliberationPhase

**State**: `DeliberationState` — full argumentation log, current round, per-round vote history, final verdict.

**Graph flow**:
```
distribute_context → jury_round → aggregate_votes → check_consensus
                          ↑                                 |
                          └──── (next round if no consensus)┘
                                                            ↓
                                                   apply_voting_strategy
                                                            ↓
                                                     finalize_verdict
```

**Jury round**: all jurors run in parallel via `asyncio.gather`. Each juror receives the full argumentation log and all *previous* round results — never the current round's peer votes. Blind voting per round, results shared between rounds.

**Voting strategy chain**: configured strategies applied in order — simple majority → trust-weighted → judge tiebreaker. First strategy to produce a non-tie result wins.

### CourtroomSetup

```python
class DefaultCourtroom(CourtroomSetup):
    async def run(self, case: CaseInput) -> PSALMResult:
        arg_result = await self.argumentation_phase.run(case)
        delib_result = await self.deliberation_phase.run(arg_result)
        return self._build_result(arg_result, delib_result)
```

---

## 5. Public API

### Builder pattern

```python
psalm = await (
    PSALM()
    .with_prosecutor(base_url="...", api_key="...", org_id="...", model="...")
    .with_defense(base_url="...", api_key="...", org_id="...", model="...")
    .with_judge(base_url="...", api_key="...", org_id="...", model="...")
    .with_jury([
        {"base_url": "...", "api_key": "...", "org_id": "...", "model": "..."},
        {"base_url": "...", "api_key": "...", "org_id": "...", "model": "..."},
        {"base_url": "...", "api_key": "...", "org_id": "...", "model": "..."},
    ])
    .with_dimensions(["character", "world-building", "plot"])
    .with_debate(rounds=5, time_limit_seconds=180)
    .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
    .build()  # async: validates config + pings all LLMs
)
```

### Evaluation

```python
# Sync
result = psalm.evaluate(source_text="...", target_text="...")

# Async
result = await psalm.aevaluate(source_text="...", target_text="...")
```

### PSALMResult

```python
class PSALMResult(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str
    argumentation_log: ArgumentationLog   # per-round arguments + counter-arguments
    debate_log: DebateLog                 # per-round jury votes + rationales
    metadata: ResultMetadata              # timing, rounds used, voting strategy applied

    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...
```

### Public exports (`__init__.py`)

```python
from psalm import PSALM, AgentConfig, PSALMResult, PSALMConfigError, PSALMError
```

Internal modules (`phases/`, `voting/`, `agents/`) are not exported.

---

## 6. Error Handling

### Config-time (raised by `await .build()`)

| Condition | Exception |
|---|---|
| Missing required agent | `PSALMConfigError` |
| Jury fewer than 3 members | `PSALMConfigError` |
| Unknown dimension | `PSALMConfigError` |
| Invalid voting strategy order | `PSALMConfigError` |
| LLM credential invalid or endpoint unreachable | `PSALMConfigError` |

LLM connections are pinged during `.build()` — fail fast before any evaluation starts.

### Runtime (during `.evaluate()` / `.aevaluate()`)

| Condition | Behavior |
|---|---|
| Empty source or target text | `ValueError` raised immediately |
| Identical texts | Returns `"Guilty"` immediately, no agents run |
| LLM timeout / retry failure | Retry 3x with exponential backoff (factor 2.0), then fallback |
| Single agent failure after retries | Phase continues, failure logged in `metadata` |
| All agents fail in a phase | Verdict falls back to `"Undecided"` + error rationale |
| Jury deadlock after all strategies | Judge tiebreaker is final; if judge also fails, `"Undecided"` |

Runtime evaluation always returns a `PSALMResult` — never raises mid-run. All agent failures are recorded in `result.metadata`.

### Exception hierarchy

```
PSALMError
├── PSALMConfigError        # bad configuration or credential failure
├── PSALMTimeoutError       # agent exceeded time limit after retries
└── PSALMEvaluationError    # unrecoverable evaluation failure
```

---

## 7. Testing Strategy

### Unit tests
- Agents tested in isolation: mock `AgentContext` passed directly to `agent.run()`
- LLMs mocked via LangChain's `FakeListChatModel`
- Each voting strategy tested independently with fixed vote inputs
- No LangGraph involved

### Integration tests
- Full phase execution (`ArgumentationPhase`, `DeliberationPhase`) with mock LLMs
- Verify graph flow, state transitions, round logic, timeout/retry behavior
- Jury parallel execution verified: all jurors receive same context, votes aggregated correctly
- Edge cases: identical texts, empty texts, single agent failure mid-phase

### End-to-end tests
- Synthetic test cases in JSON: `{"source": "...", "target": "...", "expected_verdict": "Guilty"}`
- Real LLM calls gated behind `PSALM_E2E=true` env flag
- Validates accuracy against ground truth and consistency across repeated runs

### Fixtures
- `conftest.py`: reusable `AgentConfig` fixtures, mock LLM factories, synthetic case loader
- No shared mutable state between tests

---

## 8. Packaging & Distribution

```toml
[project]
name = "psalm-eu"
version = "2.0.0"
requires-python = ">=3.14"
dependencies = [
    "langgraph>=1.2.6",
    "langchain>=1.3.10",
    "pydantic>=2.13.4",
]

[project.optional-dependencies]
dev = ["pytest>=9.1.1", "ruff>=0.15.18", "ty>=0.0.51"]
```

### Versioning (semantic)
- **patch** — bug fixes, no API changes
- **minor** — new features, backwards-compatible (new voting strategy, new dimension)
- **major** — breaking API changes

### Distribution
- Published to PyPI via GitHub Actions on tag push (`v*`)
- Source + wheel distributions
- `uv` for local development (`uv sync`, `uv run pytest`)
