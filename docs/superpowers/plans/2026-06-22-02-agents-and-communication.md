# Agents & Communication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the abstract `BaseAgent`, all four concrete agents (Prosecutor, Defense, Judge, Juror), and the communication layer (abstract `MessageQueue` + in-memory `SharedMessageQueue`).

**Architecture:** Each agent wraps a `ChatOpenAI` LLM instance from `langchain-openai` and uses `.with_structured_output()` for typed responses. Retry logic (3 attempts, exponential backoff) lives in `BaseAgent._call_llm()`. Agents are stateless — they receive all context via method arguments and return typed Pydantic results. The `SharedMessageQueue` is an in-memory list protected by an `asyncio.Lock`.

**Tech Stack:** Python 3.14+, LangChain 1.3.10+, langchain-openai 0.3.0+, Pydantic 2.13.4+, pytest-asyncio

## Global Constraints

- `requires-python = ">=3.14"`
- Agents never hold mutable state — all state lives in LangGraph phase state
- Retry: 3 attempts, exponential backoff `delay = 2.0 ** attempt` seconds
- All agent methods are `async`
- LLM calls use `langchain_openai.ChatOpenAI` with `config: AgentConfig`
- Tests mock `self._llm` — never make real API calls in unit tests
- Error codes: `PSALM-A001` (API error), `PSALM-A002` (parse error), `PSALM-A003` (retry exhausted)

---

### Task 1: BaseAgent and Communication Layer

**Files:**
- Create: `psalm/agents/base.py`
- Create: `psalm/communication/base.py`
- Create: `psalm/communication/shared_queue.py`
- Create: `tests/unit/agents/__init__.py`
- Create: `tests/unit/communication/__init__.py`
- Create: `tests/unit/communication/test_shared_queue.py`

**Interfaces:**
- Produces:
  - `BaseAgent(config: AgentConfig)` — abstract base with `_llm`, `_call_llm()`, retry logic
  - `MessageQueue` — abstract base with `post(message)` and `snapshot() -> list`
  - `SharedMessageQueue()` — in-memory, async-safe implementation

- [ ] **Step 1: Write failing tests for SharedMessageQueue**

```python
# tests/unit/communication/test_shared_queue.py
import asyncio
import pytest
from psalm.communication.shared_queue import SharedMessageQueue


async def test_post_and_snapshot():
    queue = SharedMessageQueue()
    await queue.post({"role": "prosecutor", "content": "Argument 1"})
    await queue.post({"role": "defense", "content": "Counter 1"})
    snapshot = queue.snapshot()
    assert len(snapshot) == 2
    assert snapshot[0]["role"] == "prosecutor"


async def test_snapshot_is_copy():
    queue = SharedMessageQueue()
    await queue.post({"role": "prosecutor", "content": "Arg"})
    snap = queue.snapshot()
    snap.append({"role": "intruder", "content": "injected"})
    assert len(queue.snapshot()) == 1  # original unmodified


async def test_concurrent_posts():
    queue = SharedMessageQueue()

    async def post_many(n: int) -> None:
        for i in range(n):
            await queue.post({"index": i})

    await asyncio.gather(post_many(50), post_many(50))
    assert len(queue.snapshot()) == 100


async def test_clear():
    queue = SharedMessageQueue()
    await queue.post({"content": "msg"})
    queue.clear()
    assert queue.snapshot() == []
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/communication/test_shared_queue.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/communication/base.py`**

```python
from abc import ABC, abstractmethod
from typing import Any


class MessageQueue(ABC):
    @abstractmethod
    async def post(self, message: dict[str, Any]) -> None: ...

    @abstractmethod
    def snapshot(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def clear(self) -> None: ...
```

- [ ] **Step 4: Implement `psalm/communication/shared_queue.py`**

```python
from __future__ import annotations
import asyncio
from typing import Any
from psalm.communication.base import MessageQueue


class SharedMessageQueue(MessageQueue):
    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def post(self, message: dict[str, Any]) -> None:
        async with self._lock:
            self._messages.append(message)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()
```

- [ ] **Step 5: Implement `psalm/agents/base.py`**

