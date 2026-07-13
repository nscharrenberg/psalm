import asyncio
from unittest.mock import AsyncMock, patch

from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
from main import app
from routes import start_trial
from schemas import TrialConfigRequest
from trials import store

from psalm.dimensions.base import Importance
from psalm.events import FinalVerdictReached, RunStarted
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
    DimensionVerdict,
    PSALMResult,
    ResultMetadata,
)


def _valid_payload(**overrides) -> dict:
    payload = {
        "source_text": "source text", "target_text": "target text", "dimensions": ["Character"],
        "prosecutor": {"api_key": "sk-p"}, "defense": {"api_key": "sk-d"}, "judge": {"api_key": "sk-j"},
        "jury": [{"api_key": "sk-j0"}, {"api_key": "sk-j1"}, {"api_key": "sk-j2"}],
    }
    payload.update(overrides)
    return payload


def _fake_result() -> PSALMResult:
    return PSALMResult(
        verdict="Guilty", rationale="Because.",
        dimension_verdicts=[
            DimensionVerdict(
                dimension="Character", importance=Importance.HIGH, verdict="Guilty", weighted_score=0.8,
                argumentation_log=ArgumentationLog(rounds=[]),
                debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
            )
        ],
        metadata=ResultMetadata(
            duration_seconds=1.0, argumentation_rounds_used=1, deliberation_rounds_used=1,
            voting_strategy_applied="unanimous",
        ),
    )


def _fake_astream_evaluate(self, source_text, target_text):
    async def _gen():
        yield RunStarted(
            dimensions=["Character"], evaluation_strategy="fully_separate",
            source_length=len(source_text), target_length=len(target_text),
        )
        yield FinalVerdictReached(result=_fake_result())
    return _gen()


def test_post_trials_returns_202_and_trial_id():
    store._trials.clear()
    store._current_id = None
    with (
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
        patch("psalm.builder._BuiltPSALM.astream_evaluate", new=_fake_astream_evaluate),
    ):
        client = TestClient(app)
        response = client.post("/api/trials", json=_valid_payload())
    assert response.status_code == 202
    assert "trial_id" in response.json()


def test_post_trials_runs_trial_and_populates_store():
    store._trials.clear()
    store._current_id = None
    with (
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
        patch("psalm.builder._BuiltPSALM.astream_evaluate", new=_fake_astream_evaluate),
    ):
        client = TestClient(app)
        response = client.post("/api/trials", json=_valid_payload())
        trial_id = response.json()["trial_id"]

    record = store.get(trial_id)
    assert record is not None
    assert record.status == "done"
    assert record.result["verdict"] == "Guilty"
    assert len(record.events) == 2


def test_post_trials_returns_409_when_already_running():
    store._trials.clear()
    store._current_id = None
    store.create("s", "t", {})  # leaves is_running() == True, nothing marks it done

    client = TestClient(app)
    response = client.post("/api/trials", json=_valid_payload())
    assert response.status_code == 409


def test_post_trials_reserves_the_slot_before_the_slow_build_step():
    """A second POST arriving while the first is still inside build_psalm() (before
    store.create() has run) must also get 409 — proving the reservation, not just the
    post-create() is_running() check, closes the race window."""
    store._trials.clear()
    store._current_id = None
    store._reserved = False

    # Reserve the slot exactly the way the route does at the very start of the handler,
    # simulating "a first request is mid-flight inside build_psalm() right now".
    assert store.try_reserve() is True

    client = TestClient(app)
    response = client.post("/api/trials", json=_valid_payload())
    assert response.status_code == 409

    store.release_reservation()


async def test_two_concurrent_start_trial_calls_admit_only_one_trial():
    """Directly drives two 'simultaneous' invocations of the start_trial() coroutine
    via asyncio.gather, with build_psalm patched to `await asyncio.sleep(0)` before
    returning. Because asyncio only switches coroutines at an `await`, both calls get
    to run their synchronous reservation check before either can finish build_psalm —
    reproducing the exact double-click / two-tabs race the finding describes. Exactly
    one call must be admitted (returns a trial_id dict); the other must be rejected
    with a 409 HTTPException. Two admissions would mean two trials running at once."""
    store._trials.clear()
    store._current_id = None
    store._reserved = False

    resolved = {
        "prosecutor": {"model": "m", "base_url": "b"},
        "defense": {"model": "m", "base_url": "b"},
        "judge": {"model": "m", "base_url": "b"},
        "jury": [{"model": "m", "base_url": "b"} for _ in range(3)],
    }

    async def slow_build_psalm(config, resolved_arg):
        await asyncio.sleep(0.05)
        return object()

    config = TrialConfigRequest(**_valid_payload())

    with (
        patch("routes.resolve_config", return_value=resolved),
        patch("routes.build_psalm", new=slow_build_psalm),
    ):
        results = await asyncio.gather(
            start_trial(config, BackgroundTasks()),
            start_trial(config, BackgroundTasks()),
            return_exceptions=True,
        )

    successes = [r for r in results if isinstance(r, dict)]
    failures = [r for r in results if isinstance(r, HTTPException)]
    assert len(successes) == 1, f"expected exactly 1 admitted trial, got {len(successes)}: {results}"
    assert len(failures) == 1
    assert failures[0].status_code == 409


def test_post_trials_returns_400_when_api_key_missing(monkeypatch):
    store._trials.clear()
    store._current_id = None
    for key in ("PSALM_API_KEY", "PSALM_PROSECUTOR_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    client = TestClient(app)
    response = client.post("/api/trials", json=_valid_payload(prosecutor={}))
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PSALM-WEB-001"


def test_get_trial_events_endpoint_streams_backlog_for_done_trial():
    store._trials.clear()
    store._current_id = None
    record = store.create("s", "t", {})
    asyncio.run(store.append_event(record.id, {"type": "run_started"}))
    asyncio.run(store.mark_done(record.id, {"verdict": "Guilty"}))

    client = TestClient(app)
    with client.stream("GET", f"/api/trials/{record.id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "run_started" in body


def test_get_trial_events_endpoint_404s_for_unknown_trial():
    client = TestClient(app)
    response = client.get("/api/trials/nonexistent/events")
    assert response.status_code == 404
