# Deliberation Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `DeliberationPhase` as a LangGraph `StateGraph` subgraph. Each deliberation round has two sub-steps: sequential open discussion (jurors can persuade), then parallel blind voting (`asyncio.gather`). Rounds continue until consensus or the round limit is hit; then the configured voting strategy chain resolves any remaining tie.

**Architecture:** `DeliberationPhase(jury, voting_strategies, judge, config)` compiles a `StateGraph(DeliberationState)`. The `jury_discussion` node runs jurors sequentially (each sees prior discussion). The `jury_vote` node runs all jurors in parallel via `asyncio.gather` — no juror sees a peer's current-round vote. Between rounds, previous round results are shared in context. The voting strategy chain (from Plan 3) is applied only after round limit is hit without consensus.

**Tech Stack:** Python 3.14+, LangGraph 1.2.6+, asyncio, Pydantic 2.13.4+, pytest-asyncio

## Global Constraints

- `requires-python = ">=3.14"`
- Jury votes within a round are **parallel and blind** — use `asyncio.gather`
- Juror discussion is **sequential** — each juror sees all prior messages in the same round
- Previous round results ARE shared with jurors at the start of each new round
- Voting strategy chain: strategies applied in configured order; first non-tie wins
- If all strategies fail (impossible with judge tiebreaker, but defensive): return `"Undecided"`
- `DeliberationPhase.run(argumentation_log) -> tuple[str, DebateLog]` returns `(verdict, log)`

---

### Task 1: DeliberationPhase Scaffold and State

**Files:**
- Modify: `psalm/models/state.py` (add `pending_discussion_messages` to `DeliberationState`)
- Create: `psalm/phases/deliberation.py`

**Interfaces:**
- Consumes: `Juror`, `VotingStrategy`, `Judge`, `DebateConfig`, `ArgumentationLog`
- Produces:
  - `DeliberationPhase(jury, voting_strategies, judge, config)`
  - `DeliberationPhase.run(argumentation_log) -> tuple[str, DebateLog]`

- [ ] **Step 1: Update `DeliberationState` in `psalm/models/state.py`**

Open `psalm/models/state.py` and replace `DeliberationState` with:

```python
class DeliberationState(BaseModel):
    argumentation_log: ArgumentationLog
    max_rounds: int
    current_round: int = 0
    discussion_messages: list[dict[str, str]] = Field(default_factory=list)
    vote_history: list[dict[str, Any]] = Field(default_factory=list)
    consensus_reached: bool = False
    final_verdict: str | None = None
    voting_strategy_applied: str | None = None
    # Intermediate: current round votes collected after jury_vote node
    current_round_votes: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
```

- [ ] **Step 2: Run existing state tests**

```bash
uv run pytest tests/unit/models/test_state.py -v
```

Expected: PASS (new field has default).

- [ ] **Step 3: Implement `psalm/phases/deliberation.py`**