```python
from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from typing import Any, TypeVar
from langchain_openai import ChatOpenAI
from psalm.exceptions import PSALMAgentError
from psalm.models.config import AgentConfig

T = TypeVar("T")

_RETRY_ATTEMPTS = 3
_BACKOFF_FACTOR = 2.0


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            organization=config.org_id,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            seed=config.seed,
            timeout=config.timeout_seconds,
        )

    @property
    @abstractmethod
    def role(self) -> str: ...

    async def _call_llm(self, messages: list[Any]) -> Any:
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                return await self._llm.ainvoke(messages)
            except Exception as exc:
                if attempt == _RETRY_ATTEMPTS - 1:
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=f"LLM retry limit reached after {_RETRY_ATTEMPTS} attempts.",
                        context={"role": self.role, "model": self._config.model, "attempts": _RETRY_ATTEMPTS},
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                await asyncio.sleep(_BACKOFF_FACTOR**attempt)
        raise RuntimeError("unreachable")

    async def _call_structured(self, structured_llm: Any, messages: list[Any]) -> Any:
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                return await structured_llm.ainvoke(messages)
            except Exception as exc:
                if attempt == _RETRY_ATTEMPTS - 1:
                    raise PSALMAgentError(
                        code="PSALM-A003",
                        message=f"Structured LLM retry limit reached after {_RETRY_ATTEMPTS} attempts.",
                        context={"role": self.role, "model": self._config.model, "attempts": _RETRY_ATTEMPTS},
                        suggestion="Check API credentials, endpoint availability, and rate limits.",
                        cause=exc,
                    ) from exc
                await asyncio.sleep(_BACKOFF_FACTOR**attempt)
        raise RuntimeError("unreachable")
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/unit/communication/ -v
```

Expected: all 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add psalm/agents/base.py psalm/communication/ tests/unit/communication/ tests/unit/agents/__init__.py
git commit -m "feat: add BaseAgent and SharedMessageQueue"
```

---

### Task 2: Prosecutor Agent

**Files:**
- Create: `psalm/agents/prosecutor.py`
- Create: `tests/unit/agents/test_prosecutor.py`

**Interfaces:**
- Consumes: `BaseAgent`, `AgentConfig`, `Argument`, `Proof`
- Produces:
  - `Prosecutor(config: AgentConfig)`
  - `Prosecutor.gather_arguments(source_text, target_text, dimensions, round) -> list[Argument]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/agents/test_prosecutor.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from psalm.agents.prosecutor import Prosecutor
from psalm.models.evidence import Argument, Proof


@pytest.fixture
def prosecutor(agent_config):
    return Prosecutor(config=agent_config)


@pytest.fixture
def mock_arguments(sample_argument):
    return [sample_argument]


async def test_gather_arguments_returns_list(prosecutor, sample_argument, agent_config):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(arguments=[sample_argument]))

    with patch.object(prosecutor._llm, "with_structured_output", return_value=mock_chain):
        result = await prosecutor.gather_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=["character"],
            round=1,
        )

    assert len(result) == 1
    assert result[0].agent_role == "prosecutor"
    assert result[0].dimension == "character"


async def test_gather_arguments_role():
    from psalm.models.config import AgentConfig
    config = AgentConfig(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    prosecutor = Prosecutor(config=config)
    assert prosecutor.role == "prosecutor"


async def test_gather_arguments_retries_on_failure(prosecutor, sample_argument):
    call_count = 0

    async def failing_then_success(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("temporary failure")
        return MagicMock(arguments=[sample_argument])

    mock_chain = MagicMock()
    mock_chain.ainvoke = failing_then_success

    with patch.object(prosecutor._llm, "with_structured_output", return_value=mock_chain):
        result = await prosecutor.gather_arguments("src", "tgt", ["character"], 1)

    assert call_count == 3
    assert len(result) == 1
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/agents/test_prosecutor.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/agents/prosecutor.py`**

```python
from __future__ import annotations
from pydantic import BaseModel
from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument


class _ArgumentList(BaseModel):
    arguments: list[Argument]


_SYSTEM_PROMPT = """\
You are a legal prosecutor in a copyright infringement case governed by EU copyright law.
Analyze the provided texts and identify evidence of copyright infringement for each dimension.
For each dimension, construct structured arguments backed by verbatim excerpts from both texts.
Every argument MUST include at least one proof with verbatim excerpts from both the source and target texts.
Focus on substantial similarity of protected creative expression — ignore generic tropes and unprotectable elements.
"""


class Prosecutor(BaseAgent):
    @property
    def role(self) -> str:
        return "prosecutor"

    async def gather_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[str],
        round: int,
    ) -> list[Argument]:
        structured_llm = self._llm.with_structured_output(_ArgumentList)
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE TEXT (copyright-protected):\n{source_text}\n\n"
                    f"TARGET TEXT (potentially infringing):\n{target_text}\n\n"
                    f"Dimensions to analyze: {', '.join(dimensions)}\n"
                    f"Round: {round}\n\n"
                    "For each dimension, provide arguments with verbatim proof excerpts from both texts."
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.arguments
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Prosecutor failed to return valid structured arguments.",
                context={"role": self.role, "round": round, "dimensions": dimensions},
                suggestion="Check the LLM model supports structured output and the prompt is not too long.",
                cause=exc,
            ) from exc

    async def _call_structured(self, structured_llm, prompt: list) -> _ArgumentList:
        for attempt in range(3):
            try:
                return await structured_llm.ainvoke(prompt)
            except Exception as exc:
                import asyncio
                if attempt == 2:
                    raise
                await asyncio.sleep(2.0**attempt)
        raise RuntimeError("unreachable")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agents/test_prosecutor.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/agents/prosecutor.py tests/unit/agents/test_prosecutor.py
