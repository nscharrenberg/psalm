from __future__ import annotations

import asyncio
import time
from typing import Literal

from psalm.courtroom.base import CourtroomSetup
from psalm.dimensions.base import _IMPORTANCE_MULTIPLIERS, Dimension, Importance
from psalm.events import DimensionStarted, DimensionVerdictReached, FinalVerdictReached, emit
from psalm.events.context import _current_dimension
from psalm.models.config import CaseInput, DebateConfig, EvaluationStrategy
from psalm.models.result import (
    ArgumentationLog,
    DimensionVerdict,
    PSALMResult,
    ResultMetadata,
)
from psalm.phases.argumentation import ArgumentationPhase
from psalm.phases.deliberation import DeliberationPhase


class DefaultCourtroom(CourtroomSetup):
    def __init__(
        self,
        argumentation_phase: ArgumentationPhase,
        deliberation_phases: list[DeliberationPhase],
        config: DebateConfig,
    ) -> None:
        self._argumentation_phase = argumentation_phase
        self._deliberation_phases = deliberation_phases
        self._config = config

    async def run(self, case_input: CaseInput) -> PSALMResult:
        start = time.monotonic()
        strategy = self._config.evaluation_strategy

        if strategy == EvaluationStrategy.FULLY_SEPARATE:
            dimension_verdicts = await self._run_fully_separate(case_input)
        elif strategy == EvaluationStrategy.SHARED_ARG_PER_DIM_DELIBERATION:
            dimension_verdicts = await self._run_shared_arg(case_input)
        else:  # SHARED_ALL
            dimension_verdicts = await self._run_shared_all(case_input)

        verdict = _aggregate_verdict(dimension_verdicts, self._config.guilty_threshold)
        rationale = _synthesize_rationale(verdict, dimension_verdicts)
        duration = time.monotonic() - start

        # Dimension verdicts may share the same ArgumentationLog instance (e.g. under
        # SHARED_ARG_PER_DIM_DELIBERATION / SHARED_ALL, one argumentation phase run is
        # reused across all dimensions). Dedup by object identity before summing rounds
        # so shared logs are not counted once per dimension.
        distinct_arg_logs = {
            id(dv.argumentation_log): dv.argumentation_log for dv in dimension_verdicts
        }
        total_arg_rounds = sum(len(log.rounds) for log in distinct_arg_logs.values())
        total_delib_rounds = sum(len(dv.debate_log.rounds) for dv in dimension_verdicts)
        strategy_applied = (
            dimension_verdicts[0].debate_log.final_voting_strategy_applied
            if dimension_verdicts
            else "none"
        )

        metadata = ResultMetadata(
            duration_seconds=round(duration, 3),
            argumentation_rounds_used=total_arg_rounds,
            deliberation_rounds_used=total_delib_rounds,
            voting_strategy_applied=strategy_applied,
        )
        result = PSALMResult(
            verdict=verdict,
            rationale=rationale,
            dimension_verdicts=dimension_verdicts,
            metadata=metadata,
        )
        await emit(FinalVerdictReached(result=result))
        return result

    async def _run_fully_separate(self, case_input: CaseInput) -> list[DimensionVerdict]:
        tasks = [
            self._run_single_dimension(dim, delib_phase, case_input)
            for dim, delib_phase in zip(
                case_input.dimensions, self._deliberation_phases, strict=True
            )
        ]
        return list(await asyncio.gather(*tasks))

    async def _run_single_dimension(
        self,
        dimension: Dimension,
        delib_phase: DeliberationPhase,
        case_input: CaseInput,
    ) -> DimensionVerdict:
        _current_dimension.set(dimension.name)
        await emit(DimensionStarted(
            dimension_type=dimension.dimension_type, importance=dimension.importance.value,
        ))
        if dimension.dimension_type == "infringement":
            exception_dims = [d for d in case_input.dimensions if d.dimension_type == "exception"]
            scoped_dims = [dimension] + exception_dims
        else:
            scoped_dims = [dimension]
        scoped_input = case_input.model_copy(update={"dimensions": scoped_dims})
        arg_log = await self._argumentation_phase.run(scoped_input)
        verdict, debate_log, weighted_score = await delib_phase.run(arg_log, dimension)
        await emit(DimensionVerdictReached(
            dimension_type=dimension.dimension_type, importance=dimension.importance.value,
            verdict=verdict, weighted_score=weighted_score,
        ))
        return DimensionVerdict(
            dimension=dimension.name,
            dimension_type=dimension.dimension_type,
            importance=dimension.importance,
            verdict=verdict,
            weighted_score=weighted_score,
            argumentation_log=arg_log,
            debate_log=debate_log,
        )

    async def _run_shared_arg(self, case_input: CaseInput) -> list[DimensionVerdict]:
        arg_log = await self._argumentation_phase.run(case_input)
        tasks = [
            self._deliberate_single(dim, delib_phase, arg_log)
            for dim, delib_phase in zip(
                case_input.dimensions, self._deliberation_phases, strict=True
            )
        ]
        return list(await asyncio.gather(*tasks))

    async def _deliberate_single(
        self,
        dimension: Dimension,
        delib_phase: DeliberationPhase,
        arg_log: ArgumentationLog,
    ) -> DimensionVerdict:
        _current_dimension.set(dimension.name)
        await emit(DimensionStarted(
            dimension_type=dimension.dimension_type, importance=dimension.importance.value,
        ))
        verdict, debate_log, weighted_score = await delib_phase.run(arg_log, dimension)
        await emit(DimensionVerdictReached(
            dimension_type=dimension.dimension_type, importance=dimension.importance.value,
            verdict=verdict, weighted_score=weighted_score,
        ))
        return DimensionVerdict(
            dimension=dimension.name,
            dimension_type=dimension.dimension_type,
            importance=dimension.importance,
            verdict=verdict,
            weighted_score=weighted_score,
            argumentation_log=arg_log,
            debate_log=debate_log,
        )

    async def _run_shared_all(self, case_input: CaseInput) -> list[DimensionVerdict]:
        arg_log = await self._argumentation_phase.run(case_input)
        delib_phase = self._deliberation_phases[0]
        tasks = [
            self._deliberate_single(dim, delib_phase, arg_log)
            for dim in case_input.dimensions
        ]
        return list(await asyncio.gather(*tasks))


