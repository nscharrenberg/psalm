from __future__ import annotations

from catalog import build_catalog
from execution import TrialStartError, build_psalm, resolve_config, run_trial
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from schemas import CatalogResponse, TrialConfigRequest, TrialDetail, TrialSummary
from sse import stream_trial_events
from trials import store, trial_detail, trial_summary

api_router = APIRouter(prefix="/api")


@api_router.get("/catalog", response_model=CatalogResponse)
def get_catalog() -> CatalogResponse:
    return build_catalog()


@api_router.post("/trials", status_code=202)
async def start_trial(config: TrialConfigRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    if not store.try_reserve():
        raise HTTPException(status_code=409, detail="A trial is already in progress.")

    try:
        resolved = resolve_config(config)
        psalm = await build_psalm(config, resolved)
    except TrialStartError as exc:
        store.release_reservation()
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message, "context": exc.context},
        ) from exc

    config_summary = {
        "prosecutor": {"model": resolved["prosecutor"]["model"], "base_url": resolved["prosecutor"]["base_url"]},
        "defense": {"model": resolved["defense"]["model"], "base_url": resolved["defense"]["base_url"]},
        "judge": {"model": resolved["judge"]["model"], "base_url": resolved["judge"]["base_url"]},
        "jury": [{"model": j["model"], "base_url": j["base_url"]} for j in resolved["jury"]],
        "dimensions": config.dimensions,
        "evaluation_strategy": config.evaluation_strategy,
    }
    record = store.create(config.source_text, config.target_text, config_summary)
    background_tasks.add_task(run_trial, store, record.id, psalm, config.source_text, config.target_text)
    return {"trial_id": record.id}


@api_router.get("/trials", response_model=list[TrialSummary])
def list_trials() -> list[TrialSummary]:
    return [trial_summary(r) for r in store.list_all()]


@api_router.get("/trials/{trial_id}", response_model=TrialDetail)
def get_trial(trial_id: str) -> TrialDetail:
    record = store.get(trial_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Trial not found.")
    return trial_detail(record)


@api_router.get("/trials/{trial_id}/events")
async def stream_events(trial_id: str):
    if store.get(trial_id) is None:
        raise HTTPException(status_code=404, detail="Trial not found.")
    return StreamingResponse(stream_trial_events(store, trial_id), media_type="text/event-stream")