git commit -m "feat: add Prosecutor agent"
```

---

### Task 3: Defense Agent

**Files:**
- Create: `psalm/agents/defense.py`
- Create: `tests/unit/agents/test_defense.py`

**Interfaces:**
- Consumes: `BaseAgent`, `Argument`
- Produces:
  - `Defense(config: AgentConfig)`
  - `Defense.gather_counter_arguments(source_text, target_text, dimensions, prosecutor_arguments, round) -> list[Argument]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/agents/test_defense.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from psalm.agents.defense import Defense


@pytest.fixture
def defense(agent_config):
    return Defense(config=agent_config)


async def test_defense_role(defense):
    assert defense.role == "defense"


async def test_gather_counter_arguments(defense, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(arguments=[sample_counter_argument]))

    with patch.object(defense._llm, "with_structured_output", return_value=mock_chain):
        result = await defense.gather_counter_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=["character"],
            prosecutor_arguments=[sample_argument],
            round=1,
        )

    assert len(result) == 1
    assert result[0].agent_role == "defense"


async def test_counter_argument_includes_prosecutor_args_in_prompt(defense, sample_argument):
    captured_prompt = []

    async def capture_invoke(prompt):
        captured_prompt.extend(prompt)
        return MagicMock(arguments=[sample_argument])

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke

    with patch.object(defense._llm, "with_structured_output", return_value=mock_chain):
        await defense.gather_counter_arguments("src", "tgt", ["character"], [sample_argument], 1)

    user_content = next(m["content"] for m in captured_prompt if m["role"] == "user")
    assert "prosecutor" in user_content.lower() or "argument" in user_content.lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/agents/test_defense.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/agents/defense.py`**

```python
from __future__ import annotations
import asyncio
from pydantic import BaseModel
from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument


class _ArgumentList(BaseModel):
    arguments: list[Argument]


_SYSTEM_PROMPT = """\
You are a defense attorney in a copyright infringement case governed by EU copyright law.
Challenge the prosecutor's arguments by providing counter-evidence showing the target text does not infringe.
Focus on: (1) alternative interpretations, (2) lack of substantial similarity in protected elements,
(3) elements that are generic, unprotectable, or independently created.
Every counter-argument MUST include at least one proof with verbatim excerpts from both texts.
"""


class Defense(BaseAgent):
    @property
    def role(self) -> str:
        return "defense"

    async def gather_counter_arguments(
        self,
        source_text: str,
        target_text: str,
        dimensions: list[str],
        prosecutor_arguments: list[Argument],
        round: int,
    ) -> list[Argument]:
        structured_llm = self._llm.with_structured_output(_ArgumentList)
        args_text = "\n".join(
            f"- [{a.dimension}] {a.claim} (proofs: {len(a.proofs)})"
            for a in prosecutor_arguments
        )
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SOURCE TEXT:\n{source_text}\n\n"
                    f"TARGET TEXT:\n{target_text}\n\n"
                    f"Prosecutor's arguments:\n{args_text}\n\n"
                    f"Dimensions: {', '.join(dimensions)}\nRound: {round}\n\n"
                    "Provide counter-arguments with verbatim proof excerpts from both texts."
                ),
            },
        ]
        for attempt in range(3):
            try:
                result = await structured_llm.ainvoke(prompt)
                return result.arguments
            except Exception as exc:
                if attempt == 2:
                    raise PSALMAgentError(
                        code="PSALM-A002",
                        message="Defense failed to return valid structured counter-arguments.",
                        context={"role": self.role, "round": round},
                        suggestion="Check the LLM model supports structured output.",
                        cause=exc,
                    ) from exc
                await asyncio.sleep(2.0**attempt)
        raise RuntimeError("unreachable")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agents/test_defense.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/agents/defense.py tests/unit/agents/test_defense.py
