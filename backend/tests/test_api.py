
import pytest
from fastapi.testclient import TestClient

from geostride.core.session import SessionStore
from geostride.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_store(client):
    return client.app.state.session_store


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded (OSM unreachable)")
    assert data["version"] == "1.0.0"


def test_set_location(client, session_store):
    response = client.post(
        "/set-location",
        json={"session_id": "test_session", "lat": 10.0, "lon": 20.0},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    location = session_store.get("test_session", "location")
    assert location == {"lat": 10.0, "lon": 20.0}


def test_set_location_missing_fields(client):
    response = client.post("/set-location", json={"session_id": "test"})
    assert response.status_code == 400


def test_get_route_not_found(client):
    response = client.get("/get-route/nonexistent")
    assert response.status_code == 404


def test_cached_regions(client):
    response = client.get("/cached-regions")
    assert response.status_code == 200
    data = response.json()
    assert "regions" in data


def test_execute_no_origin_no_session(client):
    response = client.post("/execute", json={"duration_minutes": 30})
    assert response.status_code == 400


def test_execute_with_session_no_location(client):
    response = client.post(
        "/execute",
        json={"session_id": "empty_session", "duration_minutes": 30},
    )
    assert response.status_code == 400


class TestSessionStore:
    def test_set_and_get(self):
        store = SessionStore(ttl_seconds=3600)
        store.set("s1", "location", {"lat": 1.0, "lon": 2.0})
        assert store.get("s1", "location") == {"lat": 1.0, "lon": 2.0}

    def test_get_missing_key(self):
        store = SessionStore()
        assert store.get("s1", "nonexistent") is None

    def test_get_missing_session(self):
        store = SessionStore()
        assert store.get("no_session", "key") is None

    def test_update_timestamp_on_get(self):
        store = SessionStore(ttl_seconds=3600)
        store.set("s1", "key", "value")
        first = store.get("s1", "key")
        second = store.get("s1", "key")
        assert first == second == "value"
