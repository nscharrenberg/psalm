from __future__ import annotations

from typing import Any, Awaitable, Callable

from langgraph.graph import END, StateGraph

from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.prosecutor import Prosecutor
from psalm.events import (
    ArgumentationRoundStarted,
    ArgumentationStabilityChecked,
    ArgumentBatchCompletenessRetry,
    ArgumentRejected,
    ArgumentSubmitted,
    ArgumentValidated,
    ClosingArgumentDelivered,
    ClosingStatementDelivered,
    emit,
)
from psalm.exceptions import PSALMAgentError
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.evidence import Argument, ArgumentBatch, ClosingStatement
from psalm.models.result import ArgumentationLog, RejectedArgument, RoundArguments
from psalm.models.state import ArgumentationState
from psalm.phases.base import BasePhase

_COMPLETENESS_RETRY_ATTEMPTS = 2
_COMPLETENESS_RETRY_HINT = (
    "Your previous response provided no arguments and did not declare "
    "no_further_arguments. You MUST either provide at least one factually-grounded "
    "argument, or explicitly set no_further_arguments=True with a closing_statement "
    "explaining why you have nothing further to add."
)


def _rejected_entry(arg: Argument, rejection_reason: str | None) -> dict[str, Any]:
    return {
        "round": arg.round,
        "argument": arg.model_dump(),
        "rejection_reason": rejection_reason or "No reason provided.",
    }


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
        graph.add_node(
            "judge_validate_prosecution_counter", self._judge_validate_prosecution_counter
        )
        graph.add_node("check_next_round", self._check_next_round)
        graph.add_node("prosecution_closing_argument", self._prosecution_closing_argument)
        graph.add_node("defense_closing_argument", self._defense_closing_argument)
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
            {"continue": "prosecution_argue", "done": "prosecution_closing_argument"},
        )
        graph.add_edge("prosecution_closing_argument", "defense_closing_argument")
        graph.add_edge("defense_closing_argument", "finalize_arguments")
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
        self,
        call: Callable[[str | None], Awaitable[ArgumentBatch]],
        *,
        role: str,
        round: int,
    ) -> ArgumentBatch:
        hint: str | None = None
        max_attempts = _COMPLETENESS_RETRY_ATTEMPTS + 1
        for attempt in range(max_attempts):
            batch = await call(hint)
            if await self._judge.validate_batch_completeness(batch):
                return batch
            await emit(ArgumentBatchCompletenessRetry(
                round=round, role=role, attempt=attempt + 1, max_attempts=max_attempts,
            ))
            hint = _COMPLETENESS_RETRY_HINT
        raise PSALMAgentError(
            code="PSALM-A004",
            message=(
                "Agent failed to provide arguments or declare no_further_arguments "
                "after retries."
            ),
            context={"attempts": max_attempts},
            suggestion="Check the LLM model's instruction-following reliability.",
        )

    # --- Step 1: Prosecution affirmative arguments ---

    async def _prosecution_argue(self, state: ArgumentationState) -> dict[str, Any]:
        round_num = state.current_round + 1
        await emit(ArgumentationRoundStarted(round=round_num))
        prior_defense = list(state.defense_arguments) or None
        batch = await self._call_with_completeness_retry(
            lambda hint: self._prosecutor.gather_arguments(
                source_text=state.source_text,
                target_text=state.target_text,
                dimensions=state.dimensions,
                round=round_num,
                prior_defense_arguments=prior_defense,
                retry_hint=hint,
            ),
            role="prosecution",
            round=round_num,
        )
        for arg in batch.arguments:
            await emit(ArgumentSubmitted(
                round=round_num, role="prosecution", kind="argument", argument=arg
            ))
        if batch.closing_statement:
            await emit(ClosingStatementDelivered(
                round=round_num, role="prosecution", statement=batch.closing_statement
            ))
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
        rejected = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg.model_dump())
                await emit(ArgumentValidated(round=arg.round, role="prosecution", argument=arg))
            else:
                rejected.append(_rejected_entry(arg, result.rejection_reason))
                await emit(ArgumentRejected(
                    round=arg.round, role="prosecution", argument=arg,
                    reason=result.rejection_reason or "No reason provided.",
                ))
        existing = [a.model_dump() for a in state.prosecution_arguments]
        return {
            "validated_prosecution_arguments": valid,
            "prosecution_arguments": existing + valid,
            "prosecution_rejected_arguments": state.prosecution_rejected_arguments + rejected,
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
            ),
            role="defense",
            round=round_num,
        )
        for arg in batch.arguments:
            await emit(ArgumentSubmitted(
                round=round_num, role="defense", kind="counter", argument=arg
            ))
        if batch.closing_statement:
            await emit(ClosingStatementDelivered(
                round=round_num, role="defense", statement=batch.closing_statement
            ))
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_defense_counters": [a.model_dump() for a in batch.arguments],
            "defense_counter_closing_statements": (
                state.defense_counter_closing_statements + closing
            ),
        }

    async def _judge_validate_defense_counter(self, state: ArgumentationState) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_defense_counters]
        valid = []
        rejected = []
        for arg in pending:
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense",
                dimensions=state.dimensions,
            )
            if result.is_valid:
                valid.append(arg.model_dump())
                await emit(ArgumentValidated(round=arg.round, role="defense", argument=arg))
            else:
                rejected.append(_rejected_entry(arg, result.rejection_reason))
                await emit(ArgumentRejected(
                    round=arg.round, role="defense", argument=arg,
                    reason=result.rejection_reason or "No reason provided.",
                ))
        existing = [a.model_dump() for a in state.defense_counters]
        return {
            "defense_counters": existing + valid,
            "defense_counter_rejected_arguments": (
                state.defense_counter_rejected_arguments + rejected
            ),
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
            ),
            role="defense",
            round=round_num,
        )
        for arg in batch.arguments:
            await emit(ArgumentSubmitted(
                round=round_num, role="defense", kind="argument", argument=arg
            ))
        if batch.closing_statement:
            await emit(ClosingStatementDelivered(
                round=round_num, role="defense", statement=batch.closing_statement
            ))
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
        rejected = []
        for arg in pending:
            result = await self._judge.validate_argument(
                arg, state.source_text, state.target_text, role="defense",
                dimensions=state.dimensions,
            )
            if result.is_valid:
                valid.append(arg.model_dump())
                await emit(ArgumentValidated(round=arg.round, role="defense", argument=arg))
            else:
                rejected.append(_rejected_entry(arg, result.rejection_reason))
                await emit(ArgumentRejected(
                    round=arg.round, role="defense", argument=arg,
                    reason=result.rejection_reason or "No reason provided.",
                ))
        existing = [a.model_dump() for a in state.defense_arguments]
        return {
            "validated_defense_arguments": valid,
            "defense_arguments": existing + valid,
            "defense_rejected_arguments": state.defense_rejected_arguments + rejected,
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
            ),
            role="prosecution",
            round=round_num,
        )
        for arg in batch.arguments:
            await emit(ArgumentSubmitted(
                round=round_num, role="prosecution", kind="counter", argument=arg
            ))
        if batch.closing_statement:
            await emit(ClosingStatementDelivered(
                round=round_num, role="prosecution", statement=batch.closing_statement
            ))
        closing = (
            [ClosingStatement(round=round_num, statement=batch.closing_statement).model_dump()]
            if batch.closing_statement else []
        )
        return {
            "pending_prosecution_counters": [a.model_dump() for a in batch.arguments],
            "prosecution_counter_closing_statements": (
                state.prosecution_counter_closing_statements + closing
            ),
        }

    async def _judge_validate_prosecution_counter(
        self, state: ArgumentationState
    ) -> dict[str, Any]:
        pending = [Argument(**a) for a in state.pending_prosecution_counters]
        valid = []
        rejected = []
        for arg in pending:
            result = await self._judge.validate_argument(arg, state.source_text, state.target_text)
            if result.is_valid:
                valid.append(arg.model_dump())
                await emit(ArgumentValidated(round=arg.round, role="prosecution", argument=arg))
            else:
                rejected.append(_rejected_entry(arg, result.rejection_reason))
                await emit(ArgumentRejected(
                    round=arg.round, role="prosecution", argument=arg,
                    reason=result.rejection_reason or "No reason provided.",
                ))
        existing = [a.model_dump() for a in state.prosecution_counters]
        return {
            "prosecution_counters": existing + valid,
            "prosecution_counter_rejected_arguments": (
                state.prosecution_counter_rejected_arguments + rejected
            ),
        }

    # --- Dedicated closing arguments (delivered once, after the round loop ends) ---

    async def _prosecution_closing_argument(self, state: ArgumentationState) -> dict[str, Any]:
        statement = await self._prosecutor.deliver_closing_argument(
            dimensions=state.dimensions,
            prosecution_arguments=state.prosecution_arguments,
            prosecution_counters=state.prosecution_counters,
            defense_counters=state.defense_counters,
            defense_arguments=state.defense_arguments,
        )
        await emit(ClosingArgumentDelivered(role="prosecution", statement=statement))
        return {"prosecution_closing_argument": statement}

    async def _defense_closing_argument(self, state: ArgumentationState) -> dict[str, Any]:
        statement = await self._defense.deliver_closing_argument(
            dimensions=state.dimensions,
            defense_counters=state.defense_counters,
            defense_arguments=state.defense_arguments,
            prosecution_arguments=state.prosecution_arguments,
            prosecution_counters=state.prosecution_counters,
        )
        await emit(ClosingArgumentDelivered(role="defense", statement=statement))
        return {"defense_closing_argument": statement}

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
        decision = stability or both_empty
        await emit(ArgumentationStabilityChecked(round=round_num, stability_detected=decision))
        return {
            "current_round": state.current_round + 1,
            "stability_detected": decision,
        }

    async def _finalize_arguments(self, state: ArgumentationState) -> dict[str, Any]:
        def _closing_for(statements: list[dict[str, Any]], r: int) -> str | None:
            match = next((s for s in statements if s["round"] == r), None)
            return match["statement"] if match else None

        def _rejected_for(entries: list[dict[str, Any]], r: int) -> list[RejectedArgument]:
            return [
                RejectedArgument(
                    argument=Argument(**e["argument"]),
                    rejection_reason=e["rejection_reason"],
                )
                for e in entries
                if e["round"] == r
            ]

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
            pros_rejected = _rejected_for(state.prosecution_rejected_arguments, r)
            def_counter_rejected = _rejected_for(state.defense_counter_rejected_arguments, r)
            def_rejected = _rejected_for(state.defense_rejected_arguments, r)
            pros_counter_rejected = _rejected_for(state.prosecution_counter_rejected_arguments, r)
            if (
                pros_args or def_counters or def_args or pros_counters
                or pros_closing or def_counter_closing or def_closing or pros_counter_closing
                or pros_rejected or def_counter_rejected or def_rejected or pros_counter_rejected
            ):
                rounds.append(
                    RoundArguments(
                        round=r,
                        prosecution_arguments=pros_args,
                        prosecution_rejected_arguments=pros_rejected,
                        prosecution_closing_statement=pros_closing,
                        defense_counters=def_counters,
                        defense_counter_rejected_arguments=def_counter_rejected,
                        defense_counter_closing_statement=def_counter_closing,
                        defense_arguments=def_args,
                        defense_rejected_arguments=def_rejected,
                        defense_closing_statement=def_closing,
                        prosecution_counters=pros_counters,
                        prosecution_counter_rejected_arguments=pros_counter_rejected,
                        prosecution_counter_closing_statement=pros_counter_closing,
                    )
                )
        log = ArgumentationLog(
            rounds=rounds,
            prosecution_closing_argument=state.prosecution_closing_argument,
            defense_closing_argument=state.defense_closing_argument,
        )
        return {"argumentation_log": log.model_dump()}

    # --- Routing ---

    def _route_next_round(self, state: ArgumentationState) -> str:
        if state.stability_detected or state.current_round >= state.max_rounds:
            return "done"
        return "continue"
