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
