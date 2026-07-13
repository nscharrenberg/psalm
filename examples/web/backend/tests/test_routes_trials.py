from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from main import app
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


def test_post_trials_returns_400_when_api_key_missing(monkeypatch):
    store._trials.clear()
    store._current_id = None
    for key in ("PSALM_API_KEY", "PSALM_PROSECUTOR_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    client = TestClient(app)
    response = client.post("/api/trials", json=_valid_payload(prosecutor={}))
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PSALM-WEB-001"
