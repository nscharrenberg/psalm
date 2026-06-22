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
├── exceptions.py            # PSALMError hierarchy + error codes
├── models/
│   ├── config.py            # AgentConfig, DebateConfig
│   ├── evidence.py          # Proof, Argument (structured argumentation models)
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

`AgentContext` is a typed Pydantic model containing: source text, target text, current phase, message queue snapshot, round number, and (for jurors) previous round aggregated results and discussion messages.

`AgentResponse` is a typed Pydantic model containing: the agent's output (role-dependent — `Argument`, `Vote`, or moderation decision), rationale, and timestamp.

Agents are **stateless** — all mutable state lives in the LangGraph phase state, never on the agent instance.

### AgentConfig

Targets the **OpenAI-compatible API** — works with any compatible endpoint (OpenAI, Azure OpenAI, Ollama, LiteLLM, etc.). Future extension to LangChain `BaseChatModel` instances is planned but out of scope for v2.0.0.

```python
class AgentConfig(BaseModel):
    base_url: str
    api_key: str
    org_id: str | None = None
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None          # reproducibility
    timeout_seconds: int = 180       # per-round time limit
```

### Concrete agents

| Agent | `run()` responsibility |
|---|---|
| `Prosecutor` | Gathers evidence per dimension, returns structured `Argument` objects with proofs |
| `Defense` | Reads prosecutor arguments (with proofs), returns counter-`Argument` objects with proofs |
| `Judge` | Validates argument quality + proof relevance, triggers cross-examination when discrepancies exist |
| `Juror` | In discussion sub-phase: posts persuasion messages. In vote sub-phase: returns blind `Vote` + rationale |

Cross-examination is triggered by the `Judge` — not by the attorneys. Judge controls all flow transitions.

---

## 4. Evidence Model

Arguments must be backed by proofs. A proof is the atomic unit of evidence: a verbatim excerpt from the source text, a verbatim excerpt from the target text, and the reasoning connecting them to the argument.

```python
class Proof(BaseModel):
    source_excerpt: str      # verbatim sentence/paragraph from source text
    target_excerpt: str      # verbatim sentence/paragraph from target text
    relevance: str           # reasoning connecting the excerpts to the argument

class Argument(BaseModel):
    claim: str                        # the argument being made
    dimension: str                    # "character" | "world-building" | "plot"
    proofs: list[Proof]               # min 1 proof required; field_validator enforces this
    agent_role: str                   # "prosecutor" | "defense"
    round: int
```

The `Judge` validates that every `Argument` has at least one `Proof` before admitting it to the message queue. Arguments without proofs are rejected and the submitting agent is prompted to revise.

---

## 5. Phase Architecture

Each phase is a LangGraph `StateGraph` compiled into a subgraph. Phases are wired together by `CourtroomSetup`.

### ArgumentationPhase

**State**: `ArgumentationState` — source/target texts, current round, message queue, accumulated `Argument` objects per dimension.

**Graph flow**:
```
prosecutor_gather → judge_validate → defense_gather → judge_validate
       ↑                                                      |
       └──────────── (cross-examination if triggered) ────────┘
       └──────────── (next round if limit not reached) ────────┘
                                                               ↓
                                                      finalize_arguments
```

`judge_validate` checks: (1) argument has at least one proof, (2) excerpts are relevant to the claimed dimension, (3) no new evidence introduced after the initial gathering phase. Rejected arguments are returned to the submitting agent for revision (one revision attempt per argument).

**Termination**: round limit reached, or judge detects no new arguments (adaptive stability detection).

### DeliberationPhase

**State**: `DeliberationState` — full argumentation log, current round, per-round discussion messages, per-round vote history, final verdict.

Each deliberation round has two sub-phases:

1. **Discussion** (sequential, open): jurors post persuasion messages visible to all, grounded in the argumentation log. Jurors can respond to each other. No voting occurs here.
2. **Vote** (parallel, blind): all jurors vote simultaneously via `asyncio.gather`. Each juror receives the full argumentation log, all previous round results, and the current round's discussion messages — but never the current round's peer votes.

**Graph flow**:
```
distribute_context → jury_discussion → jury_vote → aggregate_votes → check_consensus
                           ↑                                               |
                           └──────────── (next round if no consensus) ────┘
                                                                           ↓
                                                                  apply_voting_strategy
                                                                           ↓
                                                                    finalize_verdict
```

**Voting strategy chain**: configured strategies applied in order — simple majority → trust-weighted → judge tiebreaker. First strategy to produce a non-tie result wins.

### CourtroomSetup

`CaseInput` is a typed Pydantic model containing: source text, target text, and configured dimensions.

```python
class DefaultCourtroom(CourtroomSetup):
    async def run(self, case: CaseInput) -> PSALMResult:
        arg_result = await self.argumentation_phase.run(case)
        delib_result = await self.deliberation_phase.run(arg_result)
        return self._build_result(arg_result, delib_result)
```

---

## 6. Public API

### Builder pattern

```python
psalm = await (
    PSALM()
    .with_prosecutor(base_url="...", api_key="...", org_id="...", model="...", temperature=0.7)
    .with_defense(base_url="...", api_key="...", org_id="...", model="...", temperature=0.7)
    .with_judge(base_url="...", api_key="...", org_id="...", model="...", temperature=0.0)
    .with_jury([
        {"base_url": "...", "api_key": "...", "org_id": "...", "model": "...", "seed": 42},
        {"base_url": "...", "api_key": "...", "org_id": "...", "model": "...", "seed": 43},
        {"base_url": "...", "api_key": "...", "org_id": "...", "model": "...", "seed": 44},
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
    argumentation_log: ArgumentationLog   # per-round Arguments (with Proofs) + counter-arguments
    debate_log: DebateLog                 # per-round discussion messages + jury votes + rationales
    metadata: ResultMetadata              # timing, rounds used, voting strategy applied

    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...
```

