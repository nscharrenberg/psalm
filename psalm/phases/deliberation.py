from __future__ import annotations
import asyncio
from collections import Counter
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
        initial_state = DeliberationState(
            argumentation_log=argumentation_log,
            max_rounds=self._config.rounds,
        )
        final_state = await self._graph.ainvoke(initial_state.model_dump())
        debate_log_data = final_state["debate_log"]
        debate_log = DebateLog(**debate_log_data) if isinstance(debate_log_data, dict) else debate_log_data
        return final_state["final_verdict"], debate_log

    # --- Nodes (LangGraph passes DeliberationState Pydantic model directly) ---

    async def _distribute_context(self, state: DeliberationState) -> dict[str, Any]:
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

    async def _check_consensus(self, state: DeliberationState) -> dict[str, Any]:
        last_round = state.vote_history[-1] if state.vote_history else {}
        is_unanimous = last_round.get("is_unanimous", False)
        if is_unanimous:
            return {"consensus_reached": True, "final_verdict": last_round["top_verdict"]}
        return {"consensus_reached": False}

    async def _apply_voting_strategy(self, state: DeliberationState) -> dict[str, Any]:
        latest_votes = [JurorVote(**v) for v in state.vote_history[-1]["votes"]]
        for strategy in self._voting_strategies:
            result = await strategy.apply(latest_votes, self._judge, state.argumentation_log)
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