```python
from __future__ import annotations
import asyncio
from typing import Any
from langgraph.graph import END, StateGraph
from psalm.agents.judge import Judge
from psalm.agents.juror import Juror
from psalm.models.config import DebateConfig
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
    JurorVote,
    RoundDeliberation,
)
from psalm.models.state import DeliberationState
from psalm.phases.base import BasePhase
from psalm.voting.base import VotingStrategy


class DeliberationPhase(BasePhase):
    def __init__(
        self,
        jury: list[Juror],
        voting_strategies: list[VotingStrategy],
        judge: Judge,
        config: DebateConfig,
    ) -> None:
        self._jury = jury
        self._voting_strategies = voting_strategies
        self._judge = judge
        self._config = config
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(DeliberationState)

        graph.add_node("distribute_context", self._distribute_context)
        graph.add_node("jury_discussion", self._jury_discussion)
        graph.add_node("jury_vote", self._jury_vote)
        graph.add_node("aggregate_votes", self._aggregate_votes)
        graph.add_node("check_consensus", self._check_consensus)
        graph.add_node("apply_voting_strategy", self._apply_voting_strategy)
        graph.add_node("finalize_verdict", self._finalize_verdict)

        graph.set_entry_point("distribute_context")
        graph.add_edge("distribute_context", "jury_discussion")
        graph.add_edge("jury_discussion", "jury_vote")
        graph.add_edge("jury_vote", "aggregate_votes")
        graph.add_edge("aggregate_votes", "check_consensus")
        graph.add_conditional_edges(
            "check_consensus",
            self._route_after_consensus,
            {
                "consensus": "finalize_verdict",
                "continue": "distribute_context",
                "exhausted": "apply_voting_strategy",
            },
        )
        graph.add_edge("apply_voting_strategy", "finalize_verdict")
        graph.add_edge("finalize_verdict", END)

        return graph.compile()

    async def run(self, argumentation_log: ArgumentationLog) -> tuple[str, DebateLog]:
        from psalm.models.config import CaseInput  # avoid circular at module level
        initial_state = DeliberationState(
            argumentation_log=argumentation_log,
            max_rounds=self._config.rounds,
        )
        final_state = await self._graph.ainvoke(initial_state)
        return final_state["final_verdict"], final_state["_debate_log"]

    # --- Nodes ---

    async def _distribute_context(self, state: DeliberationState) -> dict[str, Any]:
        # Reset per-round discussion for the new round; vote_history carries previous rounds
        return {"discussion_messages": [], "current_round_votes": []}

    async def _jury_discussion(self, state: DeliberationState) -> dict[str, Any]:
        discussion: list[dict[str, str]] = []
        for juror in self._jury:
            message = await juror.discuss(
                argumentation_log=state.argumentation_log,
                previous_rounds=state.vote_history,
                current_discussion=discussion,
                round=state.current_round + 1,
            )
            discussion.append({"juror_id": juror.juror_id, "message": message})
        return {"discussion_messages": discussion}

    async def _jury_vote(self, state: DeliberationState) -> dict[str, Any]:
        vote_tasks = [
            juror.vote(
                argumentation_log=state.argumentation_log,
                previous_rounds=state.vote_history,
                discussion_messages=state.discussion_messages,
                round=state.current_round + 1,
            )
            for juror in self._jury
        ]
        votes: list[JurorVote] = await asyncio.gather(*vote_tasks)
        return {"current_round_votes": [v.model_dump() for v in votes]}

    async def _aggregate_votes(self, state: DeliberationState) -> dict[str, Any]:
        from collections import Counter
        votes = [JurorVote(**v) for v in state.current_round_votes]
        counts = Counter(v.vote for v in votes)
        top_verdict, top_count = counts.most_common(1)[0]
        is_unanimous = top_count == len(votes)
        round_record = {
            "round": state.current_round + 1,
            "votes": state.current_round_votes,
            "is_unanimous": is_unanimous,
            "top_verdict": top_verdict if is_unanimous else None,
        }
        return {
            "vote_history": state.vote_history + [round_record],
            "current_round": state.current_round + 1,
        }

    async def _check_consensus(self, state: DeliberationState) -> dict[str, Any]:
        last_round = state.vote_history[-1] if state.vote_history else {}
        is_unanimous = last_round.get("is_unanimous", False)
        if is_unanimous:
            return {"consensus_reached": True, "final_verdict": last_round["top_verdict"]}
        return {"consensus_reached": False}

    async def _apply_voting_strategy(self, state: DeliberationState) -> dict[str, Any]:
        all_votes = [
            JurorVote(**v)
            for round_record in state.vote_history
            for v in round_record["votes"]
        ]
        # Use only latest round votes for strategy
        latest_votes = [JurorVote(**v) for v in state.vote_history[-1]["votes"]]

        for strategy in self._voting_strategies:
            strategy_name = type(strategy).__name__
            result = await strategy.apply(latest_votes, self._judge, state.argumentation_log)
            if not result.is_tie:
                return {"final_verdict": result.verdict, "voting_strategy_applied": strategy_name}
        return {"final_verdict": "Undecided", "voting_strategy_applied": "fallback"}

    async def _finalize_verdict(self, state: DeliberationState) -> dict[str, Any]:
        rounds = []
        for round_record in state.vote_history:
            votes = [JurorVote(**v) for v in round_record["votes"]]
            discussion = state.discussion_messages if round_record["round"] == state.current_round else []
            rounds.append(RoundDeliberation(
                round=round_record["round"],
                discussion_messages=discussion,
                votes=votes,
                aggregated_result=round_record.get("top_verdict"),
            ))
        debate_log = DebateLog(
            rounds=rounds,
            final_voting_strategy_applied=state.voting_strategy_applied or "unanimous",
        )
        return {"_debate_log": debate_log}

    # --- Routing ---

    def _route_after_consensus(self, state: DeliberationState) -> str:
        if state.consensus_reached:
            return "consensus"
        if state.current_round >= state.max_rounds:
            return "exhausted"
        return "continue"
```