### Public exports (`__init__.py`)

```python
from psalm import PSALM, AgentConfig, PSALMResult, PSALMError, PSALMConfigError
```

Internal modules (`phases/`, `voting/`, `agents/`, `models/evidence.py`) are not exported.

---

## 7. Error Handling

### Error code system

Every `PSALMError` carries a structured error code, human-readable message, runtime context, and a suggested fix. Format: `PSALM-{category}{number}`.

| Category prefix | Meaning |
|---|---|
| `C` | Configuration errors (caught at `.build()`) |
| `V` | Validation errors (caught at evaluation start) |
| `R` | Runtime errors (caught during phase execution) |
| `A` | Agent errors (LLM-level failures) |

```python
class PSALMError(Exception):
    code: str                      # e.g. "PSALM-C001"
    message: str                   # human-readable description
    context: dict[str, Any]        # runtime details (agent role, round, config values, etc.)
    suggestion: str                # actionable fix
    cause: Exception | None        # original exception if wrapping
```

Example error output:
```
PSALMConfigError [PSALM-C002]: Jury requires a minimum of 3 members, got 2.
  Context: {"jury_size": 2, "minimum_required": 3}
  Suggestion: Add at least one more AgentConfig to .with_jury([...]).
```

### Error code catalogue

#### Configuration errors — raised by `await .build()`

| Code | Condition | Suggestion |
|---|---|---|
| `PSALM-C001` | Missing required agent (prosecutor, defense, or judge) | Call the missing `.with_*()` builder method |
| `PSALM-C002` | Jury fewer than 3 members | Add more `AgentConfig` entries to `.with_jury()` |
| `PSALM-C003` | Unknown dimension in `.with_dimensions()` | Use one of: `"character"`, `"world-building"`, `"plot"` |
| `PSALM-C004` | Invalid voting strategy name | Use one of: `"simple_majority"`, `"trust_weighted"`, `"judge_tiebreaker"` |
| `PSALM-C005` | `judge_tiebreaker` not last in voting chain | `judge_tiebreaker` must be the final fallback |
| `PSALM-C006` | LLM credential invalid or endpoint unreachable | Check `api_key`, `base_url`, and network access |
| `PSALM-C007` | `temperature` out of range `[0.0, 2.0]` | Set a value within the valid range |

#### Validation errors — raised immediately by `.evaluate()` / `.aevaluate()`

| Code | Condition | Behavior |
|---|---|---|
| `PSALM-V001` | Source text is empty | Raises immediately, no agents run |
| `PSALM-V002` | Target text is empty | Raises immediately, no agents run |
| `PSALM-V003` | Identical source and target texts | Returns `"Guilty"` immediately, no agents run |

#### Runtime errors — recorded in `result.metadata`, evaluation continues

| Code | Condition | Behavior |
|---|---|---|
| `PSALM-R001` | Agent exceeded time limit after retries | Phase continues without that agent's contribution |
| `PSALM-R002` | All agents failed in a phase | Verdict falls back to `"Undecided"` + error rationale |
| `PSALM-R003` | Argument rejected by judge (missing proof) | Agent prompted to revise; if revision also rejected, argument dropped |
| `PSALM-R004` | Jury deadlock after all voting strategies exhausted | `"Undecided"` verdict returned |

#### Agent errors — wrapped and re-raised as `PSALMAgentError`

| Code | Condition |
|---|---|
| `PSALM-A001` | LLM API returned non-2xx response |
| `PSALM-A002` | LLM response failed to parse into expected schema |
| `PSALM-A003` | LLM retry limit reached (3 attempts, exponential backoff factor 2.0) |

### Exception hierarchy

```
PSALMError
├── PSALMConfigError        # PSALM-C* codes — bad configuration or credential failure
├── PSALMValidationError    # PSALM-V* codes — invalid input at evaluation time
├── PSALMRuntimeError       # PSALM-R* codes — recoverable phase-level failures
└── PSALMAgentError         # PSALM-A* codes — LLM-level failures
```

Runtime evaluation always returns a `PSALMResult` — `PSALMRuntimeError` and `PSALMAgentError` are caught internally and recorded in `result.metadata`. `PSALMConfigError` and `PSALMValidationError` are raised to the caller.

---

## 8. Testing Strategy

### Unit tests
- Agents tested in isolation: mock `AgentContext` passed directly to `agent.run()`
- LLMs mocked via LangChain's `FakeListChatModel`
- `Proof` and `Argument` validation tested: argument with zero proofs must fail validation
- Each voting strategy tested independently with fixed vote inputs
- Error code accuracy tested: each error condition produces the correct `PSALM-*` code
- No LangGraph involved

### Integration tests
- Full phase execution (`ArgumentationPhase`, `DeliberationPhase`) with mock LLMs
- Verify graph flow, state transitions, round logic, timeout/retry behavior
- Jury blind voting verified: no juror sees peer votes within same round
- Jury discussion → vote sequence verified: discussion messages present in `DebateLog`
- Proof validation gate verified: invalid arguments rejected before entering message queue
- Edge cases: identical texts, empty texts, single agent failure mid-phase

### End-to-end tests
- Synthetic test cases in JSON: `{"source": "...", "target": "...", "expected_verdict": "Guilty"}`
- Real LLM calls gated behind `PSALM_E2E=true` env flag
- Validates accuracy against ground truth and consistency across repeated runs

### Fixtures
- `conftest.py`: reusable `AgentConfig` fixtures, mock LLM factories, synthetic case loader, sample `Proof`/`Argument` factories
- No shared mutable state between tests

---

## 9. Packaging & Distribution

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
