# Voting Strategies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the abstract `VotingStrategy` base and three concrete strategies — simple majority, trust-weighted, and judge tiebreaker — each in its own file.

**Architecture:** Strategy pattern. Each strategy implements `VotingStrategy.apply(votes, judge) -> VoteResult`. `VoteResult` carries the verdict if a winner was found, or `None` if tied (signals the next strategy in the chain should run). The judge tiebreaker calls `Judge.tiebreak()` and always produces a final verdict.

**Tech Stack:** Python 3.14+, Pydantic 2.13.4+, pytest

## Global Constraints

- `requires-python = ">=3.14"`
- Each strategy is in its own file under `psalm/voting/`
- `VotingStrategy.apply()` is `async` (judge tiebreaker calls an LLM)
- `VoteResult(verdict, is_tie)` — `is_tie=True` means this strategy could not resolve and the chain should continue
- Minimum jury size is 3 (enforced in builder, not here)
- No business logic in `VotingStrategy` base — only interface

---

### Task 1: VotingStrategy Base and SimpleMajority

**Files:**
- Create: `psalm/voting/base.py`
- Create: `psalm/voting/simple_majority.py`
- Create: `tests/unit/voting/__init__.py`
- Create: `tests/unit/voting/test_simple_majority.py`

**Interfaces:**
- Produces:
  - `VoteResult(verdict, is_tie)` — output of any strategy
  - `VotingStrategy` — abstract base with `async apply(votes, judge) -> VoteResult`
  - `SimpleMajorityVoting` — returns winning verdict if one vote-count exceeds all others, else `is_tie=True`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/voting/test_simple_majority.py
import pytest
from psalm.models.result import JurorVote
from psalm.voting.simple_majority import SimpleMajorityVoting


@pytest.fixture
def strategy():
    return SimpleMajorityVoting()


async def test_unanimous_guilty(strategy):
    votes = [
        JurorVote(juror_id=f"j{i}", vote="Guilty", rationale="Clear infringement.")
        for i in range(3)
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Guilty"
    assert result.is_tie is False


async def test_majority_not_guilty(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Not Guilty", rationale="No infringement."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Independent creation."),
        JurorVote(juror_id="j2", vote="Guilty", rationale="Some similarity."),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Not Guilty"
    assert result.is_tie is False


async def test_exact_tie_returns_is_tie(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Infringing."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Not infringing."),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.is_tie is True
    assert result.verdict is None


async def test_three_way_split_returns_is_tie(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="r1"),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="r2"),
        JurorVote(juror_id="j2", vote="Undecided", rationale="r3"),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.is_tie is True


