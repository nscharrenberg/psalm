from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Sequence
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from psalm.agents.judge import Judge
from psalm.agents.juror import Juror
from psalm.dimensions.base import _IMPORTANCE_MULTIPLIERS, _SCORE_VALUES, Dimension
from psalm.events import (
    DeliberationRoundStarted,
    JurorVoteCast,
    JuryConsensusChecked,
    JuryDiscussionMessage,
    VotingStrategyApplied,
    emit,
)
from psalm.models.config import DebateConfig
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
    JurorVote,
    RoundDeliberation,
)
from psalm.models.state import DeliberationState
from psalm.voting.base import VotingStrategy


class DeliberationPhase:
    def __init__(
        self,
        jury: list[Juror],
        voting_strategies: Sequence[VotingStrategy],
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
        graph.add_node("jury_vote", self._jury_vote)
        graph.add_node("aggregate_votes", self._aggregate_votes)
        graph.add_node("check_consensus", self._check_consensus)
        graph.add_node("jury_discussion", self._jury_discussion)
        graph.add_node("apply_voting_strategy", self._apply_voting_strategy)
        graph.add_node("finalize_verdict", self._finalize_verdict)

        graph.set_entry_point("distribute_context")
        graph.add_edge("distribute_context", "jury_vote")       # vote first, no discussion
        graph.add_edge("jury_vote", "aggregate_votes")
        graph.add_edge("aggregate_votes", "check_consensus")
        graph.add_conditional_edges(
            "check_consensus",
            self._route_after_consensus,
            {
                "consensus": "finalize_verdict",
                "continue": "jury_discussion",               # discussion only from round 2+
                "exhausted": "apply_voting_strategy",
            },
        )
        graph.add_edge("jury_discussion", "jury_vote")
        graph.add_edge("apply_voting_strategy", "finalize_verdict")
        graph.add_edge("finalize_verdict", END)
        return graph.compile()

    async def run(
        self,
        argumentation_log: ArgumentationLog,
        dimension: Dimension,
    ) -> tuple[Literal["Guilty", "Not Guilty", "Undecided"], DebateLog, float]:
        initial_state = DeliberationState(
            argumentation_log=argumentation_log,
            max_rounds=self._config.deliberation_rounds,
            current_dimension=dimension,
        )
        final_state = await self._graph.ainvoke(initial_state.model_dump())
        debate_log_data = final_state["debate_log"]
        debate_log = (
            DebateLog(**debate_log_data)
            if isinstance(debate_log_data, dict)
            else debate_log_data
        )
        return final_state["final_verdict"], debate_log, final_state["weighted_score"]

    # --- Nodes ---

    async def _distribute_context(self, state: DeliberationState) -> dict[str, Any]:
        return {"discussion_messages": [], "current_round_votes": []}

    async def _jury_vote(self, state: DeliberationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        await emit(DeliberationRoundStarted(round=round_num))
        vote_tasks = [
            juror.vote(
                argumentation_log=state.argumentation_log,
                previous_rounds=state.vote_history,
                discussion_messages=state.discussion_messages,
                round=round_num,
                dimension=state.current_dimension,
            )
            for juror in self._jury
        ]
        votes: list[JurorVote] = await asyncio.gather(*vote_tasks)
        for v in votes:
            await emit(JurorVoteCast(
                round=round_num, juror_id=v.juror_id, vote=v.vote, rationale=v.rationale,
                dimension_scores=v.dimension_scores,
            ))
        return {"current_round_votes": [v.model_dump() for v in votes]}

    async def _aggregate_votes(self, state: DeliberationState) -> dict[str, Any]:
        votes = [JurorVote(**v) for v in state.current_round_votes]
        counts = Counter(v.vote for v in votes)
        top_verdict, top_count = counts.most_common(1)[0]
        is_unanimous = top_count == len(votes)
        weighted_score = _compute_weighted_score(votes, state.current_dimension)
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
            "weighted_score": weighted_score,
        }

    async def _check_consensus(self, state: DeliberationState) -> dict[str, Any]:
        last_round = state.vote_history[-1] if state.vote_history else {}
        is_unanimous = last_round.get("is_unanimous", False)
        top_verdict = last_round.get("top_verdict")
        await emit(JuryConsensusChecked(
            round=state.current_round, is_unanimous=is_unanimous, top_verdict=top_verdict,
        ))
        if is_unanimous:
            return {"consensus_reached": True, "final_verdict": last_round["top_verdict"]}
        return {"consensus_reached": False}

    async def _jury_discussion(self, state: DeliberationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        discussion: list[dict[str, str]] = []
        for juror in self._jury:
            message = await juror.discuss(
                argumentation_log=state.argumentation_log,
                previous_rounds=state.vote_history,
                current_discussion=discussion,
                round=round_num,
            )
            discussion.append({"juror_id": juror.juror_id, "message": message})
            await emit(
                JuryDiscussionMessage(round=round_num, juror_id=juror.juror_id, message=message)
            )
        return {"discussion_messages": discussion}

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
        return {"debate_log": debate_log.model_dump()}

    # --- Routing ---

    def _route_after_consensus(self, state: DeliberationState) -> str:
        if state.consensus_reached:
            return "consensus"
        if state.current_round >= state.max_rounds:
            return "exhausted"
        return "continue"


def _compute_weighted_score(votes: list[JurorVote], dimension: Dimension) -> float:
    """Average juror scores per sub-dimension, weight by importance, normalise to [0, 1]."""
    if not votes:
        return 0.0

    sub_dim_map = {sd.name: sd for sd in dimension.sub_dimensions}
    if not sub_dim_map:
        return 0.0

    # Collect all score values per sub-dimension across jurors
    scores_by_sub: dict[str, list[int]] = {name: [] for name in sub_dim_map}
    for vote in votes:
        for ds in vote.dimension_scores:
            if ds.sub_dimension in scores_by_sub:
                scores_by_sub[ds.sub_dimension].append(_SCORE_VALUES[ds.score])

    weighted_total = 0.0
    max_possible = 0.0
    for sub_name, sub_dim in sub_dim_map.items():
        multiplier = _IMPORTANCE_MULTIPLIERS[sub_dim.importance]
        raw_scores = scores_by_sub[sub_name]
        avg = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
        max_score = 3  # SimilarityScore.CLEAR
        contribution = (max_score - avg) if sub_dim.inverse else avg
        weighted_total += contribution * multiplier
        max_possible += max_score * multiplier

    if max_possible == 0.0:
        return 0.0
    return weighted_total / max_possible