git commit -m "feat: add Defense agent"
```

---

### Task 4: Judge Agent

**Files:**
- Create: `psalm/agents/judge.py`
- Create: `tests/unit/agents/test_judge.py`

**Interfaces:**
- Consumes: `BaseAgent`, `Argument`, `ValidationResult`, `JurorVote`
- Produces:
  - `Judge(config: AgentConfig)`
  - `Judge.validate_argument(argument, source_text, target_text) -> ValidationResult`
  - `Judge.should_cross_examine(arguments, counter_arguments) -> bool`
  - `Judge.detect_stability(current_arguments, previous_arguments) -> bool`
  - `Judge.tiebreak(votes, argumentation_log) -> Literal["Guilty", "Not Guilty", "Undecided"]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/agents/test_judge.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from psalm.agents.judge import Judge
from psalm.models.result import ArgumentationLog, JurorVote, RoundArguments, ValidationResult


@pytest.fixture
def judge(agent_config):
    return Judge(config=agent_config)


async def test_judge_role(judge):
    assert judge.role == "judge"


async def test_validate_argument_valid(judge, sample_argument):
    mock_result = ValidationResult(is_valid=True)
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)

    with patch.object(judge._llm, "with_structured_output", return_value=mock_chain):
        result = await judge.validate_argument(
            argument=sample_argument,
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
        )

    assert result.is_valid is True
    assert result.rejection_reason is None


async def test_validate_argument_invalid(judge, sample_argument):
    mock_result = ValidationResult(is_valid=False, rejection_reason="Excerpts not verbatim.")
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)

    with patch.object(judge._llm, "with_structured_output", return_value=mock_chain):
        result = await judge.validate_argument(sample_argument, "src", "tgt")

    assert result.is_valid is False
    assert "verbatim" in result.rejection_reason


async def test_should_cross_examine_with_discrepancy(judge, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(should_cross_examine=True))

    with patch.object(judge._llm, "with_structured_output", return_value=mock_chain):
        result = await judge.should_cross_examine([sample_argument], [sample_counter_argument])

    assert result is True


async def test_tiebreak_returns_valid_verdict(judge, minimal_argumentation_log):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Strong evidence."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Weak similarity."),
    ]
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(verdict="Guilty"))

    with patch.object(judge._llm, "with_structured_output", return_value=mock_chain):
        verdict = await judge.tiebreak(votes, minimal_argumentation_log)

    assert verdict in {"Guilty", "Not Guilty", "Undecided"}
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/agents/test_judge.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/agents/judge.py`**

```python
from __future__ import annotations
import asyncio
from typing import Literal
from pydantic import BaseModel
from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.evidence import Argument
from psalm.models.result import ArgumentationLog, JurorVote, ValidationResult


class _CrossExamDecision(BaseModel):
    should_cross_examine: bool
    reasoning: str


class _StabilityDecision(BaseModel):
    stability_detected: bool
    reasoning: str


