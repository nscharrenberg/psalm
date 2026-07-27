from __future__ import annotations

from typing import Any

from catalog import resolve_dimensions
from config_resolution import resolve_agent_config, resolve_juror_config
from schemas import TrialConfigRequest
from trials import TrialStore

from psalm import PSALM
from psalm.exceptions import PSALMConfigError, PSALMError
from psalm.models.config import EvaluationStrategy


class TrialStartError(Exception):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.context = context or {}
        super().__init__(message)


def resolve_config(config: TrialConfigRequest) -> dict[str, Any]:
    try:
        prosecutor = resolve_agent_config("PROSECUTOR", config.prosecutor.model_dump())
        defense = resolve_agent_config("DEFENSE", config.defense.model_dump())
        judge = resolve_agent_config("JUDGE", config.judge.model_dump())
        jury = [
            resolve_juror_config(i, juror.model_dump())
            for i, juror in enumerate(config.jury)
        ]
    except ValueError as exc:
        raise TrialStartError(code="PSALM-WEB-001", message=str(exc)) from exc
    return {"prosecutor": prosecutor, "defense": defense, "judge": judge, "jury": jury}


async def build_psalm(config: TrialConfigRequest, resolved: dict[str, Any]):
    try:
        dimensions = resolve_dimensions(config.dimensions)
    except ValueError as exc:
        raise TrialStartError(code="PSALM-WEB-002", message=str(exc)) from exc

    try:
        evaluation_strategy = EvaluationStrategy(config.evaluation_strategy)
    except ValueError as exc:
        raise TrialStartError(
            code="PSALM-WEB-003",
            message=f"Unknown evaluation strategy: '{config.evaluation_strategy}'.",
        ) from exc

    try:
        return await (
            PSALM()
            .with_prosecutor(**resolved["prosecutor"])
            .with_defense(**resolved["defense"])
            .with_judge(**resolved["judge"])
            .with_jury(resolved["jury"])
            .with_dimensions(dimensions)
            .with_debate(
                argumentation_rounds=config.argumentation_rounds,
                deliberation_rounds=config.deliberation_rounds,
                time_limit_seconds=config.time_limit_seconds,
            )
            .with_execution(
                max_concurrent_llm_calls=config.max_concurrent_llm_calls,
                max_retries=config.max_retries,
                max_requests_per_minute=config.max_requests_per_minute or None,
                max_tokens_per_minute=config.max_tokens_per_minute or None,
                retry_after_fallback_seconds=config.retry_after_fallback_seconds or None,
            )
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .with_evaluation_strategy(evaluation_strategy)
            .build()
        )
    except PSALMConfigError as exc:
        raise TrialStartError(code=exc.code, message=exc.message, context=exc.context) from exc


async def run_trial(store: TrialStore, trial_id: str, psalm, source_text: str, target_text: str) -> None:
    try:
        async for event in psalm.astream_evaluate(source_text, target_text):
            await store.append_event(trial_id, event.model_dump(mode="json"))
            if event.type == "final_verdict_reached":
                await store.mark_done(trial_id, event.result.model_dump(mode="json"))
    except PSALMError as exc:
        await store.mark_error(trial_id, exc.message)
    except Exception as exc:  # noqa: BLE001 - any unexpected failure must still surface to the UI
        await store.mark_error(trial_id, str(exc))