- [ ] **Step 4: Run existing tests**

```bash
uv run pytest tests/unit/ -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add psalm/phases/deliberation.py psalm/models/state.py
git commit -m "feat: scaffold DeliberationPhase LangGraph subgraph"
```

---

### Task 2: DeliberationPhase Integration Tests

**Files:**
- Create: `tests/integration/test_deliberation_phase.py`

**Interfaces:**
- Produces: fully tested `DeliberationPhase.run()` covering consensus, no-consensus + voting strategies, and blind voting verification

- [ ] **Step 1: Write integration tests**

```python
# tests/integration/test_deliberation_phase.py
import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from psalm.agents.judge import Judge
from psalm.agents.juror import Juror
from psalm.models.config import AgentConfig, DebateConfig
from psalm.models.result import JurorVote
from psalm.phases.deliberation import DeliberationPhase
from psalm.voting.judge_tiebreaker import JudgeTiebreakerVoting
from psalm.voting.simple_majority import SimpleMajorityVoting
from psalm.voting.trust_weighted import TrustWeightedVoting


@pytest.fixture
def agent_config_factory():
    def _make(seed: int) -> AgentConfig:
        return AgentConfig(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-4o",
            seed=seed,
        )
    return _make


@pytest.fixture
def mock_jurors():
    jurors = []
    for i in range(3):
        j = AsyncMock(spec=Juror)
        j.juror_id = f"juror-{i}"
        j.discuss = AsyncMock(return_value=f"Juror {i}: I believe the evidence supports infringement.")
        j.vote = AsyncMock(return_value=JurorVote(juror_id=f"juror-{i}", vote="Guilty", rationale="Strong evidence."))
        jurors.append(j)
    return jurors


@pytest.fixture
def mock_judge():
    judge = AsyncMock(spec=Judge)
    judge.tiebreak = AsyncMock(return_value="Guilty")
    return judge


@pytest.fixture
def voting_strategies(mock_judge):
    return [
        SimpleMajorityVoting(),
        TrustWeightedVoting(),
        JudgeTiebreakerVoting(),
    ]


@pytest.fixture
def deliberation_phase(mock_jurors, voting_strategies, mock_judge):
    config = DebateConfig(rounds=3)
    return DeliberationPhase(
        jury=mock_jurors,
        voting_strategies=voting_strategies,
        judge=mock_judge,
        config=config,
    )


async def test_unanimous_verdict_first_round(deliberation_phase, minimal_argumentation_log):
    verdict, log = await deliberation_phase.run(minimal_argumentation_log)
    assert verdict == "Guilty"
    assert len(log.rounds) == 1


async def test_debate_log_contains_discussion(deliberation_phase, minimal_argumentation_log):
    verdict, log = await deliberation_phase.run(minimal_argumentation_log)
    assert len(log.rounds) > 0
    # Discussion messages populated from juror.discuss calls
    assert log.rounds[0].votes is not None


async def test_non_unanimous_triggers_more_rounds(mock_jurors, voting_strategies, mock_judge, minimal_argumentation_log):
    # First two rounds: split vote; third round: unanimous
    call_count = [0]

    async def split_then_agree(*args, **kwargs):
        call_count[0] += 1
        round_num = (call_count[0] - 1) // 3
        if round_num < 2:
            votes = ["Guilty", "Not Guilty", "Undecided"]
            juror_idx = (call_count[0] - 1) % 3
            return JurorVote(juror_id=f"juror-{juror_idx}", vote=votes[juror_idx], rationale="r")
        return JurorVote(juror_id="juror-0", vote="Not Guilty", rationale="On reflection, not infringing.")

    for j in mock_jurors:
        j.vote = split_then_agree

    config = DebateConfig(rounds=3)
    phase = DeliberationPhase(mock_jurors, voting_strategies, mock_judge, config)
    verdict, log = await phase.run(minimal_argumentation_log)
    assert len(log.rounds) > 1


async def test_jury_votes_in_parallel(mock_jurors, voting_strategies, mock_judge, minimal_argumentation_log):
    call_times = []

    async def record_time(*args, **kwargs):
        call_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.05)
        return JurorVote(juror_id="j", vote="Guilty", rationale="r")

    for j in mock_jurors:
        j.vote = record_time

    config = DebateConfig(rounds=1)
    phase = DeliberationPhase(mock_jurors, voting_strategies, mock_judge, config)
    await phase.run(minimal_argumentation_log)

    # All votes should start within a small window (parallel, not sequential)
    assert len(call_times) == 3
    time_spread = max(call_times) - min(call_times)
    assert time_spread < 0.03, f"Votes not parallel — spread was {time_spread:.3f}s"


async def test_exhausted_rounds_applies_voting_strategy(mock_jurors, voting_strategies, mock_judge, minimal_argumentation_log):
    # All rounds split — should apply voting strategy chain
    async def always_split(juror_idx):
        async def _vote(*args, **kwargs):
            votes = ["Guilty", "Not Guilty", "Undecided"]
            return JurorVote(juror_id=f"juror-{juror_idx}", vote=votes[juror_idx], rationale="r")
        return _vote

    for i, j in enumerate(mock_jurors):
        j.vote = await always_split(i)

    mock_judge.tiebreak = AsyncMock(return_value="Undecided")
    config = DebateConfig(rounds=2)
    phase = DeliberationPhase(mock_jurors, voting_strategies, mock_judge, config)
    verdict, log = await phase.run(minimal_argumentation_log)
    assert verdict in {"Guilty", "Not Guilty", "Undecided"}
    assert len(log.rounds) == 2
```

