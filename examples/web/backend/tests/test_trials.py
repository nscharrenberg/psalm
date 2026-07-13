import asyncio

from trials import TrialStore, trial_detail, trial_summary


def test_create_returns_running_record():
    store = TrialStore()
    record = store.create("source", "target", {"prosecutor": {"model": "gpt-4o"}})
    assert record.status == "running"
    assert record.source_text == "source"
    assert record.target_text == "target"
    assert record.events == []
    assert record.result is None


def test_is_running_reflects_current_trial_status():
    store = TrialStore()
    assert store.is_running() is False
    store.create("s", "t", {})
    assert store.is_running() is True


async def test_mark_done_stops_is_running():
    store = TrialStore()
    record = store.create("s", "t", {})
    await store.mark_done(record.id, {"verdict": "Guilty"})
    assert store.is_running() is False
    assert store.get(record.id).status == "done"
    assert store.get(record.id).result == {"verdict": "Guilty"}


async def test_mark_error_stops_is_running():
    store = TrialStore()
    record = store.create("s", "t", {})
    await store.mark_error(record.id, "LLM connection failed")
    assert store.is_running() is False
    assert store.get(record.id).status == "error"
    assert store.get(record.id).error_message == "LLM connection failed"


def test_get_returns_none_for_unknown_id():
    store = TrialStore()
    assert store.get("nonexistent") is None


def test_list_all_returns_newest_first():
    store = TrialStore()
    first = store.create("s1", "t1", {})
    second = store.create("s2", "t2", {})
    ids_in_order = [r.id for r in store.list_all()]
    assert ids_in_order == [second.id, first.id]


async def test_append_event_adds_to_events_list():
    store = TrialStore()
    record = store.create("s", "t", {})
    await store.append_event(record.id, {"type": "run_started"})
    assert store.get(record.id).events == [{"type": "run_started"}]


async def test_append_event_wakes_a_waiting_consumer():
    store = TrialStore()
    record = store.create("s", "t", {})

    async def waiter() -> bool:
        async with record.condition:
            await asyncio.wait_for(record.condition.wait(), timeout=2)
        return True

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)
    await store.append_event(record.id, {"type": "test_event"})
    woke = await asyncio.wait_for(task, timeout=1)
    assert woke is True


def test_try_reserve_succeeds_when_idle():
    store = TrialStore()
    assert store.try_reserve() is True
    assert store.is_running() is True


def test_try_reserve_fails_when_already_reserved():
    store = TrialStore()
    assert store.try_reserve() is True
    assert store.try_reserve() is False


def test_try_reserve_fails_when_a_trial_is_already_running():
    store = TrialStore()
    store.create("s", "t", {})
    assert store.try_reserve() is False


def test_release_reservation_allows_a_subsequent_reserve():
    store = TrialStore()
    assert store.try_reserve() is True
    store.release_reservation()
    assert store.is_running() is False
    assert store.try_reserve() is True


def test_create_clears_the_reservation_flag():
    store = TrialStore()
    store.try_reserve()
    store.create("s", "t", {})
    # is_running() should now reflect the real trial record, not a stale reservation
    assert store.is_running() is True
    store2_check = store.try_reserve()  # should fail because a real trial is running, not because of a stale flag
    assert store2_check is False


def test_trial_summary_previews_texts():
    store = TrialStore()
    record = store.create("a" * 300, "b" * 300, {})
    summary = trial_summary(record)
    assert summary.id == record.id
    assert summary.status == "running"
    assert len(summary.source_text_preview) <= 200
    assert len(summary.target_text_preview) <= 200


def test_trial_detail_includes_config_summary_and_result():
    store = TrialStore()
    record = store.create("s", "t", {"prosecutor": {"model": "gpt-4o"}})
    detail = trial_detail(record)
    assert detail.config_summary == {"prosecutor": {"model": "gpt-4o"}}
    assert detail.result is None
