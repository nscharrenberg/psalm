from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from schemas import TrialDetail, TrialSummary

TrialStatus = Literal["running", "done", "error"]

_PREVIEW_LENGTH = 200


@dataclass
class TrialRecord:
    id: str
    created_at: datetime
    status: TrialStatus
    source_text: str
    target_text: str
    config_summary: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error_message: str | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition, repr=False)


class TrialStore:
    def __init__(self) -> None:
        self._trials: dict[str, TrialRecord] = {}
        self._current_id: str | None = None

    def is_running(self) -> bool:
        if self._current_id is None:
            return False
        return self._trials[self._current_id].status == "running"

    def create(self, source_text: str, target_text: str, config_summary: dict[str, Any]) -> TrialRecord:
        trial_id = str(uuid.uuid4())
        record = TrialRecord(
            id=trial_id,
            created_at=datetime.now(timezone.utc),
            status="running",
            source_text=source_text,
            target_text=target_text,
            config_summary=config_summary,
        )
        self._trials[trial_id] = record
        self._current_id = trial_id
        return record

    def get(self, trial_id: str) -> TrialRecord | None:
        return self._trials.get(trial_id)

    def list_all(self) -> list[TrialRecord]:
        return sorted(self._trials.values(), key=lambda r: r.created_at, reverse=True)

    async def append_event(self, trial_id: str, event: dict[str, Any]) -> None:
        record = self._trials[trial_id]
        async with record.condition:
            record.events.append(event)
            record.condition.notify_all()

    async def mark_done(self, trial_id: str, result: dict[str, Any]) -> None:
        record = self._trials[trial_id]
        async with record.condition:
            record.status = "done"
            record.result = result
            record.condition.notify_all()

    async def mark_error(self, trial_id: str, error_message: str) -> None:
        record = self._trials[trial_id]
        async with record.condition:
            record.status = "error"
            record.error_message = error_message
            record.condition.notify_all()


def _preview(text: str) -> str:
    return text if len(text) <= _PREVIEW_LENGTH else text[:_PREVIEW_LENGTH]


def trial_summary(record: TrialRecord) -> TrialSummary:
    verdict = record.result.get("verdict") if record.result else None
    return TrialSummary(
        id=record.id,
        created_at=record.created_at.isoformat(),
        status=record.status,
        source_text_preview=_preview(record.source_text),
        target_text_preview=_preview(record.target_text),
        verdict=verdict,
        error_message=record.error_message,
    )


def trial_detail(record: TrialRecord) -> TrialDetail:
    summary = trial_summary(record)
    return TrialDetail(
        **summary.model_dump(),
        config_summary=record.config_summary,
        result=record.result,
    )


store = TrialStore()