async def test_majority_undecided(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Undecided", rationale="Borderline."),
        JurorVote(juror_id="j1", vote="Undecided", rationale="Borderline."),
        JurorVote(juror_id="j2", vote="Guilty", rationale="Infringing."),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Undecided"
    assert result.is_tie is False
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/voting/test_simple_majority.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/voting/base.py`**

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from pydantic import BaseModel
from psalm.models.result import JurorVote

if TYPE_CHECKING:
    from psalm.agents.judge import Judge


class VoteResult(BaseModel):
    verdict: str | None = None
    is_tie: bool = False


class VotingStrategy(ABC):
    @abstractmethod
    async def apply(self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None) -> VoteResult: ...
```

- [ ] **Step 4: Implement `psalm/voting/simple_majority.py`**

```python
from __future__ import annotations
from collections import Counter
from typing import Any
from psalm.models.result import JurorVote
from psalm.voting.base import VoteResult, VotingStrategy


class SimpleMajorityVoting(VotingStrategy):
    async def apply(self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None) -> VoteResult:
        counts = Counter(v.vote for v in votes)
        if not counts:
            return VoteResult(is_tie=True)
        top_verdict, top_count = counts.most_common(1)[0]
        # Tie: another verdict has the same count
        is_tie = sum(1 for c in counts.values() if c == top_count) > 1
        if is_tie:
            return VoteResult(is_tie=True)
        return VoteResult(verdict=top_verdict, is_tie=False)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/voting/test_simple_majority.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add psalm/voting/base.py psalm/voting/simple_majority.py tests/unit/voting/
git commit -m "feat: add VotingStrategy base and SimpleMajorityVoting"
```

---

### Task 2: TrustWeightedVoting

**Files:**
- Create: `psalm/voting/trust_weighted.py`
- Create: `tests/unit/voting/test_trust_weighted.py`

**Interfaces:**
- Consumes: `VotingStrategy`, `VoteResult`, `JurorVote`
- Produces:
  - `TrustWeightedVoting` — weights votes by number of proofs in rationale (proxy for argument strength); returns highest-weighted verdict, ties remain `is_tie=True`

**Trust weight formula:** count the number of supported claims mentioned in the juror's rationale (word count as a simple proxy). Verdict with highest summed weight wins. If top two weights are equal, `is_tie=True`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/voting/test_trust_weighted.py
import pytest
from psalm.models.result import JurorVote
from psalm.voting.trust_weighted import TrustWeightedVoting


@pytest.fixture
def strategy():
    return TrustWeightedVoting()


async def test_longer_rationale_wins_tie(strategy):
    votes = [
        JurorVote(
            juror_id="j0",
            vote="Guilty",
            rationale="The characters share blue eyes, silver cloaks, and a mentor relationship — three distinct protected traits.",
        ),
        JurorVote(
            juror_id="j1",
            vote="Not Guilty",
            rationale="No infringement.",
        ),
        JurorVote(
            juror_id="j2",
            vote="Guilty",
            rationale="Character and plot similarities are substantial.",
        ),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Guilty"
    assert result.is_tie is False


async def test_equal_weights_returns_tie(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Shared traits exist."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Independent creation."),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.is_tie is True


async def test_unanimous_with_weights(strategy):
    votes = [
        JurorVote(juror_id=f"j{i}", vote="Undecided", rationale="Borderline case with mixed evidence.")
        for i in range(3)
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Undecided"
    assert result.is_tie is False
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/voting/test_trust_weighted.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/voting/trust_weighted.py`**

```python
from __future__ import annotations
from collections import defaultdict
from typing import Any
from psalm.models.result import JurorVote
from psalm.voting.base import VoteResult, VotingStrategy


def _weight(rationale: str) -> float:
    return float(len(rationale.split()))


class TrustWeightedVoting(VotingStrategy):
    async def apply(self, votes: list[JurorVote], judge: Any, argumentation_log: Any = None) -> VoteResult:
        weights: dict[str, float] = defaultdict(float)
        for v in votes:
            weights[v.vote] += _weight(v.rationale)

        if not weights:
            return VoteResult(is_tie=True)

        sorted_verdicts = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top_verdict, top_weight = sorted_verdicts[0]

        is_tie = len(sorted_verdicts) > 1 and sorted_verdicts[1][1] == top_weight
        if is_tie:
            return VoteResult(is_tie=True)
        return VoteResult(verdict=top_verdict, is_tie=False)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/voting/test_trust_weighted.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/voting/trust_weighted.py tests/unit/voting/test_trust_weighted.py
git commit -m "feat: add TrustWeightedVoting strategy"
```

---

### Task 3: JudgeTiebreakerVoting

**Files:**
- Create: `psalm/voting/judge_tiebreaker.py`
- Create: `tests/unit/voting/test_judge_tiebreaker.py`

**Interfaces:**
- Consumes: `VotingStrategy`, `VoteResult`, `JurorVote`, `Judge.tiebreak()`
- Produces:
  - `JudgeTiebreakerVoting` — calls `judge.tiebreak(votes, argumentation_log)`, always produces `is_tie=False`

Note: `JudgeTiebreakerVoting.apply()` requires `judge` to be a `Judge` instance (not `None`). Passing `None` raises `PSALMConfigError PSALM-C005`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/voting/test_judge_tiebreaker.py
from unittest.mock import AsyncMock
import pytest
from psalm.exceptions import PSALMConfigError
from psalm.models.result import JurorVote
from psalm.voting.judge_tiebreaker import JudgeTiebreakerVoting


@pytest.fixture
def strategy():
    return JudgeTiebreakerVoting()


@pytest.fixture
def mock_judge(minimal_argumentation_log):
    judge = AsyncMock()
    judge.tiebreak = AsyncMock(return_value="Guilty")
    return judge


async def test_tiebreaker_calls_judge(strategy, mock_judge, minimal_argumentation_log):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="r1"),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="r2"),
    ]
    result = await strategy.apply(votes, judge=mock_judge, argumentation_log=minimal_argumentation_log)
    assert result.verdict == "Guilty"
    assert result.is_tie is False
    mock_judge.tiebreak.assert_called_once()


async def test_tiebreaker_never_returns_tie(strategy, mock_judge, minimal_argumentation_log):
    votes = [JurorVote(juror_id="j0", vote="Undecided", rationale="r1")]
    mock_judge.tiebreak = AsyncMock(return_value="Undecided")
    result = await strategy.apply(votes, judge=mock_judge, argumentation_log=minimal_argumentation_log)
    assert result.is_tie is False


async def test_tiebreaker_raises_without_judge(strategy, minimal_argumentation_log):
    votes = [JurorVote(juror_id="j0", vote="Guilty", rationale="r1")]
    with pytest.raises(PSALMConfigError) as exc_info:
        await strategy.apply(votes, judge=None, argumentation_log=minimal_argumentation_log)
    assert "PSALM-C005" in str(exc_info.value)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/voting/test_judge_tiebreaker.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `psalm/voting/judge_tiebreaker.py`**

```python
from __future__ import annotations
from typing import Any
from psalm.exceptions import PSALMConfigError
from psalm.models.result import ArgumentationLog, JurorVote
from psalm.voting.base import VoteResult, VotingStrategy


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

- [ ] **Step 4: Run all voting tests**

```bash
uv run pytest tests/unit/voting/ -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/voting/judge_tiebreaker.py tests/unit/voting/test_judge_tiebreaker.py
git commit -m "feat: add JudgeTiebreakerVoting strategy"
```
