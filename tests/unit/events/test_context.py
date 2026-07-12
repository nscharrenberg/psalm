from psalm.events.base import EventSink, PSALMEvent
from psalm.events.context import _current_dimension, _current_sink, emit
from tests.conftest import bound_event_sink, drain_events


async def test_emit_is_noop_without_bound_sink():
    # No sink bound anywhere in this test's task context — must not raise or block.
    await emit(PSALMEvent(category="lifecycle", type="run_started"))


async def test_emit_delivers_to_bound_sink():
    sink = EventSink(run_id="run-abc")
    token = _current_sink.set(sink)
    try:
        await emit(PSALMEvent(category="lifecycle", type="run_started"))
    finally:
        _current_sink.reset(token)

    delivered = await sink.get()
    assert delivered.run_id == "run-abc"
    assert delivered.type == "run_started"


async def test_emit_fills_dimension_from_ambient_context():
    sink = EventSink(run_id="run-abc")
    sink_token = _current_sink.set(sink)
    dim_token = _current_dimension.set("character")
    try:
        await emit(PSALMEvent(category="argumentation", type="argumentation_round_started"))
    finally:
        _current_sink.reset(sink_token)
        _current_dimension.reset(dim_token)

    delivered = await sink.get()
    assert delivered.dimension == "character"


async def test_emit_does_not_override_explicit_dimension():
    sink = EventSink(run_id="run-abc")
    sink_token = _current_sink.set(sink)
    dim_token = _current_dimension.set("character")
    try:
        await emit(PSALMEvent(
            category="argumentation", type="argumentation_round_started", dimension="plot",
        ))
    finally:
        _current_sink.reset(sink_token)
        _current_dimension.reset(dim_token)

    delivered = await sink.get()
    assert delivered.dimension == "plot"


async def test_bound_event_sink_and_drain_events_helpers():
    with bound_event_sink() as sink:
        await emit(PSALMEvent(category="lifecycle", type="run_started"))
        await emit(PSALMEvent(category="lifecycle", type="run_started"))
        events = await drain_events(sink)
    assert len(events) == 2
    assert events[0].sequence == 1
    assert events[1].sequence == 2