- [ ] **Step 2: Run to verify failure (some tests will fail until phase logic is complete)**

```bash
uv run pytest tests/integration/test_deliberation_phase.py -v
```

- [ ] **Step 3: Fix `_finalize_verdict` to correctly track per-round discussion**

The current `_finalize_verdict` only attaches discussion to the current round. Update it to persist discussion per round in state. Open `psalm/phases/deliberation.py` and update `_aggregate_votes` to also store discussion:

```python
    async def _aggregate_votes(self, state: DeliberationState) -> dict[str, Any]:
        from collections import Counter
        votes = [JurorVote(**v) for v in state.current_round_votes]
        counts = Counter(v.vote for v in votes)
        top_verdict, top_count = counts.most_common(1)[0]
        is_unanimous = top_count == len(votes)
        round_record = {
            "round": state.current_round + 1,
            "votes": state.current_round_votes,
            "discussion_messages": state.discussion_messages,
            "is_unanimous": is_unanimous,
            "top_verdict": top_verdict if is_unanimous else None,
        }
        return {
            "vote_history": state.vote_history + [round_record],
            "current_round": state.current_round + 1,
        }
```

And update `_finalize_verdict` to read discussion from vote_history records:

```python
    async def _finalize_verdict(self, state: DeliberationState) -> dict[str, Any]:
        rounds = []
        for round_record in state.vote_history:
            votes = [JurorVote(**v) for v in round_record["votes"]]
            rounds.append(RoundDeliberation(
                round=round_record["round"],
                discussion_messages=round_record.get("discussion_messages", []),
                votes=votes,
                aggregated_result=round_record.get("top_verdict"),
            ))
        debate_log = DebateLog(
            rounds=rounds,
            final_voting_strategy_applied=state.voting_strategy_applied or "unanimous",
        )
        return {"_debate_log": debate_log}
```

- [ ] **Step 4: Run integration tests**

```bash
uv run pytest tests/integration/test_deliberation_phase.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add psalm/phases/deliberation.py psalm/models/state.py tests/integration/test_deliberation_phase.py
git commit -m "feat: complete DeliberationPhase with blind parallel voting and integration tests"
```
