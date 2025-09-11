import pytest
from fastapi.testclient import TestClient
from app.main import app
import os


@pytest.fixture(scope="session", autouse=True)
def set_es_host():
    os.environ["ES_HOST"] = "http://localhost:9200"


client = TestClient(app)


def test_healthz_real():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_graph_run_real():
    payload = {"user_id": "real-user", "query": "I have a headache"}
    r = client.post("/api/graph/run", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "state" in data
    assert data["state"]["user_id"] == "real-user"
    assert data["state"]["user_query"] == "I have a headache"