def _aggregate_verdict(
    dimension_verdicts: list[DimensionVerdict],
    guilty_threshold: float,
) -> Literal["Guilty", "Not Guilty", "Undecided"]:
    infringement_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "infringement"]
    if not infringement_verdicts:
        return "Undecided"

    # Hard override: any CRITICAL infringement dimension that is Guilty → overall Guilty.
    # Exception dimensions never trigger this, regardless of their own importance/verdict.
    for dv in infringement_verdicts:
        if dv.importance == Importance.CRITICAL and dv.verdict == "Guilty":
            return "Guilty"

    normalised = _blend(infringement_verdicts)
    if normalised is None:
        return "Undecided"

    exception_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "exception"]
    exception_score = _blend(exception_verdicts)
    if exception_score is None:
        exception_score = 0.0
    effective = normalised * (1 - exception_score)

    if effective >= guilty_threshold:
        return "Guilty"
    return "Not Guilty"


def _blend(verdicts: list[DimensionVerdict]) -> float | None:
    total_weighted = 0.0
    total_weight = 0.0
    for dv in verdicts:
        multiplier = _IMPORTANCE_MULTIPLIERS[dv.importance]
        total_weighted += dv.weighted_score * multiplier
        total_weight += multiplier
    if total_weight == 0.0:
        return None
    return total_weighted / total_weight


def _synthesize_rationale(
    verdict: str,
    dimension_verdicts: list[DimensionVerdict],
) -> str:
    lines = [f"Verdict: {verdict}."]
    for dv in dimension_verdicts:
        suffix = (
            "" if dv.dimension_type == "infringement"
            else " [exception, discounts infringement score]"
        )
        lines.append(
            f"  {dv.dimension} [{dv.importance.value}]{suffix}: {dv.verdict} "
            f"(weighted score: {dv.weighted_score:.2f})"
        )
    exception_verdicts = [dv for dv in dimension_verdicts if dv.dimension_type == "exception"]
    exception_score = _blend(exception_verdicts)
    if exception_score:
        lines.append(f"  Exception discount applied: {exception_score:.2f}")
    return " ".join(lines)
