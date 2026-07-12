from __future__ import annotations

from contextvars import ContextVar

from psalm.events.base import EventSink, PSALMEvent

_current_sink: ContextVar[EventSink | None] = ContextVar("_current_sink", default=None)
_current_dimension: ContextVar[str | None] = ContextVar("_current_dimension", default=None)


async def emit(event: PSALMEvent) -> None:
    sink = _current_sink.get()
    if sink is None:
        return
    if event.dimension is None:
        dim = _current_dimension.get()
        if dim is not None:
            event = event.model_copy(update={"dimension": dim})
    await sink.put(event)
