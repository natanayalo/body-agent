from fastapi.testclient import TestClient
from conftest import configure_test_logging
from app.main import app

# Configure test logging before importing app
configure_test_logging()

# Create test client
client = TestClient(app)


def test_graph_run_basic_query():
    response = client.post(
        "/api/graph/run",
        json={"user_id": "test-user", "query": "I have a fever of 38.8C"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert data["state"]["user_id"] == "test-user"
    assert data["state"]["user_query"] == "I have a fever of 38.8C"


def test_graph_run_with_pii():
    response = client.post(
        "/api/graph/run",
        json={
            "user_id": "test-user",
            "query": "My phone number is 123-456-7890 and email is test@example.com",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert "[phone]" in data["state"]["user_query_redacted"]
    assert "[email]" in data["state"]["user_query_redacted"]
    assert "123-456-7890" not in data["state"]["user_query_redacted"]
    assert "test@example.com" not in data["state"]["user_query_redacted"]
