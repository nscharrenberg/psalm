from fastapi.testclient import TestClient
from main import app
from trials import store


def test_list_trials_returns_empty_list_initially():
    store._trials.clear()
    store._current_id = None
    client = TestClient(app)
    response = client.get("/api/trials")
    assert response.status_code == 200
    assert response.json() == []


def test_list_trials_returns_newest_first():
    store._trials.clear()
    store._current_id = None
    first = store.create("s1", "t1", {})
    second = store.create("s2", "t2", {})

    client = TestClient(app)
    response = client.get("/api/trials")
    ids = [t["id"] for t in response.json()]
    assert ids == [second.id, first.id]


def test_get_trial_returns_detail():
    store._trials.clear()
    store._current_id = None
    record = store.create("source", "target", {"prosecutor": {"model": "gpt-4o"}})

    client = TestClient(app)
    response = client.get(f"/api/trials/{record.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == record.id
    assert body["status"] == "running"
    assert body["config_summary"] == {"prosecutor": {"model": "gpt-4o"}}


def test_get_trial_returns_404_for_unknown_id():
    client = TestClient(app)
    response = client.get("/api/trials/nonexistent")
    assert response.status_code == 404
