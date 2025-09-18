import json
from fastapi.testclient import TestClient


def test_graph_stream_basic_query(client: TestClient):
    response = client.post(
        "/api/graph/stream",
        json={"user_id": "test-user", "query": "I have a fever of 38.8C"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    # Collect all streamed data
    streamed_data = response.text
    # Split the streamed data into individual JSON objects
    json_objects = [
        line.replace("data: ", "")
        for line in streamed_data.strip().split("\n\n")
        if line
    ]
    # Parse each JSON object
    events = [json.loads(obj) for obj in json_objects]
    # Check for the final state
    assert any("final" in event for event in events)


def test_graph_stream_pii_redaction(client: TestClient):
    response = client.post(
        "/api/graph/stream",
        json={
            "user_id": "test-user",
            "query": "My phone number is 123-456-7890 and email is test@example.com",
        },
    )
    assert response.status_code == 200
    streamed_data = response.text
    json_objects = [
        line.replace("data: ", "")
        for line in streamed_data.strip().split("\n\n")
        if line
    ]
    events = [json.loads(obj) for obj in json_objects]
    # Find the scrub node output
    scrub_output = None
    for event in events:
        if event.get("node") == "scrub":
            scrub_output = event.get("delta")
            break
    assert scrub_output is not None
    assert "[phone]" in scrub_output["user_query_redacted"]
    assert "[email]" in scrub_output["user_query_redacted"]


def test_graph_stream_supervisor_routing(client: TestClient):
    response = client.post(
        "/api/graph/stream",
        json={"user_id": "test-user", "query": "I need to book a lab appointment"},
    )
    assert response.status_code == 200
    streamed_data = response.text
    json_objects = [
        line.replace("data: ", "")
        for line in streamed_data.strip().split("\n\n")
        if line
    ]
    events = [json.loads(obj) for obj in json_objects]
    # Find the supervisor node output
    supervisor_output = None
    for event in events:
        if event.get("node") == "supervisor":
            supervisor_output = event.get("delta")
            break
    assert supervisor_output is not None
    assert supervisor_output["intent"] == "appointment"


def test_graph_stream_final_state_matches_run(client: TestClient):
    # Choose a query that routes to planner directly (no ES dependency)
    payload = {"user_id": "test-user", "query": "weekly check-in"}

    # Non-streaming final state
    r1 = client.post("/api/graph/run", json=payload)
    assert r1.status_code == 200
    run_state = r1.json()["state"]

    # Streaming: collect events and extract final state
    r2 = client.post("/api/graph/stream", json=payload)
    assert r2.status_code == 200
    streamed = r2.text
    events = [
        json.loads(line.replace("data: ", ""))
        for line in streamed.strip().split("\n\n")
        if line
    ]
    final_state = None
    for ev in reversed(events):
        if "final" in ev:
            final_state = ev["final"]["state"]
            break
    assert final_state is not None

    # Compare core fields for equality
    for key in ["user_id", "user_query", "user_query_redacted", "intent", "plan"]:
        assert run_state.get(key) == final_state.get(key)
