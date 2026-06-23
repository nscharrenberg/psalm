from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.prosecutor import Prosecutor
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import Argument
from psalm.models.result import ArgumentationLog, RoundArguments
from psalm.models.state import ArgumentationState
from psalm.phases.base import BasePhase


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

        graph.add_node("prosecutor_gather", self._prosecutor_gather)
        graph.add_node("judge_validate_prosecution", self._judge_validate_prosecution)
        graph.add_node("defense_gather", self._defense_gather)
        graph.add_node("judge_validate_defense", self._judge_validate_defense)
        graph.add_node("cross_examination", self._cross_examination)
        graph.add_node("check_next_round", self._check_next_round)
        graph.add_node("finalize_arguments", self._finalize_arguments)

        graph.set_entry_point("prosecutor_gather")
        graph.add_edge("prosecutor_gather", "judge_validate_prosecution")
        graph.add_edge("judge_validate_prosecution", "defense_gather")
        graph.add_edge("defense_gather", "judge_validate_defense")
        graph.add_conditional_edges(
            "judge_validate_defense",
            self._route_cross_exam,
            {"cross_examine": "cross_examination", "skip": "check_next_round"},
        )
        graph.add_edge("cross_examination", "check_next_round")
        graph.add_conditional_edges(
            "check_next_round",
            self._route_next_round,
            {"continue": "prosecutor_gather", "done": "finalize_arguments"},
        )
        graph.add_edge("finalize_arguments", END)

        return graph.compile()

    async def run(self, case_input: CaseInput) -> ArgumentationLog:
        initial_state = ArgumentationState(
            source_text=case_input.source_text,
            target_text=case_input.target_text,
            dimensions=case_input.dimensions,
            max_rounds=self._config.rounds,
        )
        final_state = await self._graph.ainvoke(initial_state.model_dump())
        log_data = final_state["argumentation_log"]
        if isinstance(log_data, dict):
            return ArgumentationLog(**log_data)
        return log_data

    # --- Nodes ---

    async def _prosecutor_gather(self, state: ArgumentationState) -> dict[str, Any]:
        arguments = await self._prosecutor.gather_arguments(
            source_text=state.source_text,
            target_text=state.target_text,
            dimensions=state.dimensions,
            round=state.current_round + 1,
        )
        return {"pending_prosecution_arguments": [a.model_dump() for a in arguments]}

    async def _judge_validate_prosecution(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_prosecution_arguments]
        valid = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg.model_dump())
        return {"validated_prosecution_arguments": valid}

    async def _defense_gather(self, state: ArgumentationState) -> dict[str, Any]:
        prosecution_args = [Argument(**a) for a in state.validated_prosecution_arguments]
        counter_arguments = await self._defense.gather_counter_arguments(
            source_text=state.source_text,
            target_text=state.target_text,
            dimensions=state.dimensions,
            prosecutor_arguments=prosecution_args,
            round=state.current_round + 1,
        )
        return {"pending_defense_arguments": [a.model_dump() for a in counter_arguments]}

    async def _judge_validate_defense(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_defense_arguments]
        prosecution_args = [Argument(**a) for a in state.validated_prosecution_arguments]
        valid = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg)
        cross_exam = await self._judge.should_cross_examine(prosecution_args, valid)
        existing_args = list(state.arguments)
        existing_counters = list(state.counter_arguments)
        return {
            "cross_examination_triggered": cross_exam,
            "arguments": [a.model_dump() for a in existing_args + prosecution_args],
            "counter_arguments": [a.model_dump() for a in existing_counters + valid],
        }

    async def _cross_examination(self, state: ArgumentationState) -> dict[str, Any]:
        return {}  # Future extension point

    async def _check_next_round(self, state: ArgumentationState) -> dict[str, Any]:
        prosecution_args = [Argument(**a) for a in state.validated_prosecution_arguments]
        prev_round_args = [a for a in state.arguments if a.round == state.current_round]
        stability = await self._judge.detect_stability(prosecution_args, prev_round_args)
        return {"current_round": state.current_round + 1, "stability_detected": stability}

    async def _finalize_arguments(self, state: ArgumentationState) -> dict[str, Any]:
        rounds = []
        for r in range(1, state.current_round + 1):
            round_args = [a for a in state.arguments if a.round == r]
            round_counters = [a for a in state.counter_arguments if a.round == r]
            rounds.append(
                RoundArguments(
                    round=r,
                    arguments=round_args,
                    counter_arguments=round_counters,
                )
            )
        log = ArgumentationLog(rounds=rounds)
        return {"argumentation_log": log.model_dump()}

    # --- Routing ---

    def _route_cross_exam(self, state: ArgumentationState) -> str:
        return "cross_examine" if state.cross_examination_triggered else "skip"

    def _route_next_round(self, state: ArgumentationState) -> str:
        if state.stability_detected or state.current_round >= state.max_rounds:
            return "done"
        return "continue"
