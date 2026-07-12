from psalm.events.base import EventSink, PSALMEvent


def test_psalm_event_generates_unique_id_and_defaults():
    e1 = PSALMEvent(category="lifecycle", type="run_started")
    e2 = PSALMEvent(category="lifecycle", type="run_started")
    assert e1.event_id != e2.event_id
    assert e1.sequence == 0
    assert e1.run_id == ""
    assert e1.dimension is None


async def test_event_sink_put_stamps_run_id_and_increments_sequence():
    sink = EventSink(run_id="run-123")
    await sink.put(PSALMEvent(category="lifecycle", type="run_started"))
    await sink.put(PSALMEvent(category="lifecycle", type="run_started"))

    first = await sink.get()
    second = await sink.get()

    assert first.run_id == "run-123"
    assert second.run_id == "run-123"
    assert first.sequence == 1
    assert second.sequence == 2


async def test_event_sink_empty_reflects_queue_state():
    sink = EventSink(run_id="run-123")
    assert sink.empty() is True
    await sink.put(PSALMEvent(category="lifecycle", type="run_started"))
    assert sink.empty() is False
    await sink.get()
    assert sink.empty() is True