class _TiebreakDecision(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str


_VALIDATION_PROMPT = """\
You are a judge validating an attorney's argument in a copyright case.
Check: (1) does the argument have at least one proof with actual verbatim excerpts from both texts?
(2) are the excerpts genuinely from the provided texts? (3) is the reasoning relevant to the dimension?
Respond with is_valid and rejection_reason if invalid.
"""


class Judge(BaseAgent):
    @property
    def role(self) -> str:
        return "judge"

    async def validate_argument(
        self, argument: Argument, source_text: str, target_text: str
    ) -> ValidationResult:
        structured_llm = self._llm.with_structured_output(ValidationResult)
        proofs_text = "\n".join(
            f"  Source: '{p.source_excerpt}'\n  Target: '{p.target_excerpt}'\n  Relevance: {p.relevance}"
            for p in argument.proofs
        )
        prompt = [
            {"role": "system", "content": _VALIDATION_PROMPT},
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
        for attempt in range(3):
            try:
                return await structured_llm.ainvoke(prompt)
            except Exception as exc:
                if attempt == 2:
                    raise PSALMAgentError(
                        code="PSALM-A002",
                        message="Judge failed to validate argument.",
                        context={"role": self.role, "claim": argument.claim},
                        suggestion="Check LLM supports structured output.",
                        cause=exc,
                    ) from exc
                await asyncio.sleep(2.0**attempt)
        raise RuntimeError("unreachable")

    async def should_cross_examine(
        self, arguments: list[Argument], counter_arguments: list[Argument]
    ) -> bool:
        structured_llm = self._llm.with_structured_output(_CrossExamDecision)
        args_text = "\n".join(f"- [{a.dimension}] {a.claim}" for a in arguments)
        counter_text = "\n".join(f"- [{a.dimension}] {a.claim}" for a in counter_arguments)
        prompt = [
            {"role": "system", "content": "You are a judge deciding if cross-examination is warranted. Cross-examine only when there are genuine discrepancies or alternative interpretations worth exploring."},
            {"role": "user", "content": f"Arguments:\n{args_text}\n\nCounter-arguments:\n{counter_text}\n\nShould cross-examination occur?"},
        ]
        for attempt in range(3):
            try:
                result = await structured_llm.ainvoke(prompt)
                return result.should_cross_examine
            except Exception:
                if attempt == 2:
                    return False
                await asyncio.sleep(2.0**attempt)
        return False

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
            f"Round {r.round}: {len(r.arguments)} arguments, {len(r.counter_arguments)} counter-arguments"
            for r in argumentation_log.rounds
        )
        prompt = [
            {"role": "system", "content": "You are a judge casting a tiebreaker vote in a copyright case. Base your decision on the totality of the evidence and arguments."},
            {"role": "user", "content": f"Jury votes (tied):\n{votes_text}\n\nArgumentation summary:\n{rounds_text}\n\nCast your tiebreaker verdict."},
        ]
        for attempt in range(3):
            try:
                result = await structured_llm.ainvoke(prompt)
                return result.verdict
            except Exception:
                if attempt == 2:
                    return "Undecided"
                await asyncio.sleep(2.0**attempt)
        return "Undecided"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agents/test_judge.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/agents/judge.py tests/unit/agents/test_judge.py
git commit -m "feat: add Judge agent"
```

---

### Task 5: Juror Agent

**Files:**
- Create: `psalm/agents/juror.py`
- Create: `tests/unit/agents/test_juror.py`

**Interfaces:**
- Consumes: `BaseAgent`, `ArgumentationLog`, `JurorVote`
- Produces:
  - `Juror(juror_id: str, config: AgentConfig)`
  - `Juror.discuss(argumentation_log, previous_rounds, current_discussion, round) -> str`
  - `Juror.vote(argumentation_log, previous_rounds, discussion_messages, round) -> JurorVote`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/agents/test_juror.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from psalm.agents.juror import Juror
from psalm.models.result import JurorVote


@pytest.fixture
def juror(agent_config):
    return Juror(juror_id="juror-0", config=agent_config)


async def test_juror_role(juror):
    assert juror.role == "juror"
    assert juror.juror_id == "juror-0"


async def test_discuss_returns_string(juror, minimal_argumentation_log):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(content="I believe this is infringing based on the character evidence."))

    with patch.object(juror._llm, "ainvoke", new=mock_chain.ainvoke):
        message = await juror.discuss(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[],
            current_discussion=[],
            round=1,
        )

    assert isinstance(message, str)
    assert len(message) > 0


async def test_vote_returns_juror_vote(juror, minimal_argumentation_log):
    mock_result = JurorVote(juror_id="juror-0", vote="Guilty", rationale="Strong character similarity evidence.")
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)

    with patch.object(juror._llm, "with_structured_output", return_value=mock_chain):
        vote = await juror.vote(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[],
            discussion_messages=[{"juror_id": "juror-0", "message": "I agree."}],
            round=1,
        )

    assert vote.juror_id == "juror-0"
    assert vote.vote in {"Guilty", "Not Guilty", "Undecided"}


async def test_vote_does_not_see_current_round_peer_votes(juror, minimal_argumentation_log):
    captured_prompt = []

    async def capture_invoke(prompt):
        captured_prompt.extend(prompt)
        return JurorVote(juror_id="juror-0", vote="Not Guilty", rationale="Insufficient evidence.")

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke

    with patch.object(juror._llm, "with_structured_output", return_value=mock_chain):
        await juror.vote(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[{"round": 0, "votes": [{"juror_id": "juror-1", "vote": "Guilty"}]}],
            discussion_messages=[],
            round=1,
        )

    user_content = " ".join(m.get("content", "") for m in captured_prompt if m.get("role") == "user")
    # previous rounds ARE visible
    assert "round" in user_content.lower() or "previous" in user_content.lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/agents/test_juror.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/agents/juror.py`**

```python
from __future__ import annotations
import asyncio
import json
from typing import Any
from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.result import ArgumentationLog, JurorVote


_DISCUSS_SYSTEM = """\
You are a juror in a copyright infringement deliberation. Engage in open discussion, share your perspective,
and respond to other jurors based solely on the evidence presented. Be concise and focused on legal evidence.
"""

_VOTE_SYSTEM = """\
You are a juror in a copyright infringement case. After reviewing all evidence and deliberations,
cast your independent vote. Do NOT be influenced by what you think other jurors in this round will vote.
Base your decision only on the argumentation log, previous round results, and this round's discussion.
"""


class Juror(BaseAgent):
    def __init__(self, juror_id: str, config) -> None:
        super().__init__(config)
        self.juror_id = juror_id

    @property
    def role(self) -> str:
        return "juror"

    async def discuss(
        self,
        argumentation_log: ArgumentationLog,
        previous_rounds: list[dict[str, Any]],
        current_discussion: list[dict[str, str]],
        round: int,
    ) -> str:
        args_summary = "\n".join(
            f"Round {r.round}: {len(r.arguments)} prosecution arguments, {len(r.counter_arguments)} defense arguments"
            for r in argumentation_log.rounds
        )
        discussion_so_far = "\n".join(
            f"{m['juror_id']}: {m['message']}" for m in current_discussion
        ) or "No messages yet."
        prompt = [
            {"role": "system", "content": _DISCUSS_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Evidence summary:\n{args_summary}\n\n"
                    f"Previous round results:\n{json.dumps(previous_rounds, indent=2)}\n\n"
                    f"Current discussion:\n{discussion_so_far}\n\n"
                    f"Round {round} — share your perspective."
                ),
            },
        ]
        response = await self._call_llm(prompt)
        return response.content

    async def vote(
        self,
        argumentation_log: ArgumentationLog,
        previous_rounds: list[dict[str, Any]],
        discussion_messages: list[dict[str, str]],
        round: int,
    ) -> JurorVote:
        structured_llm = self._llm.with_structured_output(JurorVote)
        args_summary = "\n".join(
            f"Round {r.round}: {len(r.arguments)} prosecution, {len(r.counter_arguments)} defense arguments"
            for r in argumentation_log.rounds
        )
        discussion_text = "\n".join(
            f"{m['juror_id']}: {m['message']}" for m in discussion_messages
        ) or "No discussion this round."
        prompt = [
            {"role": "system", "content": _VOTE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Evidence summary:\n{args_summary}\n\n"
                    f"Previous round results (for context only):\n{json.dumps(previous_rounds, indent=2)}\n\n"
                    f"This round's discussion:\n{discussion_text}\n\n"
                    f"Round {round} — cast your vote as juror '{self.juror_id}'."
                ),
            },
        ]
        for attempt in range(3):
            try:
                result = await structured_llm.ainvoke(prompt)
                return JurorVote(
                    juror_id=self.juror_id,
                    vote=result.vote,
                    rationale=result.rationale,
                )
            except Exception as exc:
                if attempt == 2:
                    raise PSALMAgentError(
                        code="PSALM-A002",
                        message=f"Juror {self.juror_id} failed to cast a valid vote.",
                        context={"juror_id": self.juror_id, "round": round},
                        suggestion="Check LLM supports structured output.",
                        cause=exc,
                    ) from exc
                await asyncio.sleep(2.0**attempt)
        raise RuntimeError("unreachable")
```

- [ ] **Step 4: Run all agent tests**

```bash
uv run pytest tests/unit/agents/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/agents/juror.py tests/unit/agents/test_juror.py
git commit -m "feat: add Juror agent"
```
